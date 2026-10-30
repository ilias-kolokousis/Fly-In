#!/usr/bin/env python3

from map_class import Map, create_map, Connection
from parse_files import Hub
import sys
import heapq


class Drone:
    """Drone object holdinh its journey.
    """
    def __init__(self,
                 id: int,
                 path: tuple[list[str], int],
                 start: str) -> None:
        """Initiliaze a Drone object.

        Args:
            id (int): unique identifier
            path (tuple[list[str], int]): optimal path using
                                               Dijkstra's algorithm
            start (str): start_hub
        """
        self.path: list[str] = path[0]
        self.journey: dict[int, str] = {0: start}
        self.rounds_restricted: int = 0
        self.id: int = id
        self.remaining: int = path[1]


def schedule_drones(map: Map) -> list[Drone]:
    """Schedule drones to go through the map.

    Args:
        map (Map): Map object (Graph)

    Returns:
        list[Drone]: Drone objects.
    """
    start: str = [hub.name for hub in map.hubs.values()
                  if hub.is_start][0]
    goal: str = [hub.name for hub in map.hubs.values() if hub.is_end][0]
    drones: list[Drone] = [Drone(i, find_path(map, start), start)
                           for i in range(1, map.nb_drones + 1)]
    turn: int = 1
    while map.hubs[goal].drones != map.nb_drones:
        drones = sorted(drones, key=lambda x: x.remaining)
        for drone in drones:
            current: Hub = map.hubs[drone.journey[turn - 1]]

            path_wo_occ, cost_wo_occ = find_path(map, current.name, True)
            path_w_occ, cost_w_occ = find_path(map, current.name)

            if path_wo_occ[0] == goal:
                drone.journey[turn] = drone.journey[turn - 1]
                continue

            next_name = path_wo_occ[1]
            next_hub = map.hubs[next_name]
            link = map.connections[current.name + next_name]
            has_room = ((next_hub.is_end
                         or next_hub.drones < next_hub.max_drones)
                        and link.drones_passed < link.max_link_capacity)

            if has_room:
                drone.path = path_wo_occ
                drone.remaining = cost_wo_occ
            elif cost_w_occ < cost_wo_occ + 1:
                drone.path = path_w_occ
                drone.remaining = cost_w_occ
            else:
                drone.journey[turn] = current.name
                continue

            if current.zone == 'restricted':
                if drone.rounds_restricted > 0:
                    drone.rounds_restricted = 0
                else:
                    drone.journey[turn] = drone.journey[turn - 1]
                    drone.rounds_restricted += 1
                    continue

            drone.journey[turn] = drone.path[1]
            map.hubs[drone.path[1]].drones += 1
            map.hubs[current.name].drones -= 1

            conn: Connection = map.connections[drone.journey[turn - 1]
                                               + drone.journey[turn]]
            conn.drones_passed += 1

        for key in map.connections:
            map.connections[key].drones_passed = 0
        turn += 1
    return drones


def find_path(map: Map,
              start: str,
              ignore_occ: bool = False) -> tuple[list[str], int]:
    """Find optimal path using Dijkstra's algorithm.

    Args:
        map (Map): Map object (Graph)
        start (str): name of the hub starting the path
        ignore_occ (bool, optional): ignore occupying drones in hub.
                                     Defaults to False.

    Returns:
        tuple[list[str], int]: path, cost
    """
    goal: str = [hub.name for hub in map.hubs.values() if hub.is_end][0]
    dist: dict[str, tuple[int, int]] = {start: (0, 0)}
    heap: list[tuple[int, int, str]] = []
    heapq.heappush(heap, (0, 0, start))
    previous: dict[str, str] = {}
    visited: set[str] = set()

    while heap != []:
        current_cost, current_penalty, current_name = heapq.heappop(heap)
        if current_name in visited:
            continue
        if current_name == goal:
            break
        visited.add(current_name)
        current_hub: Hub = map.hubs[current_name]
        for neigh in current_hub.neighbors:
            zone: str = map.hubs[neigh].zone
            visiting_drones: int = map.hubs[neigh].drones
            connection: Connection = map.connections[current_name + neigh]
            max_link: int = (map.connections[current_name + neigh]
                             .max_link_capacity)
            max_drones: int = map.hubs[neigh].max_drones
            if zone == 'blocked' or neigh in visited:
                continue
            if (not ignore_occ
                and ((visiting_drones >= max_drones
                     or connection.drones_passed >= max_link)
                     and current_name == start)):
                continue
            new_cost: int = current_cost + (2 if zone == 'restricted'
                                            else 1)
            new_penalty: int = current_penalty + (0 if zone == 'priority'
                                                  else 1)
            new_key: tuple[int, int] = (new_cost, new_penalty)
            if new_key < dist.get(neigh, (sys.maxsize, sys.maxsize)):
                dist[neigh] = new_key
                previous[neigh] = current_name
                heapq.heappush(heap, (new_cost, new_penalty, neigh))

    path: list[str] = [goal]
    while path[-1] in previous:
        path.append(previous[path[-1]])
    path = path[::-1]
    return path, dist.get(goal, (sys.maxsize, 0))[0]


if __name__ == "__main__":
    map: Map = create_map()
    drones = schedule_drones(map)
    for i in drones:
        print(f'=== Drone {i.id} ===\n{i.journey}')
