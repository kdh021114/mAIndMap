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
#          Deterministic local test doubles are injected through the LLM factory.
# False -> use OpenAI when OPENAI_API_KEY is available; otherwise optionally use
#          fallback mocks depending on USE_MOCK_LLM_WHEN_NO_API_KEY.
TEST_MODE = True

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
OPENAI_CHAT_MODEL = "gpt-5.5"

# Smaller models used only for graph labels/titles.
# They are deliberately separated from the chat model.
OPENAI_EDGE_MODEL = "gpt-5.4-nano"
OPENAI_TITLE_MODEL = "gpt-5.4-nano"

# Keep the prototype runnable even when .env is not configured.
# Set to False when you want the app to fail fast without an API key.
# This is ignored when TEST_MODE=True, because test mode always blocks LLM calls.
USE_MOCK_LLM_WHEN_NO_API_KEY = True

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
