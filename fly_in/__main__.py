"""Command-line entry point: ``python -m fly_in <map file>``."""

import argparse
import os
import sys
from pathlib import Path

from colorist import Color

from .graph import Map
from .parser import MapError, parse_map_file
from .scheduler import SchedulingError, format_turns, schedule_drones


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='fly_in',
        description='Route a fleet of drones from the start hub to the end '
                    'hub of a map, then replay the schedule.')
    parser.add_argument('map_file', type=Path, help='path to a map file')
    parser.add_argument('--no-gui', action='store_true',
                        help='only print the turn-by-turn moves')
    args = parser.parse_args(argv)

    try:
        graph = Map(parse_map_file(args.map_file))
        drones = schedule_drones(graph)
    except (MapError, SchedulingError) as e:
        print(f'{Color.RED}Error:{Color.OFF} {e}', file=sys.stderr)
        return 1

    print(format_turns(graph, drones))
    if not args.no_gui:
        os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
        from .visualizer import run_visualizer
        run_visualizer(graph, drones)
    return 0


if __name__ == '__main__':
    sys.exit(main())
