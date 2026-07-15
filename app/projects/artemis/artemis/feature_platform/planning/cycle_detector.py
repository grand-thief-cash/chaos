from __future__ import annotations


def detect_cycle(edges: dict[int, set[int]]) -> list[int]:
    unseen, visiting, done = 0, 1, 2
    state: dict[int, int] = {}
    stack: list[int] = []
    positions: dict[int, int] = {}

    def visit(node: int) -> list[int]:
        state[node] = visiting
        positions[node] = len(stack)
        stack.append(node)
        for upstream in sorted(edges.get(node, set())):
            if state.get(upstream, unseen) == unseen:
                found = visit(upstream)
                if found:
                    return found
            elif state.get(upstream) == visiting:
                start = positions[upstream]
                return [*stack[start:], upstream]
        stack.pop()
        positions.pop(node, None)
        state[node] = done
        return []

    for node in sorted(edges):
        if state.get(node, unseen) == unseen:
            found = visit(node)
            if found:
                return found
    return []
