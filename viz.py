#!/usr/bin/env python3

from map_class import create_map, Map
from pathfinder import Drone, schedule_drones
from parse_files import check_connections
import pygame
import math
from typing import Final
from types import TracebackType


class Visualizer:
    """Visualizer object for visualization.
    """
    WHITE: Final = (255, 255, 255)
    LIGHT_GRAY: Final = (170, 170, 170)
    DARK_GRAY: Final = (100, 100, 100)
    FLASH_MS: Final = 150
    WIDTH: int = 1000
    HEIGHT: int = 700

    def __init__(self, map: Map, drones: list[Drone]) -> None:
        """Initialize a Visualization object.

        Args:
            map (Map): Map Object (Graph)
            drones (list[Drone]): Drone objects holding their path
        """
        pygame.init()
        self.map: Map = map
        self.drones: list[Drone] = drones

        self.screen: pygame.Surface = (pygame.display.
                                       set_mode((self.WIDTH, self.HEIGHT)))
        self.background: pygame.Surface = (pygame.image.
                                           load('map_cropped.png').convert())
        self.BACKGROUND: Final = (pygame.transform.
                                  scale(self.background,
                                        (self.WIDTH, self.HEIGHT))
                                  )
        self.drone_sprite: pygame.Surface = (pygame.image.
                                             load('drone.png').convert_alpha())
        self.DRONE_SPRITE: Final = pygame.transform.scale(self.drone_sprite,
                                                          (80, 40))
        self.PAD: Final = (pygame.image.
                           load('circle.png').convert_alpha())
        self.LEFT_RECT: Final = pygame.Rect(10, self.HEIGHT - 50, 40, 40)
        self.RIGHT_RECT: Final = pygame.Rect(60, self.HEIGHT - 50, 40, 40)
        self.shadow: pygame.Surface = pygame.Surface((50, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(self.shadow, (0, 0, 0, 90), self.shadow.get_rect())

        self.spacing_x: float = self.WIDTH / (map.max_x + 1)
        self.spacing_y: float = self.HEIGHT / (map.max_y + 1)
        self.centres: dict[str, tuple[int, int]] = {
            name: (round(self.spacing_x * (hub.x + 0.5)),
                   round(self.spacing_y * (hub.y + 0.5)))
            for name, hub in map.hubs.items()
        }

        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.running: bool = True
        self.left_pressed_at = -self.FLASH_MS
        self.right_pressed_at = -self.FLASH_MS

        self.pad_size: int = 80 if len(map.hubs) < 20 else 40
        self.half: int = self.pad_size // 2
        self.pad = pygame.transform.scale(self.PAD, (self.pad_size,
                                                     self.pad_size))
        self.rainbow_hubs: list[str] = []
        self.rainbow_pads: list[pygame.Surface] = []
        for step in range(36):
            colour = pygame.Color(0)
            colour.hsva = (step * 10, 50, 100, 100)
            tinted = self.pad.copy()
            tinted.fill(colour, special_flags=pygame.BLEND_RGBA_MULT)
            self.rainbow_pads.append(tinted)
        self.font: pygame.font.Font = (pygame.font.
                                       SysFont(None, 30
                                               if self.pad_size == 50 else 20))
        self.labels: dict[str, pygame.Surface] = {
            name: self.font.render(name, True, (220, 220, 220), (60, 60, 60))
            for name in map.hubs
        }

        self.is_error: bool = False
        self.static = self.BACKGROUND.copy()

        for connection in map.connections.values():
            pygame.draw.line(self.static, 'black',
                             self.centres[connection.hub1.name],
                             self.centres[connection.hub2.name],
                             5 * connection.max_link_capacity)

        for name, hub in map.hubs.items():
            if hub.color is not None and hub.color.lower() == 'rainbow':
                self.rainbow_hubs.append(name)
                continue
            tinted = self.pad.copy()
            if hub.color is not None:
                try:
                    tint = pygame.Color(hub.color).lerp(pygame.Color('white'),
                                                        0.5)
                    tinted.fill(tint, special_flags=pygame.BLEND_RGBA_MULT)
                except ValueError:
                    self.is_error = True
            (self.static.
             blit(tinted, tinted.get_rect(center=self.centres[name])))

        self.turn = 0
        self.turn_font: pygame.font.Font = (pygame.font.
                                            SysFont(None, 30))

    def _position_of(self, place: str) -> tuple[float, float]:
        """Get position for a specific hub or connection.

        Args:
            place (str): current place a drone is.

        Returns:
            tuple[float, float]: coordinates (x,y)
        """
        if '-' in place:
            a, b = place.split('-')
            (ax, ay), (bx, by) = self.centres[a], self.centres[b]
            return ((ax + bx) / 2, (ay + by) / 2)
        return self.centres[place]

    def _place_of(self, drone: Drone) -> str:
        """Get connection name if zone is restricted, else hub name

        Args:
            drone (Drone): Drone object

        Returns:
            str: name of connection or hub
        """
        cur = drone.journey[self.turn]
        prev = drone.journey.get(self.turn - 1, cur)
        if self.map.hubs[cur].zone == 'restricted' and prev != cur:
            return f'{prev}-{cur}'
        return cur

    def _draw_rainbow_hubs(self, time: float) -> None:
        """Draw hubs whose colour cycles through the hue wheel.

        Args:
            time (float): current time in seconds.
        """
        for i, name in enumerate(self.rainbow_hubs):
            index = int(time * 12 + i * 6) % len(self.rainbow_pads)
            pad = self.rainbow_pads[index]
            self.screen.blit(pad, pad.get_rect(center=self.centres[name]))

    def _get_events(self) -> None:
        """Check pygame events for quitting and button presses.
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.LEFT_RECT.collidepoint(event.pos):
                    self.turn = max(self.turn - 1, 0)
                    self.left_pressed_at = pygame.time.get_ticks()
                elif self.RIGHT_RECT.collidepoint(event.pos):
                    self.turn = (min(self.turn + 1,
                                     len(self.drones[0].journey) - 1))
                    self.right_pressed_at = pygame.time.get_ticks()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_LEFT:
                    self.turn = max(self.turn - 1, 0)
                    self.left_pressed_at = pygame.time.get_ticks()
                elif event.key == pygame.K_RIGHT:
                    self.turn = (min(self.turn + 1,
                                     len(self.drones[0].journey) - 1))
                    self.right_pressed_at = pygame.time.get_ticks()

    def _draw_arrows(self) -> None:
        """Draw arrow buttons.
        """
        left_arrow: list[tuple[int, int]] = [
                (50, self.HEIGHT - 50),
                (50, self.HEIGHT - 10),
                (10, self.HEIGHT - 30)
                ]
        right_arrow: list[tuple[int, int]] = [
            (60, self.HEIGHT - 50),
            (100, self.HEIGHT - 30),
            (60, self.HEIGHT - 10)
            ]

        now: int = pygame.time.get_ticks()

        turn_txt: pygame.Surface = (self.turn_font.
                                    render(f'Turn {self.turn}',
                                           True,
                                           self.WHITE))
        self.screen.blit(turn_txt, (25, self.HEIGHT - 75))

        if self.turn == 0:
            pygame.draw.polygon(self.screen, self.DARK_GRAY, left_arrow)
        else:
            color: tuple[int, int, int] = (
                self.LIGHT_GRAY
                if now - self.left_pressed_at < self.FLASH_MS
                else self.WHITE
                )
            pygame.draw.polygon(self.screen, color, left_arrow)

        if self.turn == len(self.drones[0].journey) - 1:
            pygame.draw.polygon(self.screen, self.DARK_GRAY, right_arrow)
        else:
            color = (
                self.LIGHT_GRAY
                if now - self.right_pressed_at < self.FLASH_MS
                else self.WHITE
                )
            pygame.draw.polygon(self.screen, color, right_arrow)

    def _draw_map_w_drones(self,
                           groups: dict[str, list[Drone]],
                           time: float) -> None:
        """Draw hubs, connections and drones.

        Args:
            groups (dict[str, list[Drone]]): dictionary mapping hub to drones.
            time (float): current time.
        """
        for name, group in groups.items():
            cx: float
            cy: float
            cx, cy = self._position_of(name)
            if len(group) > 2:
                bob: float = math.sin(time * 4) * 4
                scale: float = 1 - bob / 20
                shadow_scale: pygame.Surface = (
                    pygame.transform.
                    scale(self.shadow,
                          (round(50 * scale),
                           round(12 * scale)))
                    )

                self.screen.blit(shadow_scale, shadow_scale.get_rect(
                    center=(cx, cy + 26)))
                self.screen.blit(self.DRONE_SPRITE, self.DRONE_SPRITE.
                                 get_rect(center=(cx, cy + bob)))
                badge: pygame.Surface = self.font.render(f'x{len(group)}',
                                                         True,
                                                         self.WHITE,
                                                         (60, 60, 60))
                self.screen.blit(badge,
                                 badge.get_rect(midleft=(cx - 8, cy - 42)))
            else:
                for i, drone in enumerate(group):
                    offset: float = (i - (len(group) - 1) / 2) * 30
                    bob = math.sin(time * 3 + drone.id * 0.8) * 4
                    scale = 1 - bob / 20
                    shadow_scale = (pygame.
                                    transform.
                                    scale(self.shadow,
                                          (round(50 * scale),
                                           round(12 * scale)))
                                    )
                    self.screen.blit(shadow_scale,
                                     shadow_scale.get_rect(
                                      center=(cx + offset, cy + 26))
                                     )
                    self.screen.blit(self.DRONE_SPRITE,
                                     self.DRONE_SPRITE.get_rect(
                                      center=(cx + offset, cy + bob))
                                     )

    def render_loop(self) -> None:
        """Render the simulation.
        """
        while self.running:
            time: float = pygame.time.get_ticks() / 1000

            self._get_events()

            self.screen.blit(self.static, (0, 0))
            self.screen.blit(self.static, (0, 0))
            self._draw_rainbow_hubs(time)

            mx: int
            my: int
            mx, my = pygame.mouse.get_pos()
            for name, (cx, cy) in self.centres.items():
                if (mx - cx) ** 2 + (my - cy) ** 2 <= self.half ** 2:
                    label: pygame.Surface = self.labels[name]
                    self.screen.blit(label,
                                     label.get_rect(
                                         midtop=(cx, cy + self.half + 4))
                                     )
                    break

            groups: dict[str, list[Drone]] = {}
            for drone in self.drones:
                groups.setdefault(self._place_of(drone), []).append(drone)

            self._draw_map_w_drones(groups, time)
            self._draw_arrows()
            pygame.display.flip()
            self.clock.tick(60)

    def print_terminal_output(self) -> None:
        """Print the simulation.
        """
        output: str = '=====================================================\n'
        for turn in range(len(self.drones[0].journey)):
            start: str = output
            for drone in self.drones:
                if (drone.journey.get(turn - 1, 0) == drone.journey[turn]
                    and self.map.hubs[drone.journey[turn]].zone != 'restricted'
                   or turn == 0):
                    continue
                place: str = drone.journey[turn]
                if (self.map.hubs[place].zone == 'restricted'
                   and drone.journey.get(turn - 1, 0) != drone.journey[turn]):
                    conn: str = (f'{drone.journey[turn - 1]}' +
                                 f'-{drone.journey[turn]}')
                    output += f'D{drone.id}-{conn} '
                else:
                    output += f'D{drone.id}-{drone.journey[turn]} '
            if output != start:
                output += '\n'
        output += '====================================================='
        print(output)

    def __enter__(self) -> 'Visualizer':
        """Dunder method for context managers.

        Returns:
            Visualizer: Visualizer object
        """
        return self

    def __exit__(self,
                 exc_type: type[BaseException] | None,
                 exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        """Dunder method for context managers.

        Args:
            exc_type (type[BaseException] | None): Class of the exception
                raised inside the ``with`` block, or None if it exited
                normally.
            exc (BaseException | None): The exception instance, or None.
            tb (TracebackType | None): Traceback of the exception, or None.
        """
        pygame.quit()


def visualize() -> None:
    """Run visualization.
    """
    check_connections()
    map: Map = create_map()
    drones: list[Drone] = schedule_drones(map)

    with Visualizer(map, drones) as viz:
        viz.print_terminal_output()
        viz.render_loop()

    if viz.is_error:
        print('Invalid color was given, so default has been used.')


if __name__ == '__main__':
    visualize()
