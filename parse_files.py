#!/usr/bin/env python3

import sys
from colorist import Color
from pydantic import Field, BaseModel, ValidationError, field_validator
from typing import Literal, List, cast
import re


ZoneType = Literal['normal', 'blocked', 'restricted', 'priority']
ArgsDict = dict[str, str | dict[str, str]]


class Hub(BaseModel):
    """Hub class (zones in subject or nodes in graph terminology)

    Args:
        BaseModel: inherits from pydantic's BaseModel
                    for validation

    Raises:
        ValueError: Instead of ValidationError, because it's
                    clearer to have a custom message for RegEx
    """
    name: str = Field(min_length=1)
    x: int = Field(ge=0)
    y: int
    color: str | None = Field(default=None)
    zone: ZoneType = "normal"
    max_drones: int = Field(default=1, ge=1)
    drones: int = 0
    neighbors: list = []
    is_start: bool = False
    is_end: bool = False
    viz_x: int = 0
    viz_y: int = 0

    @field_validator('name')
    @classmethod
    def _no_dash_or_space(cls, val_name: str) -> str:
        """Validates that the name doesn't include spaces or dashes.

        Args:
            val_name (str): possible hub name

        Raises:
            ValueError: if name includes spaces or dashes

        Returns:
            str: name if no errors exist
        """
        if not val_name or '-' in val_name or any(c.isspace()
                                                  for c in val_name):
            raise ValueError('zone names cannot be empty ' +
                             'or contain dashes or spaces')
        return val_name


class Connection(BaseModel):
    """Connection class for validation.

    Args:
        BaseModel: inherits from pydantic's BaseModel
                    for validation
    """
    name1: str = Field(min_length=1)
    name2: str = Field(min_length=1)
    max_link_capacity: int = Field(default=1, ge=1)


class MapValidation(BaseModel):
    """MapValidation class for validation

    Args:
        BaseModel: inherits from pydantic's BaseModel
                    for validation
    """
    nb_drones: int = Field(ge=1)
    start_hub: Hub
    end_hub: Hub
    hubs: List[Hub] = Field(default_factory=list)
    connections: List[Connection] = Field(min_length=1)
    hub_connections: dict[str, Hub] = Field(default_factory=dict)


def _get_section(args: ArgsDict, key: str) -> dict[str, str]:
    """Return args[key] narrowed to a dict (hub/connection entries).

    Raises:
        KeyError: if key is missing.
        ValueError: if the entry is a plain value instead of a section.
    """
    value = args[key]
    if not isinstance(value, dict):
        raise ValueError(f'"{key}" must define a name and coordinates.')
    return value


def _get_value(args: ArgsDict, key: str) -> str:
    """Return args[key] narrowed to a str (e.g. nb_drones).

    Raises:
        KeyError: if key is missing.
        ValueError: if the entry is a section instead of a plain value.
    """
    value = args[key]
    if not isinstance(value, str):
        raise ValueError(f'"{key}" must be a single value.')
    return value


def _build_hub(data: dict[str, str],
               is_start: bool = False,
               is_end: bool = False) -> Hub:
    """Build a Hub from a parsed hub section."""
    return Hub(
        name=data['name'],
        x=int(data['x']),
        y=int(data['y']),
        is_start=is_start,
        is_end=is_end,
        color=data.get('color'),
        # cast only satisfies mypy; pydantic still validates the value
        zone=cast(ZoneType, data.get('zone', 'normal')),
        max_drones=int(data.get('max_drones', '1'))
    )


def validate(data: str) -> None:
    """Validate the txt file.

    Args:
        data (str): data imported from the txt file

    Raises:
        ValueError: if ':' is missing
        ValueError: if key is invalid
        ValueError: if metadata key is invalid
        ValueError: if max_link_capacity
                    is included in hub metadata
        ValueError: if any other than max_link_capacity
                    is included in the connections metadata
    """
    acceptable_keys: List[str] = [
        'nb_drones',
        'start_hub',
        'end_hub',
        'hub',
        'connection'
    ]
    metadata: List[str] = [
        'color',
        'zone',
        'max_drones',
        'max_link_capacity'
    ]
    for line in data.split('\n'):
        if line.startswith('#') or line == '' or line == ' ':
            continue
        for key in acceptable_keys:
            if key in line and ':' not in line:
                raise ValueError(f'Error in {line}. ' +
                                 'Each key must be followed with ":".')
        if line.split(':')[0] not in acceptable_keys:
            raise ValueError(f'"{line.split(":")[0]}" ' +
                             'is not an acceptable key')
        if line.find('[') != -1:
            brackets: List[str] = (line[line.find('[') + 1:line.find(']')]
                                   .split())
            for i in range(len(brackets)):
                if brackets[i].split('=')[0] not in metadata:
                    raise ValueError(f'Error in "{line}." ' +
                                     'Metadata key doesn\'t exist ' +
                                     'or forgot an "=" or key name ' +
                                     'somewhere.')
            if 'hub' in line and 'max_link_capacity' in brackets:
                raise ValueError(f'Error in "{line}." ' +
                                 '"max_link_capacity" is a valid' +
                                 'argument only for connections.')
            if ('connection' in line
               and 'max_link_capacity' != brackets[0].split('=')[0]):
                raise ValueError(f'Error in "{line}." ' +
                                 '"max_link_capacity" is the only valid ' +
                                 'argument for connections.')


