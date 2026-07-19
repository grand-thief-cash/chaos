from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DependencyGraph:
    """Directed graph where a node points to its upstream dependencies."""

    edges: dict[int, set[int]] = field(default_factory=dict)

    def add_node(self, node_id: int) -> None:
        self.edges.setdefault(node_id, set())

    def add_dependency(self, node_id: int, upstream_id: int) -> None:
        self.add_node(node_id)
        self.add_node(upstream_id)
        self.edges[node_id].add(upstream_id)
