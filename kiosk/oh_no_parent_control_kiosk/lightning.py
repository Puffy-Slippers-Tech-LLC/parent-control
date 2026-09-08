"""Short, branching crystal discharges in the gateway's pixel-art palette."""

from dataclasses import dataclass
import math
import random

import cairo


@dataclass(frozen=True)
class Flash:
    starts_at: float
    duration: float
    brightness: float
    fade_rate: float

    def light(self, age):
        progress = (age - self.starts_at) / self.duration
        if not 0 <= progress < 1:
            return 0.0
        return self.brightness * (1 - progress) ** self.fade_rate


def _jagged_path(rng, start, end, depth, roughness):
    """Subdivide at unequal intervals, keeping hard corners and fixed ends.

    Coordinates run along/across the discharge, in fractions of its length.
    Smaller displacements on each pass give large kinks finer broken edges,
    without a repeated zigzag or a smooth, waving cable.
    """
    points = (start, end)
    for _ in range(depth):
        subdivided = [points[0]]
        for left, right in zip(points, points[1:]):
            fraction = rng.uniform(0.32, 0.68)
            span = right[0] - left[0]
            subdivided.extend((
                (
                    left[0] + span * fraction,
                    left[1] + (right[1] - left[1]) * fraction
                    + rng.uniform(-roughness, roughness) * span,
                ),
                right,
            ))
        points = tuple(subdivided)
    return points


class LightningDischarge:
    """One fixed channel, a few brief return flashes, and fading square sparks.

    All randomness belongs to the strike, never to the drawing frame. A flash
    lights the complete channel immediately; it cannot stretch or swim toward
    its destination as it fades. Drawing only depends on elapsed time.
    """

    def __init__(self, rng=None):
        rng = rng if rng is not None else random.SystemRandom()
        self.points = _jagged_path(rng, (0.0, 0.0), (1.0, 0.0), 4, 0.22)
        self.width = rng.uniform(1.6, 2.8)
        branches = []
        for index in rng.sample(range(3, len(self.points) - 4), rng.randint(2, 4)):
            root = self.points[index]
            length = rng.uniform(0.10, 0.24)
            # Forks peel away from actual trunk vertices and continue toward
            # the gate. They remain attached through every return flash.
            side = -1 if root[1] < 0 else 1
            end = (
                min(0.96, root[0] + length),
                root[1] + side * length * rng.uniform(0.45, 0.85),
            )
            branches.append((
                _jagged_path(rng, root, end, 3, 0.25),
                rng.uniform(0.30, 0.48),
            ))
        self.branches = tuple(branches)

        flashes = [Flash(0.0, rng.uniform(0.11, 0.16), 1.0, 1.65)]
        for _ in range(rng.choices((0, 1, 2), weights=(3, 6, 1))[0]):
            previous = flashes[-1]
            flashes.append(Flash(
                previous.starts_at + previous.duration + rng.uniform(0.055, 0.11),
                rng.uniform(0.075, 0.12),
                rng.uniform(0.55, 0.85),
                rng.uniform(1.3, 1.8),
            ))
        self.flashes = tuple(flashes)
        self._sparks = tuple(
            (
                anchor, rng.uniform(-34, 34), rng.uniform(-40, 8),
                rng.uniform(0.22, 0.38), rng.uniform(1.2, 2.5),
            )
            for anchor in (0, 1)
            for _ in range(rng.randint(2, 4))
        )
        last = self.flashes[-1]
        self.duration = max(
            last.starts_at + last.duration,
            max(spark[3] for spark in self._sparks),
        )

    def active_flash(self, age):
        for index, flash in enumerate(self.flashes):
            if flash.starts_at <= age < flash.starts_at + flash.duration:
                return index, flash
        return None

    @staticmethod
    def _stroke(context, points, width, light):
        # Restrained, narrow light around a crisp, bevelled channel. Broad
        # opaque outlines would turn the discharge into a purple ribbon.
        context.move_to(*points[0])
        for point in points[1:]:
            context.line_to(*point)
        for multiplier, color, alpha in (
            (5.0, (0.36, 0.22, 1.0), 0.07),
            (2.3, (0.48, 0.49, 1.0), 0.28),
            (1.0, (0.72, 0.83, 1.0), 0.92),
            (0.42, (0.97, 0.99, 1.0), 1.0),
        ):
            context.set_source_rgba(*color, light * alpha)
            context.set_line_width(max(0.45, width * multiplier))
            context.stroke_preserve()
        context.new_path()

    @staticmethod
    def _contact_light(context, point, scale, light):
        x, y = point
        radius = 22 * scale
        glow = cairo.RadialGradient(x, y, 0, x, y, radius)
        glow.add_color_stop_rgba(0, 0.65, 0.76, 1.0, light * 0.32)
        glow.add_color_stop_rgba(0.3, 0.38, 0.40, 1.0, light * 0.12)
        glow.add_color_stop_rgba(1, 0.30, 0.22, 1.0, 0)
        context.set_source(glow)
        context.rectangle(x - radius, y - radius, radius * 2, radius * 2)
        context.fill()
        size = max(1, round(3 * scale))
        context.set_source_rgba(0.88, 0.94, 1.0, light * 0.85)
        context.rectangle(round(x - size / 2), round(y - size / 2), size, size)
        context.fill()

    def draw(self, context, source, target, scale, age):
        if age < 0 or age >= self.duration or scale <= 0:
            return
        vector_x, vector_y = target[0] - source[0], target[1] - source[1]
        if math.hypot(vector_x, vector_y) < 1:
            return

        def project(points):
            return tuple(
                (
                    source[0] + vector_x * along - vector_y * across,
                    source[1] + vector_y * along + vector_x * across,
                )
                for along, across in points
            )

        context.save()
        context.set_line_join(cairo.LineJoin.BEVEL)
        context.set_line_cap(cairo.LineCap.SQUARE)
        active = self.active_flash(age)
        if active is not None:
            flash_index, flash = active
            light = flash.light(age)
            width = self.width * scale
            for point in (source, target):
                self._contact_light(context, point, scale, light)
            for points, thickness in self.branches:
                # Fine leaders die away before the main channel. Subsequent
                # pulses follow the same trunk, with much fainter forks.
                branch_light = light ** 1.6 * (0.72 if flash_index == 0 else 0.32)
                self._stroke(context, project(points), width * thickness, branch_light)
            self._stroke(context, project(self.points), width, light)

        # A handful of square embers fall away from the two contact points;
        # nothing travels along the bolt like a projectile or trailing ribbon.
        context.set_antialias(cairo.Antialias.NONE)
        for anchor, velocity_x, velocity_y, lifetime, size in self._sparks:
            if age >= lifetime:
                continue
            origin = source if anchor == 0 else target
            x = origin[0] + velocity_x * age * scale
            y = origin[1] + (velocity_y * age + 45 * age * age) * scale
            size = max(1, round(size * scale))
            context.set_source_rgba(0.67, 0.82, 1.0, 0.7 * (1 - age / lifetime) ** 1.5)
            context.rectangle(round(x), round(y), size, size)
            context.fill()
        context.restore()
