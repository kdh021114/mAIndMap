from __future__ import annotations

from datetime import datetime
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from flask import (
    Blueprint,
    Flask,
    Response,
    g,
    jsonify,
    request,
    send_from_directory,
    stream_with_context,
)

from app.domain.ports import NodeTitleGenerator
from app.infrastructure.persistence.json_repositories import JsonSettingsRepository
from app.infrastructure.persistence.json_store import JsonStore
from chat_ui.domain import ChatMessage, Conversation
from chat_ui.repository import JsonConversationRepository
from chat_ui.streaming import StreamingChatModel
from chat_ui.use_cases import (
    CreateConversationUseCase,
    DeleteConversationUseCase,
    ExportConversationLogsUseCase,
    ListConversationsUseCase,
    LoadMessagesUseCase,
    RenameConversationUseCase,
    StreamReplyUseCase,
)


STATIC_DIR = Path(__file__).resolve().parent / "static"
_UNSAFE_FILENAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


@dataclass(frozen=True)
class ChatUiContainer:
    list_conversations: ListConversationsUseCase
    create_conversation: CreateConversationUseCase
    rename_conversation: RenameConversationUseCase
    delete_conversation: DeleteConversationUseCase
    load_messages: LoadMessagesUseCase
    stream_reply: StreamReplyUseCase
    export_conversation_logs: ExportConversationLogsUseCase
    settings_repository: JsonSettingsRepository


def _build_container(
    store: JsonStore,
    settings_repository: JsonSettingsRepository,
    streaming_chat_model: StreamingChatModel,
    title_generator: NodeTitleGenerator,
) -> ChatUiContainer:
    repo = JsonConversationRepository(store)
    return ChatUiContainer(
        list_conversations=ListConversationsUseCase(repo),
        create_conversation=CreateConversationUseCase(repo),
        rename_conversation=RenameConversationUseCase(repo),
        delete_conversation=DeleteConversationUseCase(repo),
        load_messages=LoadMessagesUseCase(repo),
        stream_reply=StreamReplyUseCase(repo, streaming_chat_model, title_generator),
        export_conversation_logs=ExportConversationLogsUseCase(repo),
        settings_repository=settings_repository,
    )


def _conversation_to_dict(conversation: Conversation) -> dict:
    # Stage 6: return the full LocalizedText so the frontend can re-resolve
    # the display title on a locale toggle without re-fetching.
    return {
        "id": conversation.id,
        "title": dict(conversation.title),
        "createdAt": conversation.created_at,
        "updatedAt": conversation.updated_at,
    }


def _message_to_dict(message: ChatMessage) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "createdAt": message.created_at,
    }


def _sse_frame(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def register_chat_ui(
    app: Flask,
    *,
    store: JsonStore,
    settings_repository: JsonSettingsRepository,
    streaming_chat_model: StreamingChatModel,
    title_generator: NodeTitleGenerator,
) -> None:
    container = _build_container(
        store, settings_repository, streaming_chat_model, title_generator
    )

    bp = Blueprint(
        "chat_ui",
        __name__,
        static_folder=str(STATIC_DIR),
        static_url_path="/chat-static",
    )

    @bp.get("/chat")
    def chat_index():
        return send_from_directory(STATIC_DIR, "index.html")

    @bp.get("/api/chat/locale")
    def get_locale():
        return jsonify({"locale": container.settings_repository.get_locale()})

    @bp.get("/api/chat/export/conversations.zip")
    def export_conversation_logs():
        participant_id = getattr(g, "participant_id", "unknown")
        locale = container.settings_repository.get_locale()
        export = container.export_conversation_logs.execute(locale=locale)
        manifest = dict(export["manifest"])
        manifest["participant_id"] = participant_id

        buffer = io.BytesIO()
        used_names: set[str] = set()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "index.json",
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
            for entry in export["entries"]:
                data = dict(entry["data"])
                data["participant_id"] = participant_id
                basename = _unique_export_name(
                    entry["order"], entry["title"], entry["conversation_id"], used_names
                )
                archive.writestr(
                    f"conversations/{basename}",
                    json.dumps(data, ensure_ascii=False, indent=2),
                )

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_pid = re.sub(r"[^a-zA-Z0-9_-]", "", participant_id)[:20]
        download_name = f"{ts}_{safe_pid}_linear_chat.zip"
        return Response(
            buffer.getvalue(),
            mimetype="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
        )

    @bp.get("/api/chat/conversations")
    def list_conversations():
        conversations = container.list_conversations.execute()
        return jsonify([_conversation_to_dict(c) for c in conversations])

    @bp.post("/api/chat/conversations")
    def create_conversation():
        locale = container.settings_repository.get_locale()
        conversation = container.create_conversation.execute(locale=locale)
        return jsonify(_conversation_to_dict(conversation)), 201

    @bp.patch("/api/chat/conversations/<conversation_id>")
    def rename_conversation(conversation_id: str):
        locale = container.settings_repository.get_locale()
        payload = request.get_json(silent=True) or {}
        title = payload.get("title", "")
        try:
            conversation = container.rename_conversation.execute(
                conversation_id=conversation_id,
                locale=locale,
                title=title,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except KeyError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify(_conversation_to_dict(conversation))

    @bp.delete("/api/chat/conversations/<conversation_id>")
    def delete_conversation(conversation_id: str):
        try:
            container.delete_conversation.execute(conversation_id=conversation_id)
        except KeyError as exc:
            return jsonify({"error": str(exc)}), 404
        return "", 204

    @bp.get("/api/chat/conversations/<conversation_id>/messages")
    def list_messages(conversation_id: str):
        try:
            messages = container.load_messages.execute(conversation_id=conversation_id)
        except KeyError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify([_message_to_dict(m) for m in messages])

    @bp.post("/api/chat/conversations/<conversation_id>/messages")
    def stream_message(conversation_id: str):
        locale = container.settings_repository.get_locale()
        payload = request.get_json(silent=True) or {}
        content = payload.get("content", "")

        # Validate + persist the user message BEFORE returning the generator,
        # so error paths return clean JSON 400/404 instead of half-open SSE.
        try:
            frames = container.stream_reply.execute(
                conversation_id=conversation_id,
                user_text=content,
                locale=locale,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except KeyError as exc:
            return jsonify({"error": str(exc)}), 404

        @stream_with_context
        def generate():
            for frame in frames:
                yield _sse_frame(frame)
            yield "data: [DONE]\n\n"

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    app.register_blueprint(bp)


def _unique_export_name(
    order: int, title: str, id_fallback: str, used_names: set[str], ext: str = ".json"
) -> str:
    safe = _UNSAFE_FILENAME_RE.sub(" ", title or "")
    safe = re.sub(r"\s+", " ", safe).strip()[:50].strip()
    if not safe:
        safe = id_fallback
    base = f"{order:02d}_{safe}"
    candidate = f"{base}{ext}"
    suffix = 2
    while candidate in used_names:
        candidate = f"{base} ({suffix}){ext}"
        suffix += 1
    used_names.add(candidate)
    return candidate
