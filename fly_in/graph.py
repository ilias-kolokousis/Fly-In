"""Runtime graph used by the pathfinder, scheduler and visualizer."""

from dataclasses import dataclass, field

from .parser import HubSpec, MapSpec, ZoneType


@dataclass
class Hub:
    """A node of the graph, together with its current occupancy."""

    name: str
    x: int
    y: int
    zone: ZoneType
    max_drones: int
    color: str | None = None
    is_start: bool = False
    is_end: bool = False
    drones: int = 0
    neighbors: list[str] = field(default_factory=list)

    @classmethod
    def from_spec(cls, spec: HubSpec, is_start: bool = False,
                  is_end: bool = False) -> 'Hub':
        return cls(name=spec.name, x=spec.x, y=spec.y, zone=spec.zone,
                   max_drones=spec.max_drones, color=spec.color,
                   is_start=is_start, is_end=is_end)


@dataclass
class Connection:
    """An undirected edge between two hubs.

    ``drones_passed`` counts the drones that used the link this turn, in
    either direction, and is reset at the end of every turn.
    """

    hub1: Hub
    hub2: Hub
    max_link_capacity: int
    drones_passed: int = 0


class Map:
    """The drone network: hubs, connections and their current state."""

    def __init__(self, spec: MapSpec) -> None:
        self.nb_drones: int = spec.nb_drones
        self.start: str = spec.start_hub.name
        self.goal: str = spec.end_hub.name

        self.hubs: dict[str, Hub] = {}
        for hub_spec in spec.all_hubs():
            self.hubs[hub_spec.name] = Hub.from_spec(
                hub_spec,
                is_start=hub_spec.name == self.start,
                is_end=hub_spec.name == self.goal)

        # Every drone starts on the start hub and ends on the end hub, so
        # those two must be able to hold the whole fleet.
        for name in (self.start, self.goal):
            self.hubs[name].max_drones = self.nb_drones
        self.hubs[self.start].drones = self.nb_drones

        self.links: list[Connection] = []
        self._connections: dict[tuple[str, str], Connection] = {}
        for conn_spec in spec.connections:
            a, b = self.hubs[conn_spec.name1], self.hubs[conn_spec.name2]
            link = Connection(a, b, conn_spec.max_link_capacity)
            self.links.append(link)
            self._connections[(a.name, b.name)] = link
            self._connections[(b.name, a.name)] = link
            a.neighbors.append(b.name)
            b.neighbors.append(a.name)

        # Shift y so the topmost hub sits on row 0 (x is already >= 0).
        min_y = min(hub.y for hub in self.hubs.values())
        for hub in self.hubs.values():
            hub.y -= min_y
        self.max_x: int = max(hub.x for hub in self.hubs.values())
        self.max_y: int = max(hub.y for hub in self.hubs.values())

    def connection(self, a: str, b: str) -> Connection:
        """Return the connection between hubs ``a`` and ``b``."""
        return self._connections[(a, b)]

    def reset_link_usage(self) -> None:
        """Forget which links were used during the current turn."""
        for link in self.links:
            link.drones_passed = 0
