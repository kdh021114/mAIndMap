from __future__ import annotations

from dataclasses import dataclass

from flask import Flask

from app.application.chat_use_cases import LoadThreadMessagesUseCase, SendMessageUseCase
from app.application.context_builder import AncestorContextPolicy, AncestorLineageContextBuilder
from app.application.graph_use_cases import (
    AddChildNodeUseCase,
    CreateGraphThreadUseCase,
    CreateRootNodeUseCase,
    DeleteGraphThreadUseCase,
    DeleteNodeUseCase,
    DeleteNodesUseCase,
    EditEdgePhraseUseCase,
    GenerateMissingGraphLabelsUseCase,
    MoveNodeUseCase,
    MoveNodesUseCase,
    RenameNodeUseCase,
    SwitchGraphThreadUseCase,
)
from app.application.history_use_cases import (
    GetWorkspaceSnapshotUseCase,
    RestoreWorkspaceSnapshotUseCase,
)
from app.application.restructure_use_cases import (
    MergeSiblingNodesUseCase,
    SplitNodeUseCase,
)
from app.application.search_use_cases import SearchWorkspaceUseCase
from app.application.settings_use_cases import ChangeLocaleUseCase
from app.application.workspace_state import GetWorkspaceStateUseCase
from app.domain.graph import NodePosition, TreeGraphPolicy
from app.infrastructure.layout.tree_layout_service import TreeLayoutConfig, TreeLayoutService
from app.infrastructure.llm.llm_factory import LlmConfig, LlmProviderFactory
from app.infrastructure.persistence.json_repositories import (
    JsonChatRepository,
    JsonGraphRepository,
    JsonSettingsRepository,
    JsonWorkspaceSnapshotRepository,
)
from app.infrastructure.persistence.json_store import JsonStore
from app.presentation.web.routes import register_routes


@dataclass(frozen=True)
class UseCaseContainer:
    get_workspace_state: GetWorkspaceStateUseCase
    create_graph_thread: CreateGraphThreadUseCase
    switch_graph_thread: SwitchGraphThreadUseCase
    delete_graph_thread: DeleteGraphThreadUseCase
    create_root_node: CreateRootNodeUseCase
    add_child_node: AddChildNodeUseCase
    rename_node: RenameNodeUseCase
    move_node: MoveNodeUseCase
    move_nodes: MoveNodesUseCase
    delete_node: DeleteNodeUseCase
    delete_nodes: DeleteNodesUseCase
    edit_edge_phrase: EditEdgePhraseUseCase
    generate_missing_graph_labels: GenerateMissingGraphLabelsUseCase
    load_thread_messages: LoadThreadMessagesUseCase
    send_message: SendMessageUseCase
    change_locale: ChangeLocaleUseCase
    get_workspace_snapshot: GetWorkspaceSnapshotUseCase
    restore_workspace_snapshot: RestoreWorkspaceSnapshotUseCase
    search_workspace: SearchWorkspaceUseCase
    merge_sibling_nodes: MergeSiblingNodesUseCase
    split_node: SplitNodeUseCase


