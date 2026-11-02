_This project has been created as part of the 42 curriculum by ikolokou._

# Fly-In

Fly-In routes a fleet of drones through a network of hubs (a graph) from a
start hub to an end hub, using as few turns as possible while respecting
the capacity limits of hubs and connections. The resulting schedule is printed
turn by turn and replayed in an interactive pygame visualizer.

![Fly-In visualizer](docs/screenshot.png)

## Features

- **Map parser and validator** for a simple text format, with clear error messages that include line numbers.
- **Dijkstra pathfinding** that takes zone costs into account: blocked,
  restricted (slow) and priority (preferred) hubs.
- **Turn-based scheduler** that keeps every drone moving while never exceeding
  a hub's `max_drones` or a link's `max_link_capacity`, and stops with an error
  if the fleet can no longer make progress.
- **Interactive visualizer**: step through the turns, hover a hub to see its
  name, and see link capacity drawn as line thickness.

## Getting started

Requirements: Python ≥ 3.10 and [uv](https://docs.astral.sh/uv/).

```sh
make install                      # create .venv and install dependencies
make run                          # run maps/simple_fork.txt with the visualizer
make run MAP=maps/zones.txt       # run another map
make headless MAP=maps/zones.txt  # print the schedule only, no window
```

Or call the module directly:

```sh
uv run python -m fly_in <map file> [--no-gui]
```

Other targets: `make lint` (flake8 + `mypy --strict`), `make debug` (runs under
pdb) and `make clean`.

### Example

`maps/simple_fork.txt`:

```txt
# Easy Level 2: Simple fork with two paths
nb_drones: 4

start_hub: start 0 0 [color=green]
hub: junction 1 0 [color=yellow max_drones=2]
hub: path_a 2 1 [color=blue]
hub: path_b 2 -1 [color=green]
end_hub: goal 3 0 [color=red]

connection: start-junction [max_link_capacity=2]
connection: junction-path_a
connection: junction-path_b
connection: path_a-goal
connection: path_b-goal
```

```console
$ make headless
=====================================================
D1-junction D2-junction
D1-path_a D2-path_b D3-junction D4-junction
D1-goal D2-goal D3-path_a D4-path_b
D3-goal D4-goal
=====================================================
```

Each line is one turn and lists the drones that moved, as `D<id>-<hub>`. A
drone flying into a restricted hub spends a turn on the connection, shown as
`D<id>-<from>-<to>`, and lands on the following turn.

## Map file format

- **One entry per line**, written as `key: value`. The valid keys are
  `nb_drones`, `start_hub`, `end_hub`, `hub` and `connection`.
- **Case-insensitive**. `#` starts a comment, either on its own line or after an entry. Empty lines are ignored.
- **`nb_drones: <n>`**: mandatory and appears once. An integer ≥ 1.
- **`start_hub`**, **`end_hub`**: mandatory and appear exactly once each. They use the same syntax as `hub`.
- **`hub: <name> <x> <y> [metadata]`**: declares a hub.
  - `name` must be unique and cannot contain dashes (`-`) or spaces.
  - `x` is an integer ≥ 0. `y` is any integer.
- **`connection: <name1>-<name2> [metadata]`**: declares a bidirectional link.
  - At least one connection is required, and both hubs must exist.
  - `a-b` and `b-a` are the same connection and can only be declared once.
- **Metadata** is optional. It goes in a single pair of square brackets at the
  end of the line, written as space-separated `key=value` pairs (each key at most once).

| Metadata key        | Applies to  | Values                                        | Default  |
|---------------------|-------------|-----------------------------------------------|----------|
| `zone`              | hubs        | `normal`, `blocked`, `restricted`, `priority` | `normal` |
| `color`             | hubs        | any pygame color name, or `rainbow`           | none     |
| `max_drones`        | hubs        | integer ≥ 1                                   | `1`      |
| `max_link_capacity` | connections | integer ≥ 1                                   | `1`      |

- `blocked` hubs can never be entered.
- Entering a `restricted` hub takes 2 turns instead of 1.
- `priority` hubs are preferred over other paths of equal cost.
- `start_hub` and `end_hub` can hold the whole fleet, regardless of `max_drones`.
- There must be a path from `start_hub` to `end_hub` that avoids blocked hubs.

More examples are in [`maps/`](maps/): `zones.txt` uses every zone type and
`bottleneck.txt` pushes eight drones through a single-capacity hub.

## How it works

### Pathfinding

Each hub costs 1 turn to enter (2 if restricted). Paths are compared by
`(cost, number of non-priority hubs)`, so among equally fast routes the one
through the most priority hubs wins. I chose Dijkstra's algorithm over A\*: a
distance heuristic can easily lead towards a hub that looks close to the goal
but turns out to be a dead end.

### Scheduling

Every turn, drones are processed closest-to-the-goal first. For each drone:

1. Compute the shortest path to the goal, ignoring other drones.
2. If the next hub and link on that path have room, take that step.
3. Otherwise, if an equally short path through hubs with room exists, take that one instead.
4. Otherwise, wait one turn.

Link usage is reset at the end of every turn. If a full turn passes in which no
drone can move, the scheduler raises an error instead of looping forever.

This is a greedy, per-turn approach. A globally optimal schedule would plan
every drone's full route up front, for example with flow-based algorithms.

### Visualizer

- Use the on-screen arrows (bottom left) or the ←/→ keys to step through turns. ESC or the window's close button quits.
- Hover a hub to see its name.
- When more than two drones share a spot, one drone is drawn with a counter (e.g. `x4`).
- Thicker connections have a higher `max_link_capacity`.
- A drone entering a restricted hub is drawn on the connection for one turn.

## Project structure

```
Fly-In/
├── fly_in/
│   ├── __main__.py     # command-line entry point
│   ├── parser.py       # map file parsing and validation
│   ├── graph.py        # runtime graph: hubs, connections, occupancy
│   ├── pathfinder.py   # Dijkstra shortest path
│   ├── scheduler.py    # turn-by-turn drone scheduling and output
│   ├── visualizer.py   # pygame visualizer
│   └── assets/         # sprites and background
├── maps/               # example maps
├── docs/               # README images
├── Makefile
└── pyproject.toml
```

## Resources

- [Dijkstra's algorithm](https://www.geeksforgeeks.org/dsa/dijkstras-shortest-path-algorithm-greedy-algo-7/)
- [pygame-ce documentation](https://pyga.me/docs/)

AI was used as a guide: it asked investigative questions to help me get unblocked
without handing me the answer. It also helped me get started with pygame, which
was completely new to me.
