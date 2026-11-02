"""Turn-by-turn scheduling of the drone fleet."""

from dataclasses import dataclass, field

from .graph import Map
from .pathfinder import find_path


class SchedulingError(Exception):
    """Raised when the drones can no longer make progress."""


@dataclass
class Drone:
    """A drone and the hub it occupies at every turn."""

    id: int
    path: list[str]
    remaining: int
    journey: list[str] = field(default_factory=list)
    rounds_restricted: int = 0

    @property
    def position(self) -> str:
        return self.journey[-1]


def schedule_drones(graph: Map) -> list[Drone]:
    """Move every drone from the start hub to the end hub.

    Each turn, drones are handled in order of their remaining distance
    (closest first). A drone follows its shortest path if the next hub
    and link have room; otherwise it takes an equally short detour if one
    exists, or waits. Entering a restricted hub takes two turns.

    Returns:
        The drones, sorted by id. Every journey has the same length (one
        entry per turn, starting with turn 0).

    Raises:
        SchedulingError: if a turn passes in which no drone can move.
    """
    path, cost = find_path(graph, graph.start)
    drones = [Drone(i, list(path), cost, [graph.start])
              for i in range(1, graph.nb_drones + 1)]
    goal = graph.hubs[graph.goal]

    turn = 0
    while goal.drones < graph.nb_drones:
        turn += 1
        # Stable sort: drones with equal distance keep last turn's order.
        drones.sort(key=lambda d: d.remaining)
        progressed = False
        for drone in drones:
            progressed |= _advance(graph, drone)
        graph.reset_link_usage()
        if not progressed:
            # Nothing changed, so every following turn would be identical.
            raise SchedulingError(f'drones are stuck at turn {turn}: '
                                  'no drone can move')
    drones.sort(key=lambda d: d.id)
    return drones


def _advance(graph: Map, drone: Drone) -> bool:
    """Play one turn for ``drone``. Returns True if its state changed."""
    current = graph.hubs[drone.position]
    if current.is_end:
        drone.journey.append(current.name)
        return False

    free_path, free_cost = find_path(graph, current.name,
                                     ignore_occupancy=True)
    busy_path, busy_cost = find_path(graph, current.name)
    if len(free_path) < 2:
        drone.journey.append(current.name)
        return False

    next_hub = graph.hubs[free_path[1]]
    link = graph.connection(current.name, next_hub.name)
    has_room = ((next_hub.is_end or next_hub.drones < next_hub.max_drones)
                and link.drones_passed < link.max_link_capacity)
    if has_room:
        drone.path, drone.remaining = free_path, free_cost
    elif busy_cost <= free_cost:
        drone.path, drone.remaining = busy_path, busy_cost
    else:
        drone.journey.append(current.name)
        return False

    if current.zone == 'restricted' and drone.rounds_restricted == 0:
        # First turn after entering a restricted hub: finish the crossing.
        drone.rounds_restricted = 1
        drone.journey.append(current.name)
        return True
    drone.rounds_restricted = 0

    next_name = drone.path[1]
    drone.journey.append(next_name)
    graph.hubs[next_name].drones += 1
    current.drones -= 1
    graph.connection(current.name, next_name).drones_passed += 1
    return True


def format_turns(graph: Map, drones: list[Drone]) -> str:
    """Render the schedule as one line of moves per turn.

    A move is written ``D<id>-<hub>``. A drone flying into a restricted
    hub spends one turn on the connection (``D<id>-<from>-<to>``) and
    lands on the next turn. Turns in which nothing moves are omitted.
    """
    separator = '=' * 53
    lines = [separator]
    for turn in range(1, len(drones[0].journey)):
        moves: list[str] = []
        for drone in drones:
            prev, cur = drone.journey[turn - 1], drone.journey[turn]
            restricted = graph.hubs[cur].zone == 'restricted'
            if prev != cur:
                where = f'{prev}-{cur}' if restricted else cur
                moves.append(f'D{drone.id}-{where}')
            elif (restricted and turn >= 2
                  and drone.journey[turn - 2] != prev):
                moves.append(f'D{drone.id}-{cur}')
        if moves:
            lines.append(' '.join(moves))
    lines.append(separator)
    return '\n'.join(lines)