def create_app(config_module) -> Flask:
    store = JsonStore(config_module.DATA_FILE)
    graph_repository = JsonGraphRepository(store)
    chat_repository = JsonChatRepository(store)
    snapshot_repository = JsonWorkspaceSnapshotRepository(store)
    settings_repository = JsonSettingsRepository(
        store,
        default_locale=config_module.DEFAULT_LOCALE,
        supported_locales=config_module.SUPPORTED_LOCALES,
    )

    llm_services = LlmProviderFactory(
        LlmConfig(
            api_key=config_module.OPENAI_API_KEY,
            chat_model=config_module.OPENAI_CHAT_MODEL,
            edge_model=config_module.OPENAI_EDGE_MODEL,
            title_model=config_module.OPENAI_TITLE_MODEL,
            reasoning_effort=config_module.OPENAI_REASONING_EFFORT,
            text_verbosity=config_module.OPENAI_TEXT_VERBOSITY,
            chat_max_output_tokens=config_module.OPENAI_CHAT_MAX_OUTPUT_TOKENS,
            label_max_output_tokens=config_module.OPENAI_LABEL_MAX_OUTPUT_TOKENS,
            store_responses=config_module.OPENAI_STORE_RESPONSES,
            timeout_seconds=config_module.OPENAI_TIMEOUT_SECONDS,
            web_search_enabled=getattr(config_module, "OPENAI_WEB_SEARCH_ENABLED", False),
            web_search_context_size=getattr(config_module, "OPENAI_WEB_SEARCH_CONTEXT_SIZE", "low"),
            web_search_max_tool_calls=getattr(config_module, "OPENAI_WEB_SEARCH_MAX_TOOL_CALLS", 1),
            web_search_tool_choice=getattr(config_module, "OPENAI_WEB_SEARCH_TOOL_CHOICE", "auto"),
            web_search_external_access=getattr(config_module, "OPENAI_WEB_SEARCH_EXTERNAL_ACCESS", True),
            use_mock_when_no_api_key=config_module.USE_MOCK_LLM_WHEN_NO_API_KEY,
            test_mode=config_module.TEST_MODE,
        )
    ).create_services()

    tree_policy = TreeGraphPolicy()
    ancestor_context_builder = AncestorLineageContextBuilder(
        graph_repository=graph_repository,
        chat_repository=chat_repository,
        policy=AncestorContextPolicy(
            include_full_ancestor_lineage=config_module.INCLUDE_FULL_ANCESTOR_LINEAGE,
            message_limit_per_ancestor=config_module.ANCESTOR_CONTEXT_MESSAGE_LIMIT,
        ),
    )
    layout_service = TreeLayoutService(
        TreeLayoutConfig(
            node_width=config_module.NODE_WIDTH,
            node_height=config_module.NODE_HEIGHT,
            horizontal_gap=config_module.TREE_HORIZONTAL_GAP,
            vertical_gap=config_module.TREE_VERTICAL_GAP,
            margin_x=config_module.TREE_MARGIN_X,
            margin_y=config_module.TREE_MARGIN_Y,
        )
    )

    use_cases = UseCaseContainer(
        get_workspace_state=GetWorkspaceStateUseCase(
            graph_repository=graph_repository,
            chat_repository=chat_repository,
            settings_repository=settings_repository,
            layout_service=layout_service,
            app_title=config_module.APP_TITLE,
            llm_mode=llm_services.mode,
            web_search_available=llm_services.web_search_available,
        ),
        create_graph_thread=CreateGraphThreadUseCase(
            graph_repository=graph_repository,
            settings_repository=settings_repository,
        ),
        switch_graph_thread=SwitchGraphThreadUseCase(
            graph_repository=graph_repository,
            settings_repository=settings_repository,
        ),
        delete_graph_thread=DeleteGraphThreadUseCase(
            graph_repository=graph_repository,
            chat_repository=chat_repository,
            settings_repository=settings_repository,
        ),
        create_root_node=CreateRootNodeUseCase(
            graph_repository=graph_repository,
            chat_repository=chat_repository,
            settings_repository=settings_repository,
            tree_policy=tree_policy,
            root_position=NodePosition(
                x=config_module.ROOT_NODE_X,
                y=config_module.ROOT_NODE_Y,
            ),
        ),
        add_child_node=AddChildNodeUseCase(
            graph_repository=graph_repository,
            chat_repository=chat_repository,
            tree_policy=tree_policy,
            default_horizontal_gap=config_module.TREE_HORIZONTAL_GAP,
            default_vertical_gap=config_module.TREE_VERTICAL_GAP,
        ),
        rename_node=RenameNodeUseCase(
            graph_repository=graph_repository,
            chat_repository=chat_repository,
        ),
        move_node=MoveNodeUseCase(graph_repository=graph_repository),
        move_nodes=MoveNodesUseCase(graph_repository=graph_repository),
        delete_node=DeleteNodeUseCase(
            graph_repository=graph_repository,
            chat_repository=chat_repository,
        ),
        delete_nodes=DeleteNodesUseCase(
            graph_repository=graph_repository,
            chat_repository=chat_repository,
        ),
        edit_edge_phrase=EditEdgePhraseUseCase(graph_repository=graph_repository),
        generate_missing_graph_labels=GenerateMissingGraphLabelsUseCase(
            graph_repository=graph_repository,
            chat_repository=chat_repository,
            title_generator=llm_services.title_generator,
            edge_phrase_generator=llm_services.edge_phrase_generator,
        ),
        load_thread_messages=LoadThreadMessagesUseCase(chat_repository=chat_repository),
        send_message=SendMessageUseCase(
            graph_repository=graph_repository,
            chat_repository=chat_repository,
            chat_model=llm_services.chat_model,
            title_generator=llm_services.title_generator,
            edge_phrase_generator=llm_services.edge_phrase_generator,
            ancestor_context_builder=ancestor_context_builder,
            current_thread_message_limit=config_module.CURRENT_THREAD_MESSAGE_LIMIT,
        ),
        change_locale=ChangeLocaleUseCase(settings_repository=settings_repository),
        get_workspace_snapshot=GetWorkspaceSnapshotUseCase(snapshot_repository=snapshot_repository),
        restore_workspace_snapshot=RestoreWorkspaceSnapshotUseCase(snapshot_repository=snapshot_repository),
        search_workspace=SearchWorkspaceUseCase(
            graph_repository=graph_repository,
            chat_repository=chat_repository,
            settings_repository=settings_repository,
        ),
        merge_sibling_nodes=MergeSiblingNodesUseCase(
            graph_repository=graph_repository,
            chat_repository=chat_repository,
            tree_policy=tree_policy,
        ),
        split_node=SplitNodeUseCase(
            graph_repository=graph_repository,
            chat_repository=chat_repository,
            tree_policy=tree_policy,
            title_generator=llm_services.title_generator,
            edge_phrase_generator=llm_services.edge_phrase_generator,
            default_vertical_gap=config_module.TREE_VERTICAL_GAP,
            default_horizontal_gap=config_module.TREE_HORIZONTAL_GAP,
        ),
    )

    flask_app = Flask(__name__, static_folder="presentation/web/static", static_url_path="/static")
    register_routes(flask_app, use_cases)
    return flask_app
