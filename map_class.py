#!/usr/bin/env python3

from parse_files import parse_main, MapValidation, Hub
from parse_files import Connection as ConnectionValidation
import sys


class Connection():
    """Connection class connecting two hubs.
    """
    def __init__(self,
                 hub1: Hub,
                 hub2: Hub,
                 max_link_capacity: int) -> None:
        """Initialize Connection.

        Args:
            hub1 (Hub): one of the hubs
            hub2 (Hub): the second hub
            max_link_capacity (int): how many drones can
                                     traverse the conenction at the same time.
        """
        self.hub1: Hub = hub1
        self.hub2: Hub = hub2
        self.max_link_capacity: int = max_link_capacity
        self.drones_passed: int = 0

    def __str__(self) -> str:
        """Convert the connection to string object for testing.

        Returns:
            str: Connection object as a string
        """
        string: str = '\n'.join((f'hub1:\t{self.hub1}',
                                 f'hub2:\t{self.hub2}',
                                 f'max_link_capacity:\t'
                                 f'{self.max_link_capacity}'))
        return string


class Map():
    """Map object used for fiding shortest path and visualization.
    """
    def __init__(self,
                 nb_drones: int,
                 hubs: list[Hub],
                 connections: list[ConnectionValidation],
                 hub_connections: dict[str, Hub]) -> None:
        """Initialize a Map object.

        Args:
            nb_drones (int): number of drones in Map
            hubs (list[Hub]): Hubs in Map
            connections (list[ConnectionValidation]): Connections
                                                   connecting the Hubs
            hub_connections (dict[str, Hub]): dictionary connecting one Hub
                                              with another.
        """
        self.nb_drones: int = nb_drones
        self.hubs: dict[str, Hub] = {hub.name: hub for hub in hubs}
        self.connections: dict[str, Connection] = {
            connection.name1 + connection.name2: Connection(
                hub_connections[connection.name1],
                hub_connections[connection.name2],
                connection.max_link_capacity) for connection in connections}
        for connection in connections:
            self.connections[connection.name2 + connection.name1] = Connection(
                hub_connections[connection.name1],
                hub_connections[connection.name2],
                connection.max_link_capacity)
        self.min_y: int = min(hub.y for hub in self.hubs.values())
        for hub in self.hubs.values():
            for conn in list(self.connections.values()):
                if conn.hub1.name == hub.name:
                    hub.neighbors.append(conn.hub2.name)
                if conn.hub2.name == hub.name:
                    hub.neighbors.append(conn.hub1.name)
            hub.y -= self.min_y
        self.max_x: int = max(hub.x for hub in self.hubs.values())
        self.max_y: int = max(hub.y for hub in self.hubs.values())

    def show_map(self) -> None:
        """Print Map object for testing.
        """
        print(f'nb_drones:\t{self.nb_drones}',
              f'hubs:\t{self.hubs}',
              f'connections:\t{str(self.connections)}',
              f'min_y:\t{self.min_y}',
              f'max_y:\t{self.max_y}',
              f'max_x:\t{self.max_x}',
              sep='\n')


def create_map() -> Map:
    """Create a Map object.

    Returns:
        Map: Map object
    """
    validated_map: MapValidation = parse_main()
    validated_map.start_hub.max_drones = sys.maxsize - validated_map.nb_drones
    validated_map.end_hub.max_drones = sys.maxsize - validated_map.nb_drones
    validated_map.hubs.extend([validated_map.start_hub,
                               validated_map.end_hub])
    map: Map = Map(validated_map.nb_drones,
                   validated_map.hubs,
                   validated_map.connections,
                   validated_map.hub_connections)
    return map


if __name__ == "__main__":
    map: Map = create_map()
    map.show_map()
