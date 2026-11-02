"""Interactive pygame visualization of a drone schedule."""

import math
import sys
from pathlib import Path
from types import TracebackType
from typing import Final

import pygame

from .graph import Map
from .scheduler import Drone

ASSETS_DIR: Final = Path(__file__).resolve().parent / 'assets'

Color = tuple[int, int, int]


class Visualizer:
    """Window that replays the schedule turn by turn.

    Controls: left/right arrow keys or the on-screen arrows step through
    the turns, hovering a hub shows its name, ESC or closing the window
    quits.
    """

    WHITE: Final[Color] = (255, 255, 255)
    LIGHT_GRAY: Final[Color] = (170, 170, 170)
    DARK_GRAY: Final[Color] = (100, 100, 100)
    LABEL_BG: Final[Color] = (60, 60, 60)
    FLASH_MS: Final = 150
    WIDTH: Final = 1000
    HEIGHT: Final = 700
    FPS: Final = 60

    def __init__(self, graph: Map, drones: list[Drone]) -> None:
        pygame.init()
        pygame.display.set_caption('Fly-In')
        self.graph = graph
        self.drones = drones
        self.last_turn = len(drones[0].journey) - 1
        self.turn = 0
        self.running = True
        self.invalid_colors: list[str] = []

        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        self.clock = pygame.time.Clock()
        self.left_pressed_at = -self.FLASH_MS
        self.right_pressed_at = -self.FLASH_MS
        self.left_rect = pygame.Rect(10, self.HEIGHT - 50, 40, 40)
        self.right_rect = pygame.Rect(60, self.HEIGHT - 50, 40, 40)

        self.drone_sprite = pygame.transform.scale(
            self._load('drone.png'), (80, 40))
        self.shadow = pygame.Surface((50, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(self.shadow, (0, 0, 0, 90),
                            self.shadow.get_rect())

        spacing_x = self.WIDTH / (graph.max_x + 1)
        spacing_y = self.HEIGHT / (graph.max_y + 1)
        self.centres: dict[str, tuple[int, int]] = {
            name: (round(spacing_x * (hub.x + 0.5)),
                   round(spacing_y * (hub.y + 0.5)))
            for name, hub in graph.hubs.items()
        }

        self.pad_size = 80 if len(graph.hubs) < 20 else 40
        self.pad = pygame.transform.scale(
            self._load('pad.png'), (self.pad_size, self.pad_size))
        self.rainbow_pads = [self._tinted_pad(self._hue(step * 10))
                             for step in range(36)]
        self.rainbow_hubs: list[str] = []

        self.font = pygame.font.SysFont(None, 20)
        self.turn_font = pygame.font.SysFont(None, 30)
        self.labels = {
            name: self.font.render(name, True, (220, 220, 220),
                                   self.LABEL_BG)
            for name in graph.hubs
        }
        self.static = self._draw_static_layer()

    @staticmethod
    def _load(filename: str) -> pygame.Surface:
        return pygame.image.load(ASSETS_DIR / filename).convert_alpha()

    @staticmethod
    def _hue(degrees: int) -> pygame.Color:
        colour = pygame.Color(0)
        colour.hsva = (degrees, 50, 100, 100)
        return colour

    def _tinted_pad(self, colour: pygame.Color) -> pygame.Surface:
        tinted = self.pad.copy()
        tinted.fill(colour, special_flags=pygame.BLEND_RGBA_MULT)
        return tinted

    def _draw_static_layer(self) -> pygame.Surface:
        """Pre-render the background, links and hubs (except rainbow)."""
        static = pygame.transform.scale(
            pygame.image.load(ASSETS_DIR / 'background.png').convert(),
            (self.WIDTH, self.HEIGHT))
        for link in self.graph.links:
            pygame.draw.line(static, 'black',
                             self.centres[link.hub1.name],
                             self.centres[link.hub2.name],
                             5 * link.max_link_capacity)

        for name, hub in self.graph.hubs.items():
            if hub.color == 'rainbow':
                self.rainbow_hubs.append(name)
                continue
            pad = self.pad
            if hub.color is not None:
                try:
                    tint = pygame.Color(hub.color).lerp(pygame.Color('white'),
                                                        0.5)
                    pad = self._tinted_pad(tint)
                except ValueError:
                    self.invalid_colors.append(hub.color)
            static.blit(pad, pad.get_rect(center=self.centres[name]))
        return static

    def _position_of(self, place: str) -> tuple[float, float]:
        """Screen position of a hub, or of the midpoint of ``a-b``."""
        if '-' in place:
            a, b = place.split('-')
            (ax, ay), (bx, by) = self.centres[a], self.centres[b]
            return ((ax + bx) / 2, (ay + by) / 2)
        return self.centres[place]

    def _place_of(self, drone: Drone) -> str:
        """Where to draw a drone: on the link while entering a restricted
        hub, otherwise on its hub."""
        cur = drone.journey[self.turn]
        prev = drone.journey[self.turn - 1] if self.turn > 0 else cur
        if self.graph.hubs[cur].zone == 'restricted' and prev != cur:
            return f'{prev}-{cur}'
        return cur

    def _step(self, delta: int) -> None:
        self.turn = min(max(self.turn + delta, 0), self.last_turn)
        if delta < 0:
            self.left_pressed_at = pygame.time.get_ticks()
        else:
            self.right_pressed_at = pygame.time.get_ticks()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.left_rect.collidepoint(event.pos):
                    self._step(-1)
                elif self.right_rect.collidepoint(event.pos):
                    self._step(1)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_LEFT:
                    self._step(-1)
                elif event.key == pygame.K_RIGHT:
                    self._step(1)

    def _draw_rainbow_hubs(self, time: float) -> None:
        """Draw hubs whose colour cycles through the hue wheel."""
        for i, name in enumerate(self.rainbow_hubs):
            index = int(time * 12 + i * 6) % len(self.rainbow_pads)
            pad = self.rainbow_pads[index]
            self.screen.blit(pad, pad.get_rect(center=self.centres[name]))

    def _draw_hover_label(self) -> None:
        mx, my = pygame.mouse.get_pos()
        half = self.pad_size // 2
        for name, (cx, cy) in self.centres.items():
            if (mx - cx) ** 2 + (my - cy) ** 2 <= half ** 2:
                label = self.labels[name]
                self.screen.blit(label, label.get_rect(
                    midtop=(cx, cy + half + 4)))
                return

    def _draw_drone(self, x: float, y: float, bob: float) -> None:
        scale = 1 - bob / 20
        shadow = pygame.transform.scale(
            self.shadow, (round(50 * scale), round(12 * scale)))
        self.screen.blit(shadow, shadow.get_rect(center=(x, y + 26)))
        self.screen.blit(self.drone_sprite,
                         self.drone_sprite.get_rect(center=(x, y + bob)))

    def _draw_drones(self, time: float) -> None:
        """Draw every drone; crowded spots show one drone and a counter."""
        groups: dict[str, list[Drone]] = {}
        for drone in self.drones:
            groups.setdefault(self._place_of(drone), []).append(drone)

        for place, group in groups.items():
            cx, cy = self._position_of(place)
            if len(group) > 2:
                self._draw_drone(cx, cy, math.sin(time * 4) * 4)
                badge = self.font.render(f'x{len(group)}', True, self.WHITE,
                                         self.LABEL_BG)
                self.screen.blit(badge,
                                 badge.get_rect(midleft=(cx - 8, cy - 42)))
                continue
            for i, drone in enumerate(group):
                offset = (i - (len(group) - 1) / 2) * 30
                self._draw_drone(cx + offset, cy,
                                 math.sin(time * 3 + drone.id * 0.8) * 4)

    def _arrow_colour(self, enabled: bool, pressed_at: int) -> Color:
        if not enabled:
            return self.DARK_GRAY
        if pygame.time.get_ticks() - pressed_at < self.FLASH_MS:
            return self.LIGHT_GRAY
        return self.WHITE

    def _draw_controls(self) -> None:
        h = self.HEIGHT
        turn_txt = self.turn_font.render(f'Turn {self.turn}', True,
                                         self.WHITE)
        self.screen.blit(turn_txt, (25, h - 75))
        pygame.draw.polygon(
            self.screen,
            self._arrow_colour(self.turn > 0, self.left_pressed_at),
            [(50, h - 50), (50, h - 10), (10, h - 30)])
        pygame.draw.polygon(
            self.screen,
            self._arrow_colour(self.turn < self.last_turn,
                               self.right_pressed_at),
            [(60, h - 50), (100, h - 30), (60, h - 10)])

    def render_loop(self) -> None:
        """Run the window until the user closes it."""
        while self.running:
            time = pygame.time.get_ticks() / 1000
            self._handle_events()
            self.screen.blit(self.static, (0, 0))
            self._draw_rainbow_hubs(time)
            self._draw_hover_label()
            self._draw_drones(time)
            self._draw_controls()
            pygame.display.flip()
            self.clock.tick(self.FPS)

    def __enter__(self) -> 'Visualizer':
        return self

    def __exit__(self,
                 exc_type: type[BaseException] | None,
                 exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        pygame.quit()


def run_visualizer(graph: Map, drones: list[Drone]) -> None:
    """Open the visualizer window and block until it is closed."""
    with Visualizer(graph, drones) as viz:
        for colour in viz.invalid_colors:
            print(f'Warning: unknown color "{colour}", using the default.',
                  file=sys.stderr)
        viz.render_loop()
