from __future__ import annotations

from typing import Mapping


def pick_localized_text(value: Mapping[str, str], locale: str, fallback: str = "") -> str:
    if value.get(locale):
        return value[locale]
    for key in ("ko", "en"):
        if value.get(key):
            return value[key]
    for text in value.values():
        if text:
            return text
    return fallback


def default_node_title(locale: str) -> str:
    return "새 대화" if locale == "ko" else "New chat"


def default_root_title(locale: str) -> str:
    return "시작 대화" if locale == "ko" else "Root chat"


def default_edge_phrase(locale: str) -> str:
    return "새 분기" if locale == "ko" else "New branch"


def default_graph_thread_title(locale: str, index: int) -> str:
    return f"그래프 스레드 {index}" if locale == "ko" else f"Graph thread {index}"
