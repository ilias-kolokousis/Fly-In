"""Parsing and validation of Fly-In map files.

A map file is a list of ``key: value`` lines, for example::

    nb_drones: 4
    start_hub: start 0 0 [color=green]
    hub: junction 1 0 [max_drones=2]
    end_hub: goal 2 0
    connection: start-junction [max_link_capacity=2]
    connection: junction-goal

See the README for the full format.
"""

from collections import deque
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

ZoneType = Literal['normal', 'blocked', 'restricted', 'priority']

HUB_KEYS = ('start_hub', 'end_hub', 'hub')
VALID_KEYS = ('nb_drones', 'connection') + HUB_KEYS
HUB_METADATA = frozenset({'zone', 'color', 'max_drones'})
CONNECTION_METADATA = frozenset({'max_link_capacity'})


class MapError(Exception):
    """Raised when a map file cannot be read or is invalid."""


class HubSpec(BaseModel):
    """A hub (graph node) as declared in the map file."""

    name: str = Field(min_length=1)
    x: int = Field(ge=0)
    y: int
    color: str | None = None
    zone: ZoneType = 'normal'
    max_drones: int = Field(default=1, ge=1)

    @field_validator('name')
    @classmethod
    def _no_dash_or_space(cls, name: str) -> str:
        """Reject names that would make connection syntax ambiguous."""
        if '-' in name or any(c.isspace() for c in name):
            raise ValueError('hub names cannot contain dashes or spaces')
        return name


class ConnectionSpec(BaseModel):
    """An undirected connection (graph edge) between two hubs."""

    name1: str = Field(min_length=1)
    name2: str = Field(min_length=1)
    max_link_capacity: int = Field(default=1, ge=1)


class MapSpec(BaseModel):
    """A fully validated map."""

    nb_drones: int = Field(ge=1)
    start_hub: HubSpec
    end_hub: HubSpec
    hubs: list[HubSpec] = Field(default_factory=list)
    connections: list[ConnectionSpec] = Field(min_length=1)

    def all_hubs(self) -> list[HubSpec]:
        """Return every hub, including the start and end hubs."""
        return [self.start_hub, *self.hubs, self.end_hub]


def parse_map_file(path: str | Path) -> MapSpec:
    """Read and validate a map file.

    Raises:
        MapError: if the file cannot be read or the map is invalid.
    """
    try:
        text = Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as e:
        raise MapError(f'cannot read "{path}": {e}') from e
    return parse_map(text)


def parse_map(text: str) -> MapSpec:
    """Parse and validate the contents of a map file.

    The whole file is case-insensitive and ``#`` starts a comment.

    Raises:
        MapError: if the map is invalid. Errors tied to a specific line
            are prefixed with its line number.
    """
    nb_drones: int | None = None
    start_hub: HubSpec | None = None
    end_hub: HubSpec | None = None
    hubs: list[HubSpec] = []
    connections: list[ConnectionSpec] = []

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split('#', 1)[0].strip().lower()
        if not line:
            continue
        try:
            key, values, metadata = _split_line(line)
            if key == 'nb_drones':
                if nb_drones is not None:
                    raise MapError('"nb_drones" is defined more than once')
                nb_drones = _parse_nb_drones(values, metadata)
            elif key == 'connection':
                connections.append(_parse_connection(values, metadata))
            else:
                hub = _parse_hub(values, metadata)
                if key == 'hub':
                    hubs.append(hub)
                elif key == 'start_hub':
                    if start_hub is not None:
                        raise MapError('only one start_hub can exist')
                    start_hub = hub
                else:
                    if end_hub is not None:
                        raise MapError('only one end_hub can exist')
                    end_hub = hub
        except ValidationError as e:
            raise MapError(f'line {lineno}: {_describe(e)}') from e
        except MapError as e:
            raise MapError(f'line {lineno}: {e}') from e

    for name, value in (('nb_drones', nb_drones), ('start_hub', start_hub),
                        ('end_hub', end_hub)):
        if value is None:
            raise MapError(f'mandatory key "{name}" is missing')
    if not connections:
        raise MapError('at least one connection is required')

    assert (nb_drones is not None and start_hub is not None
            and end_hub is not None)
    spec = MapSpec(nb_drones=nb_drones, start_hub=start_hub, end_hub=end_hub,
                   hubs=hubs, connections=connections)
    _check_unique_hub_names(spec)
    _check_connections(spec)
    _check_reachable(spec)
    return spec


def _describe(error: ValidationError) -> str:
    """Turn a pydantic ValidationError into a short, readable message."""
    return '; '.join(
        f'{".".join(str(loc) for loc in err["loc"])}: {err["msg"]}'
        if err['loc'] else err['msg']
        for err in error.errors()
    )


