from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Literal
from uuid import uuid4

Locale = Literal["ko", "en"]
LocalizedText = Dict[str, str]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def dataclass_to_dict(value: Any) -> dict:
    if not is_dataclass(value):
        raise TypeError(f"Expected dataclass, got {type(value)!r}")
    return asdict(value)
