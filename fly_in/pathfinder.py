"""Shortest-path search over the drone network."""

import heapq
import sys

from .graph import Map

UNREACHABLE = sys.maxsize


def find_path(graph: Map, start: str,
              ignore_occupancy: bool = False) -> tuple[list[str], int]:
    """Find the cheapest path from ``start`` to the end hub (Dijkstra).

    Entering a hub costs 1 turn, or 2 for a restricted hub. Blocked hubs
    are never entered. Between paths of equal cost, the one crossing the
    most priority hubs wins.

    Args:
        graph: the drone network.
        start: name of the hub the path starts from.
        ignore_occupancy: if False, the first hop must go to a hub with
            room left, over a link that still has capacity this turn.

    Returns:
        The path as a list of hub names (``start`` first) and its cost in
        turns, or ``([], UNREACHABLE)`` if there is no path.
    """
    goal = graph.goal
    dist: dict[str, tuple[int, int]] = {start: (0, 0)}
    heap: list[tuple[int, int, str]] = [(0, 0, start)]
    previous: dict[str, str] = {}
    visited: set[str] = set()

    while heap:
        cost, penalty, name = heapq.heappop(heap)
        if name in visited:
            continue
        if name == goal:
            break
        visited.add(name)
        for neighbor_name in graph.hubs[name].neighbors:
            neighbor = graph.hubs[neighbor_name]
            if neighbor.zone == 'blocked' or neighbor_name in visited:
                continue
            if not ignore_occupancy and name == start:
                link = graph.connection(name, neighbor_name)
                if (neighbor.drones >= neighbor.max_drones
                        or link.drones_passed >= link.max_link_capacity):
                    continue
            key = (cost + (2 if neighbor.zone == 'restricted' else 1),
                   penalty + (0 if neighbor.zone == 'priority' else 1))
            if key < dist.get(neighbor_name, (UNREACHABLE, UNREACHABLE)):
                dist[neighbor_name] = key
                previous[neighbor_name] = name
                heapq.heappush(heap, (key[0], key[1], neighbor_name))

    if goal not in dist:
        return [], UNREACHABLE
    path = [goal]
    while path[-1] in previous:
        path.append(previous[path[-1]])
    path.reverse()
    return path, dist[goal][0]
