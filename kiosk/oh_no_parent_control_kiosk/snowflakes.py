"""Quiet, continuous snowflake paths around the gateway artwork."""

from dataclasses import dataclass
import logging
import math
import random

import cairo


LOG = logging.getLogger("oh-no-parent-control")
# Bounds of the entire frame, including its neon edges, in artwork fractions.
GATEWAY_OUTER_BOUNDS = (1104 / 3840, 72 / 2160, 2520 / 3840, 2100 / 2160)
PIXEL_SIZE_RANGE = (0.9, 6.6)
DRIFT_PERIOD_RANGE = (25, 165)
HALO_RADIUS_UNITS = 5
PALETTE = (
    (0.37, 0.27, 0.95),
    (0.29, 0.44, 1.00),
    (0.35, 0.77, 1.00),
    (0.73, 0.88, 1.00),
)
PIXEL_FLAKES = (
    ((0, -1), (-1, 0), (0, 0), (1, 0), (0, 1)),
    ((0, -1), (-1, 0), (1, 0), (0, 1)),
    ((0, -2), (-1, -1), (1, -1), (-2, 0), (0, 0), (2, 0),
     (-1, 1), (1, 1), (0, 2)),
)


@dataclass(frozen=True)
class Drift:
    center: float
    amplitude: float
    period: float
    phase: float
    secondary_phase: float

    def position(self, elapsed):
        # Two long, differently phased waves make broad turns with smaller
        # meanders. Position and velocity stay continuous; there are no random
        # per-frame nudges, waypoint stops, wraps, or abrupt boundary bounces.
        angle = math.tau * elapsed / self.period
        return self.center + self.amplitude * (
            0.72 * math.sin(angle + self.phase)
            + 0.28 * math.sin(angle / 0.63 + self.secondary_phase)
        )


@dataclass(frozen=True)
class Snowflake:
    horizontal: Drift
    vertical: Drift
    pixel_size: float
    color: tuple
    opacity: float
    pixels: tuple


class SnowflakeField:
    def __init__(self):
        self._random = random.SystemRandom()
        self._geometry = None
        self._flakes = []

    def configure(self, width, height, artwork):
        """Fit paths to the visible screen and the cover-scaled gateway."""
        geometry = (width, height, *artwork)
        if geometry == self._geometry:
            return
        self._geometry = geometry
        self._flakes.clear()
        if width <= 0 or height <= 0:
            return

        scale = min(width / 1920, height / 1080)
        image_x, image_y, image_width, image_height = artwork
        left, top, right, bottom = GATEWAY_OUTER_BOUNDS
        # Leave room for the complete flake and its soft halo. Keeping the
        # whole path outside the frame avoids clipping or vanishing at it.
        margin = (PIXEL_SIZE_RANGE[1] * HALO_RADIUS_UNITS + 1) * scale
        left = max(0, min(width, image_x + left * image_width))
        right = max(0, min(width, image_x + right * image_width))
        top = max(0, min(height, image_y + top * image_height))
        bottom = max(0, min(height, image_y + bottom * image_height))
        regions = [
            (0, 0, width, top),
            (0, bottom, width, height),
            (0, top, left, bottom),
            (right, top, width, bottom),
        ]
        regions = [
            (x1 + margin, y1 + margin, x2 - margin, y2 - margin)
            for x1, y1, x2, y2 in regions
            if x2 - x1 > 2 * margin and y2 - y1 > 2 * margin
        ]
        areas = [(x2 - x1) * (y2 - y1) for x1, y1, x2, y2 in regions]
        count = round(100 * sum(areas) / (width * height))
        for _ in range(count):
            x1, y1, x2, y2 = self._random.choices(regions, weights=areas)[0]
            self._flakes.append(Snowflake(
                self._new_drift(x1, x2, 90 * scale),
                self._new_drift(y1, y2, 140 * scale),
                self._random.uniform(*PIXEL_SIZE_RANGE) * scale,
                self._random.choices(PALETTE, weights=(4, 4, 3, 1))[0],
                self._random.uniform(0.40, 0.85),
                self._random.choice(PIXEL_FLAKES),
            ))
        LOG.debug(
            "gateway snowflakes configured count=%d pixel_size_range=%s "
            "drift_period_seconds=%s",
            len(self._flakes), PIXEL_SIZE_RANGE, DRIFT_PERIOD_RANGE,
        )

    def _new_drift(self, lower, upper, maximum_amplitude):
        # Choose a visible excursion before placing its center. Choosing the
        # center first can leave edge flakes with almost no room to move.
        amplitude = min((upper - lower) / 2, maximum_amplitude)
        amplitude *= self._random.uniform(0.55, 0.95)
        center = self._random.uniform(lower + amplitude, upper - amplitude)
        return Drift(
            center,
            amplitude,
            self._random.uniform(*DRIFT_PERIOD_RANGE),
            self._random.uniform(0, math.tau),
            self._random.uniform(0, math.tau),
        )

    def draw(self, context, elapsed):
        for flake in self._flakes:
            x = flake.horizontal.position(elapsed)
            y = flake.vertical.position(elapsed)
            unit = flake.pixel_size
            red, green, blue = flake.color
            radius = unit * HALO_RADIUS_UNITS
            glow = cairo.RadialGradient(x, y, 0, x, y, radius)
            glow.add_color_stop_rgba(0, red, green, blue, flake.opacity * 0.22)
            glow.add_color_stop_rgba(1, red, green, blue, 0)
            context.set_source(glow)
            context.rectangle(x - radius, y - radius, 2 * radius, 2 * radius)
            context.fill()
            context.set_source_rgba(red, green, blue, flake.opacity)
            for column, row in flake.pixels:
                context.rectangle(
                    x + (column - 0.5) * unit,
                    y + (row - 0.5) * unit,
                    unit, unit,
                )
            context.fill()
