from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from app.domain.graph import GraphNode


@dataclass(frozen=True)
class TreeLayoutConfig:
    node_width: int
    node_height: int
    horizontal_gap: int
    vertical_gap: int
    margin_x: int
    margin_y: int


class TreeLayoutService:
    """Exposes stored freeform node positions with shared UI dimensions."""

    def __init__(self, config: TreeLayoutConfig):
        self._config = config

    def layout(self, nodes: List[GraphNode]) -> Dict[str, dict]:
        return {
            node.id: {
                "x": node.position.x,
                "y": node.position.y,
                "width": self._config.node_width,
                "height": self._config.node_height,
            }
            for node in nodes
        }

    def settings(self) -> dict:
        return {
            "nodeWidth": self._config.node_width,
            "nodeHeight": self._config.node_height,
            "horizontalGap": self._config.horizontal_gap,
            "verticalGap": self._config.vertical_gap,
            "marginX": self._config.margin_x,
            "marginY": self._config.margin_y,
        }
