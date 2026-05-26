"""Application configuration.

Edit this file directly, then run:

    python run.py

Secrets still belong in .env, not in this file.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

# -----------------------------------------------------------------------------
# Runtime
# -----------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 7860
DEBUG = True

# -----------------------------------------------------------------------------
# Test mode
# -----------------------------------------------------------------------------
# True  -> never call OpenAI, even when OPENAI_API_KEY exists.
#          Use this for local UI/data-flow checks with deterministic test doubles.
# False -> use OpenAI when OPENAI_API_KEY is available.
TEST_MODE = False

# -----------------------------------------------------------------------------
# Storage
# -----------------------------------------------------------------------------
DATA_DIR = ROOT_DIR / "storage"
DATA_FILE = DATA_DIR / "data.json"

# -----------------------------------------------------------------------------
# Locale / labels
# -----------------------------------------------------------------------------
DEFAULT_LOCALE = "ko"  # "ko" or "en"
SUPPORTED_LOCALES = ("ko", "en")

# -----------------------------------------------------------------------------
# OpenAI
# -----------------------------------------------------------------------------
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_API_KEY = os.environ.get(OPENAI_API_KEY_ENV, "")

# The main model used for normal conversation in the chat sidebar.
# gpt-5.4-nano is the lowest-cost GPT-5.4-class model and is enough for
# inexpensive end-to-end API smoke tests.
OPENAI_CHAT_MODEL = "gpt-5.4-nano"

# Smaller models used only for graph labels/titles.
# They are deliberately separated from the chat model.
OPENAI_EDGE_MODEL = "gpt-5.4-nano"
OPENAI_TITLE_MODEL = "gpt-5.4-nano"

# Cost controls for Responses API calls.
# "none" keeps reasoning-token use low on GPT-5.4-class models. If a future
# model rejects it, switch to "low" or set this to None.
OPENAI_REASONING_EFFORT = "none"
OPENAI_TEXT_VERBOSITY = "low"
OPENAI_CHAT_MAX_OUTPUT_TOKENS = 512
OPENAI_LABEL_MAX_OUTPUT_TOKENS = 80
OPENAI_STORE_RESPONSES = False
OPENAI_TIMEOUT_SECONDS = 45.0

# Optional web search for chat replies.
# The UI exposes this as a per-message toggle. Keep the global switch True if
# you want the toggle to work; turn it False to block web search API use.
OPENAI_WEB_SEARCH_ENABLED = True
OPENAI_WEB_SEARCH_CONTEXT_SIZE = "low"  # "low", "medium", or "high"
OPENAI_WEB_SEARCH_MAX_TOOL_CALLS = 1
# "required" makes the chat composer toggle mean "search this message".
# Use "auto" if you only want to allow search and let the model decide.
OPENAI_WEB_SEARCH_TOOL_CHOICE = "required"
OPENAI_WEB_SEARCH_EXTERNAL_ACCESS = True

# Keep this False when you specifically want to verify real OpenAI wiring.
# Set to True only if you want the app to fall back to local mocks without a key.
# This is ignored when TEST_MODE=True, because test mode always blocks LLM calls.
USE_MOCK_LLM_WHEN_NO_API_KEY = False

# -----------------------------------------------------------------------------
# Context policy
# -----------------------------------------------------------------------------
# The graph is a rooted tree. When chatting in a selected node, the LLM receives:
#   1. the current selected node's recent messages, and
#   2. the ancestor lineage from root -> ... -> direct parent.
# Siblings and child branches are never passed by default.
INCLUDE_FULL_ANCESTOR_LINEAGE = True
ANCESTOR_CONTEXT_MESSAGE_LIMIT = 8
CURRENT_THREAD_MESSAGE_LIMIT = 20

# -----------------------------------------------------------------------------
# Graph canvas
# -----------------------------------------------------------------------------
# Stored node positions use a freeform canvas coordinate system. The web view
# centers the camera on the root when the graph first opens, so (0, 0) appears in
# the middle of the graph window by default.
ROOT_NODE_X = 0
ROOT_NODE_Y = 0
NODE_WIDTH = 210
NODE_HEIGHT = 82
TREE_HORIZONTAL_GAP = 270
TREE_VERTICAL_GAP = 150
TREE_MARGIN_X = 60
TREE_MARGIN_Y = 50

# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
APP_TITLE = "HAI Graph Chat Prototype"