def _split_line(line: str) -> tuple[str, list[str], dict[str, str]]:
    """Split a line into its key, positional values and metadata."""
    key, sep, rest = line.partition(':')
    key = key.strip()
    if not sep:
        raise MapError(f'expected "key: value", got "{line}"')
    if key not in VALID_KEYS:
        raise MapError(f'"{key}" is not a valid key '
                       f'(expected one of: {", ".join(VALID_KEYS)})')

    rest = rest.strip()
    metadata: dict[str, str] = {}
    if '[' in rest or ']' in rest:
        if rest.count('[') != 1 or rest.count(']') != 1:
            raise MapError('metadata must be in a single pair of '
                           'square brackets')
        if not rest.endswith(']') or rest.index('[') > rest.index(']'):
            raise MapError('metadata must be enclosed in square brackets '
                           'at the end of the line')
        rest, _, metadata_text = rest.partition('[')
        metadata = _parse_metadata(metadata_text[:-1])
    return key, rest.split(), metadata


def _parse_metadata(text: str) -> dict[str, str]:
    """Parse ``key=value key=value`` pairs from inside square brackets."""
    metadata: dict[str, str] = {}
    for token in text.split():
        name, sep, value = token.partition('=')
        if not sep or not name or not value:
            raise MapError(f'invalid metadata "{token}", expected key=value')
        if name in metadata:
            raise MapError(f'duplicate metadata key "{name}"')
        metadata[name] = value
    return metadata


def _check_metadata(metadata: dict[str, str], allowed: frozenset[str],
                    entry: str) -> None:
    """Reject metadata keys that are not valid for this kind of entry."""
    for name in metadata:
        if name not in allowed:
            raise MapError(f'"{name}" is not valid metadata for {entry} '
                           f'(allowed: {", ".join(sorted(allowed))})')


def _parse_nb_drones(values: list[str], metadata: dict[str, str]) -> int:
    if len(values) != 1 or metadata:
        raise MapError('"nb_drones" takes exactly one integer')
    try:
        nb_drones = int(values[0])
    except ValueError:
        raise MapError(f'"nb_drones" must be an integer, '
                       f'got "{values[0]}"') from None
    if nb_drones < 1:
        raise MapError('"nb_drones" must be at least 1')
    return nb_drones


def _parse_hub(values: list[str], metadata: dict[str, str]) -> HubSpec:
    if len(values) != 3:
        raise MapError(f'expected "<name> <x> <y> [metadata]", got '
                       f'{len(values)} value(s) before the metadata')
    _check_metadata(metadata, HUB_METADATA, 'hubs')
    name, x, y = values
    return HubSpec.model_validate({'name': name, 'x': x, 'y': y, **metadata})


def _parse_connection(values: list[str],
                      metadata: dict[str, str]) -> ConnectionSpec:
    if len(values) != 1:
        raise MapError('expected "<hub1>-<hub2> [metadata]"')
    names = values[0].split('-')
    if len(names) != 2 or not all(names):
        raise MapError(f'invalid connection "{values[0]}", '
                       'expected "<hub1>-<hub2>"')
    if names[0] == names[1]:
        raise MapError(f'hub "{names[0]}" cannot connect to itself')
    _check_metadata(metadata, CONNECTION_METADATA, 'connections')
    return ConnectionSpec.model_validate(
        {'name1': names[0], 'name2': names[1], **metadata})


def _check_unique_hub_names(spec: MapSpec) -> None:
    seen: set[str] = set()
    for hub in spec.all_hubs():
        if hub.name in seen:
            raise MapError(f'duplicate hub name "{hub.name}"')
        seen.add(hub.name)


def _check_connections(spec: MapSpec) -> None:
    """Check connections reference known hubs and are not duplicated.

    ``a-b`` and ``b-a`` count as the same connection.
    """
    names = {hub.name for hub in spec.all_hubs()}
    seen: set[frozenset[str]] = set()
    for conn in spec.connections:
        for name in (conn.name1, conn.name2):
            if name not in names:
                raise MapError(f'connection "{conn.name1}-{conn.name2}" '
                               f'uses unknown hub "{name}"')
        pair = frozenset((conn.name1, conn.name2))
        if pair in seen:
            raise MapError(f'duplicate connection "{conn.name1}-{conn.name2}"')
        seen.add(pair)


def _check_reachable(spec: MapSpec) -> None:
    """Check the end hub can be reached without crossing blocked hubs."""
    blocked = {hub.name for hub in spec.all_hubs() if hub.zone == 'blocked'}
    neighbors: dict[str, list[str]] = {}
    for conn in spec.connections:
        neighbors.setdefault(conn.name1, []).append(conn.name2)
        neighbors.setdefault(conn.name2, []).append(conn.name1)

    start, goal = spec.start_hub.name, spec.end_hub.name
    seen = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        if current == goal:
            return
        for neighbor in neighbors.get(current, []):
            if neighbor not in seen and neighbor not in blocked:
                seen.add(neighbor)
                queue.append(neighbor)
    raise MapError(f'there is no path from "{start}" to "{goal}" '
                   'that avoids blocked hubs')