def add_optional_args(line: str,
                      key: str,
                      args: ArgsDict) -> ArgsDict:
    """Add optional metadata while parsing.

    Args:
        line (str): Line from the txt file.
        key (str): Metadata key to be added in a dictionary.
        args (dict[str, str  |  dict[str, str]]): Dictionary holding
                                all args drawn from the line.

    Raises:
        ValueError: if metadata are not enclosed in sqaure brackets.
        ValueError: if there are more than one square brackets.
        ValueError: if anything other than comment is found
                    after square brackets.
        ValueError: if metadata key is found more than once.
        ValueError: if key exists but no value.

    Returns:
        dict[str, str | dict[str, str]]: args parameter filled with meatdata
    """
    metadata: List[str] = ['zone', 'color', 'max_drones', 'max_link_capacity']
    if '[' in line:
        if ']' not in line:
            raise ValueError(f'Error in line "{line}": ' +
                             'Line metadata must be enclosed in ' +
                             'square brackets ([])')
        if line.count('[') > 1 or line.count(']') > 1:
            raise ValueError(f'Error in line "{line}": ' +
                             'There can be only a single set of ' +
                             'square brackets per line.')
        if not line.strip().endswith(']'):
            raise ValueError(f'Error in line "{line}": ' +
                             'Extra material found after metadata.')
        section = args[key]
        if not isinstance(section, dict):
            raise ValueError(f'Error in line "{line}": ' +
                             'Metadata is only allowed for hubs ' +
                             'and connections.')
        line = line[line.index('['):]
        for meta in metadata:
            if line.count(meta) > 1:
                raise ValueError(f'Error in line "{line}": ' +
                                 f'Duplicate metadata key found ({meta}).')
            if meta in line:
                section[meta] = (line[line.index(meta) + len(meta):]
                                 .split()[0]
                                 .strip('= ]'))
                if section[meta] == '':
                    raise ValueError(f'Error in line "{line}": ' +
                                     f'Value is missing for metadata "{meta}"')
    return args


def check_duplicate_names(args: ArgsDict) -> None:
    """Check for duplicate names in hubs.

    Args:
        args (dict[str, str  |  dict[str, str]]): dictionary holding
                                all values drawn from the txt file.

    Raises:
        ValueError: if there is a duplicate hub name.
    """
    hubs: List[str] = [_get_section(args, hub)['name']
                       for hub in args if 'hub' in hub]

    for hub in hubs:
        if hubs.count(hub) >= 2:
            raise ValueError(f'Duplicate hub name: {hub}')


def parse_file(data: str) -> ArgsDict:
    """Parse file, validating at the same time.

    Args:
        data (str): lines from the txt file.

    Raises:
        ValueError: if there is more than one start_hub keys.
        ValueError: if there is more than one end_hub keys.
        ValueError: if there are not enough arguments in line.
        ValueError: if there are too manyarguments in line.

    Returns:
        dict[str, str | dict[str, str]]: data converted into a dictionary
    """
    args: ArgsDict = {}
    suffix: int = 0
    if len(re.findall('start_hub[ ]*:', data)) > 1:
        raise ValueError('Only 1 start_hub can exist.')
    if len(re.findall('end_hub[ ]*:', data)) > 1:
        raise ValueError('Only 1 end_hub can exist.')
    for line in data.split('\n'):
        line = line.lower()
        if line.startswith('#'):
            continue
        if '#' in line:
            line = line[:line.find('#')]
        items: List[str] = line.split()
        if line == '':
            continue
        if items[0].startswith('#'):
            continue
        if items[0].endswith(':'):
            key = items[0].strip(' :')
            if key in ('hub', 'connection'):
                suffix += 1
                key = key+str(suffix)
                args[key] = ''
            else:
                args[key] = ''
        if 'hub' in key:
            if len(items) < 4:
                raise ValueError(f'Not enough arguments in "{line}"')
            if len(line[:line.find('[')].split()) > 4:
                raise ValueError(f'Too many arguments in "{line}". ' +
                                 "Maybe some metadata is outside " +
                                 "of square brackets?")
            args[key] = {
                'name': items[1],
                'x': items[2],
                'y': items[3]
            }
        elif 'connection' in key:
            if len(items) < 2:
                raise ValueError(f'Not enough arguments in "{line}"')
            if len(line[:line.find('[')].split()) > 2:
                raise ValueError(f'Too many arguments in "{line}". ' +
                                 "Maybe some metadata is outside " +
                                 "of square brackets?")
            args[key] = {
                'name1': items[1].split('-')[0],
                'name2': items[1].split('-')[1]
            }
        else:
            if len(items) < 2:
                raise ValueError(f'Not enough arguments in "{line}"')
            if len(line.split()) > 2:
                raise ValueError(f'Too many arguments in "{line}"')
            args[key] = items[1]
        args = add_optional_args(line, key, args)
    check_duplicate_names(args)
    return args


