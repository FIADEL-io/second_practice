from __future__ import annotations

from collections.abc import Callable

ACTIVE = "active"
DONE = "done"

Neighbors = Callable[[str], list[str]]


class GraphError(Exception):
    pass


class Graph:

    def __init__(
        self,
        adjacency: dict[str, tuple[str, ...]],
        order: tuple[str, ...],
        cycles: tuple[tuple[str, ...], ...],
    ) -> None:
        self.adjacency = adjacency
        self.order = order
        self.cycles = cycles


def build_graph(root: str, neighbors: Neighbors, skip: str) -> Graph:
    if _hidden(root, skip):
        raise GraphError("корневой пакет отброшен фильтром")
    adjacency: dict[str, tuple[str, ...]] = {}
    order: list[str] = []
    discovered = {root}
    _expand([root], neighbors, skip, adjacency, order, discovered)
    cycles = _cycles(adjacency)
    return Graph(adjacency, tuple(order), cycles)


def format_graph(graph: Graph) -> str:
    lines = ["граф зависимостей:"]
    for node in graph.order:
        deps = ", ".join(graph.adjacency[node])
        if deps == "":
            lines.append(f"{node} ->")
        else:
            lines.append(f"{node} -> {deps}")
    if not graph.cycles:
        lines.append("циклы: нет")
        return "\n".join(lines)
    for cycle in graph.cycles:
        lines.append("цикл: " + " -> ".join(cycle))
    return "\n".join(lines)


def _expand(
    frontier: list[str],
    neighbors: Neighbors,
    skip: str,
    adjacency: dict[str, tuple[str, ...]],
    order: list[str],
    discovered: set[str],
) -> None:
    if not frontier:
        return
    nxt: list[str] = []
    for node in frontier:
        deps = _visible(neighbors(node), skip)
        adjacency[node] = tuple(deps)
        order.append(node)
        for dep in deps:
            if dep in discovered:
                continue
            discovered.add(dep)
            nxt.append(dep)
    _expand(nxt, neighbors, skip, adjacency, order, discovered)


def _visible(names: list[str], skip: str) -> list[str]:
    visible: list[str] = []
    for name in names:
        if _hidden(name, skip):
            continue
        if name in visible:
            continue
        visible.append(name)
    return visible


def _hidden(name: str, skip: str) -> bool:
    return skip != "" and skip in name


def _cycles(
    adjacency: dict[str, tuple[str, ...]],
) -> tuple[tuple[str, ...], ...]:
    state: dict[str, str] = {}
    found: list[tuple[str, ...]] = []
    path: list[str] = []
    for node in adjacency:
        if node not in state:
            _visit(node, adjacency, state, path, found)
    return tuple(found)


def _visit(
    node: str,
    adjacency: dict[str, tuple[str, ...]],
    state: dict[str, str],
    path: list[str],
    found: list[tuple[str, ...]],
) -> None:
    state[node] = ACTIVE
    path.append(node)
    for dep in adjacency.get(node, ()):
        mark = state.get(dep)
        if mark == ACTIVE:
            start = path.index(dep)
            found.append(tuple(path[start:] + [dep]))
        elif mark != DONE and dep in adjacency:
            _visit(dep, adjacency, state, path, found)
    path.pop()
    state[node] = DONE
