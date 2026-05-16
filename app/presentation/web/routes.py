from __future__ import annotations

from dataclasses import asdict
import math
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from app.domain.graph import NodePosition


STATIC_DIR = Path(__file__).resolve().parent / "static"


def register_routes(app: Flask, use_cases: Any) -> None:
    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/api/state")
    def get_state():
        return jsonify(use_cases.get_workspace_state.execute())

    @app.post("/api/settings/locale")
    def change_locale():
        data = _json_body()
        locale = data.get("locale")
        use_cases.change_locale.execute(locale=locale)
        use_cases.generate_missing_graph_labels.execute(locale=locale)
        return jsonify(use_cases.get_workspace_state.execute())

    @app.post("/api/graph/localize-missing")
    def localize_missing():
        locale = _current_locale(use_cases)
        use_cases.generate_missing_graph_labels.execute(locale=locale)
        return jsonify(use_cases.get_workspace_state.execute())

    @app.post("/api/nodes/root")
    def create_root_node():
        data = _json_body()
        locale = _current_locale(use_cases)
        result = use_cases.create_root_node.execute(
            locale=locale,
            position=_position_from_body(data),
        )
        return jsonify({"result": _to_dict(result), "state": use_cases.get_workspace_state.execute()})

    @app.post("/api/nodes/<node_id>/children")
    def add_child_node(node_id: str):
        data = _json_body()
        locale = _current_locale(use_cases)
        result = use_cases.add_child_node.execute(
            parent_node_id=node_id,
            locale=locale,
            position=_position_from_body(data),
        )
        return jsonify({"result": _to_dict(result), "state": use_cases.get_workspace_state.execute()})

    @app.patch("/api/nodes/<node_id>/title")
    def rename_node(node_id: str):
        data = _json_body()
        locale = _current_locale(use_cases)
        title = data.get("title", "")
        node = use_cases.rename_node.execute(node_id=node_id, locale=locale, title=title)
        return jsonify({"node": _to_dict(node), "state": use_cases.get_workspace_state.execute()})

    @app.patch("/api/nodes/<node_id>/position")
    def move_node(node_id: str):
        data = _json_body()
        position = _position_from_body(data)
        if position is None:
            raise ValueError("Node position requires finite x and y values.")
        node = use_cases.move_node.execute(node_id=node_id, position=position)
        return jsonify({"node": _to_dict(node), "state": use_cases.get_workspace_state.execute()})

    @app.delete("/api/nodes/<node_id>")
    def delete_node(node_id: str):
        use_cases.delete_node.execute(node_id=node_id)
        return jsonify(use_cases.get_workspace_state.execute())

    @app.get("/api/threads/<thread_id>/messages")
    def load_messages(thread_id: str):
        messages = use_cases.load_thread_messages.execute(thread_id=thread_id)
        return jsonify([_to_dict(m) for m in messages])

    @app.post("/api/nodes/<node_id>/messages")
    def send_message(node_id: str):
        data = _json_body()
        locale = _current_locale(use_cases)
        content = data.get("content", "")
        result = use_cases.send_message.execute(node_id=node_id, content=content, locale=locale)
        state = use_cases.get_workspace_state.execute()
        node = next(n for n in state["nodes"] if n["id"] == node_id)
        messages = use_cases.load_thread_messages.execute(thread_id=node["threadId"])
        return jsonify(
            {
                "result": _to_dict(result),
                "messages": [_to_dict(m) for m in messages],
                "state": state,
            }
        )

    @app.patch("/api/edges/<edge_id>/phrase")
    def edit_edge_phrase(edge_id: str):
        data = _json_body()
        locale = _current_locale(use_cases)
        phrase = data.get("phrase", "")
        edge = use_cases.edit_edge_phrase.execute(edge_id=edge_id, locale=locale, phrase=phrase)
        return jsonify({"edge": _to_dict(edge), "state": use_cases.get_workspace_state.execute()})

    @app.errorhandler(Exception)
    def handle_exception(error: Exception):
        status = 400
        if error.__class__.__name__ in {"NotFound", "KeyError"}:
            status = 404
        return jsonify({"error": str(error)}), status


def _json_body() -> dict:
    return request.get_json(silent=True) or {}


def _position_from_body(data: dict) -> NodePosition | None:
    raw_position = data.get("position", data)
    if not isinstance(raw_position, dict):
        return None
    if "x" not in raw_position or "y" not in raw_position:
        return None

    x = _finite_float(raw_position["x"], "x")
    y = _finite_float(raw_position["y"], "y")
    return NodePosition(x=x, y=y)


def _finite_float(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite.")
    return number


def _current_locale(use_cases: Any) -> str:
    return use_cases.get_workspace_state.execute()["locale"]


def _to_dict(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [_to_dict(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, dict):
        return {k: _to_dict(v) for k, v in value.items()}
    return value