def init_map(args: ArgsDict) -> MapValidation:
    """Initiliaze a MapValidation object.

    Args:
        args (dict[str, str  |  dict[str, str]]): dictionary holding
                                                  all arguments.

    Returns:
        MapValidation: Map (Graph) validated.
    """
    hubs = [i for i in list(args.keys()) if 'hub' in i
            and 'start' not in i and 'end' not in i]
    connections = [i for i in list(args.keys()) if 'connection' in i]
    map: MapValidation = MapValidation(
        nb_drones=int(_get_value(args, 'nb_drones')),
        start_hub=_build_hub(_get_section(args, 'start_hub'), is_start=True),
        end_hub=_build_hub(_get_section(args, 'end_hub'), is_end=True),
        hubs=[_build_hub(_get_section(args, hub)) for hub in hubs],
        connections=[Connection(
            name1=conn['name1'],
            name2=conn['name2'],
            max_link_capacity=int(conn.get('max_link_capacity', '1'))
        ) for conn in (_get_section(args, c) for c in connections)]
    )
    for hub in map.hubs:
        map.hub_connections[hub.name] = hub
    map.hub_connections[map.start_hub.name] = map.start_hub
    map.hub_connections[map.end_hub.name] = map.end_hub
    return map


def check_name_existence(map: MapValidation) -> None:
    """Check if the names in connections exist as hubs.

    Args:
        map (MapValidation): Map object holding all hubs and connections

    Raises:
        ValueError: if name doesn't exist in hubs.
    """
    names: list[str] = [hub.name for hub in map.hubs]
    names.extend([map.start_hub.name, map.end_hub.name])
    for conn in map.connections:
        if conn.name1 not in names:
            raise ValueError(f'"{conn.name1}" exists in connections, but ' +
                             'not in hubs.')
        if conn.name2 not in names:
            raise ValueError(f'"{conn.name2}" exists in connections, but ' +
                             'not in hubs.')


def check_duplicate_connections(map: MapValidation) -> None:
    """Check if there are duplicate connections
       (name1-name2 and name2-name1 is also duplicate).

    Args:
        map (MapValidation): Map object holding all hubs and connections.

    Raises:
        ValueError: if duplicate connection is found.
    """
    conns: list[str] = [f'{conn.name1}-{conn.name2}'
                        for conn in map.connections]
    conns.extend([f'{conn.name2}-{conn.name1}' for conn in map.connections])
    for conn in conns:
        if conns.count(conn) > 1:
            raise ValueError(f'Duplicate connection found in "{conn}"')


def parse_main() -> MapValidation:
    """Parse the file and handle gracefully any errors while parsing.

    Returns:
        MapValidation: Map object holding all hubs and connections.
    """
    if len(sys.argv) != 2:
        print("Only 1 argument is allowed.", file=sys.stderr)
        exit(1)
    file_path: str = sys.argv[1]
    try:
        with open(file_path) as f:
            data: str = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"{Color.RED}While opening the file an error occured:{Color.OFF}"
              f"\n{e}",
              file=sys.stderr)
        exit(1)

    try:
        validate(data)
        args = parse_file(data)
        map: MapValidation = init_map(args)
        check_name_existence(map)
        check_duplicate_connections(map)
        return map
    except (ValueError, ValidationError, KeyError) as e:
        if e.__class__.__name__ == 'KeyError':
            print(f'{Color.RED}There is an exception caught:{Color.OFF}',
                  f'Mandatory key is missing: {e}',
                  file=sys.stderr)
        else:
            print(f'{Color.RED}There is an exception caught:{Color.OFF} {e}',
                  file=sys.stderr)
        exit(1)


def check_connections() -> None:
    """Check that start and goal connect. It's using the Dijkstra's
       algorithm from later on.

    Raises:
        ValueError: if start and finish do not connect.
    """
    from map_class import Map, create_map
    from pathfinder import find_path

    map: Map = create_map()
    start: str = [hub.name for hub in map.hubs.values()
                  if hub.is_start][0]
    goal: str = [hub.name for hub in map.hubs.values() if hub.is_end][0]
    try:
        if find_path(map, start)[0] == [goal]:
            raise ValueError('Start and Goal do not connect.')
    except ValueError as e:
        print(f'{Color.RED}There is an exception caught:{Color.OFF} {e}',
              file=sys.stderr)
        exit(1)


if __name__ == "__main__":
    map: MapValidation = parse_main()
    check_connections()
    print(map.model_dump_json(indent=2))
