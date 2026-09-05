"""Original crystal artwork on independent, smoothly randomized float paths."""

from dataclasses import dataclass
import logging
import random

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Graphene, Gsk, Gtk


LOG = logging.getLogger("oh-no-parent-control")
SOURCE_WIDTH = 1672
SOURCE_HEIGHT = 941
# The previous shortest turn was 3.4 / 2.1 seconds. Lengthening it by the
# reciprocal of the 85% speed cap preserves the excursion while reducing the
# highest possible float velocity to 85% of its prior limit.
TURN_SECONDS = ((3.4 / 2.1) / 0.85, 6.8 / 2.1)
EXCURSION = (6 / 1080, 13 / 1080)


@dataclass(frozen=True)
class Island:
    lightning_tip_index: int
    outline: tuple


# Silhouettes in kiosk-background-still.png coordinates, including each island's
# stone base. Runtime masks retain the actual artwork pixels, without repainting
# the crystals. The lower-right and foreground formations remain on the floor.
ISLANDS = (
    Island(0, (
        (272, 90), (282, 109), (286, 122), (277, 140), (288, 139),
        (292, 145), (286, 164), (300, 181), (297, 201), (279, 203),
        (267, 192), (259, 216), (225, 235), (218, 236), (207, 218),
        (204, 209), (210, 192), (191, 190), (194, 168), (214, 158),
        (201, 142), (200, 130), (204, 118), (224, 124), (236, 141),
        (244, 103), (257, 95),
    )),
    Island(1, (
        (138, 313), (180, 313), (198, 318), (198, 354), (210, 351),
        (225, 358), (225, 393), (239, 393), (239, 430), (243, 430),
        (243, 467), (266, 467), (266, 514), (211, 518), (211, 555),
        (176, 559), (142, 558), (142, 518), (84, 518), (84, 467),
        (123, 467), (98, 438), (88, 415), (88, 403), (96, 393),
        (113, 391), (124, 402), (125, 351), (138, 351),
    )),
    Island(2, (
        (298, 567), (306, 576), (318, 590), (318, 622), (340, 603),
        (348, 622), (350, 629), (343, 642), (357, 643), (357, 656),
        (346, 674), (375, 675), (375, 684), (412, 684), (412, 736),
        (394, 752), (338, 752), (325, 771), (264, 772), (228, 766),
        (168, 760), (168, 749), (119, 748), (119, 699), (138, 688),
        (199, 688), (218, 678), (236, 680), (229, 668), (222, 656),
        (224, 642), (237, 639), (234, 619), (243, 605), (260, 610),
        (272, 632), (273, 590), (286, 576),
    )),
    Island(4, (
        (1294, 360), (1320, 357), (1348, 360), (1348, 390),
        (1364, 391), (1364, 428), (1375, 422), (1388, 421),
        (1396, 438), (1385, 456), (1395, 457), (1395, 489),
        (1399, 489), (1399, 530), (1352, 535), (1352, 569),
        (1314, 571), (1286, 566), (1286, 534), (1244, 530),
        (1245, 489), (1256, 489), (1255, 456), (1267, 456),
        (1266, 425), (1277, 424), (1277, 391), (1294, 390),
    )),
)


class RandomFloat:
    """Random turning heights/times with continuous velocity and acceleration.

    Each half-wave is a quintic curve. Its derivatives vanish at the join, so
    newly sampled turns cannot introduce a twitch. Heights and durations are
    drawn again at EVERY turn; there is no periodic sine/cosine or looped clip.
    """

    def __init__(self, rng=None):
        self._random = rng if rng is not None else random.SystemRandom()
        self._start = self._random.choice((-1, 1)) * self._random.uniform(*EXCURSION)
        self._target = self._next_target(self._start)
        self._duration = self._random.uniform(*TURN_SECONDS)
        # Begin partway through an independent wave instead of synchronizing
        # all four objects at a turning point when the window opens.
        self._starts_at = -self._random.random() * self._duration

    def _next_target(self, previous):
        return (-1 if previous > 0 else 1) * self._random.uniform(*EXCURSION)

    def position(self, elapsed):
        """Return the vertical offset as a fraction of artwork height."""
        while elapsed >= self._starts_at + self._duration:
            self._starts_at += self._duration
            self._start = self._target
            self._target = self._next_target(self._start)
            self._duration = self._random.uniform(*TURN_SECONDS)
        fraction = max(0.0, (elapsed - self._starts_at) / self._duration)
        eased = fraction ** 3 * (10 + fraction * (-15 + 6 * fraction))
        return self._start + (self._target - self._start) * eased


class FloatingIslands:
    """Cached GTK layers, sharing the gateway's cover transform and frame time."""

    def __init__(self, original, clear):
        self._paths = {island.lightning_tip_index: RandomFloat() for island in ISLANDS}
        self._sprites = []
        self._background = None
        if original is None or clear is None:
            return

        background = Gtk.Snapshot()
        for island in ISLANDS:
            # The generated fill is used only under the original silhouettes.
            # A small soft margin removes the original edge/glow without
            # changing the gateway, floor, or any other stationary artwork.
            self._append_masked(background, clear, island.outline, padding=14)
            sprite = Gtk.Snapshot()
            self._append_masked(sprite, original, island.outline)
            self._sprites.append((island.lightning_tip_index, sprite.to_node()))
        self._background = background.to_node()
        LOG.debug(
            "gateway floating islands configured count=%d turn_seconds=%s "
            "max_speed_percent_of_previous=85 excursion_at_1080px=(6, 13)",
            len(self._sprites), TURN_SECONDS,
        )

    @staticmethod
    def _append_masked(snapshot, texture, outline, padding=0):
        left = min(x for x, _y in outline) - padding * 3 - 2
        top = min(y for _x, y in outline) - padding * 3 - 2
        right = max(x for x, _y in outline) + padding * 3 + 2
        bottom = max(y for _x, y in outline) + padding * 3 + 2
        bounds = Graphene.Rect().init(left, top, right - left, bottom - top)
        snapshot.push_mask(Gsk.MaskMode.ALPHA)
        if padding:
            snapshot.push_blur(5)
        context = snapshot.append_cairo(bounds)
        context.move_to(*outline[0])
        for point in outline[1:]:
            context.line_to(*point)
        context.close_path()
        context.set_source_rgba(1, 1, 1, 1)
        context.fill_preserve()
        context.set_line_width(2 * padding if padding else 0.8)
        context.stroke()
        if padding:
            snapshot.pop()
        snapshot.pop()
        snapshot.append_texture(texture, Graphene.Rect().init(
            0, 0, SOURCE_WIDTH, SOURCE_HEIGHT,
        ))
        snapshot.pop()

    def offset(self, tip_index, elapsed):
        if self._background is None or tip_index not in self._paths:
            return 0.0
        return self._paths[tip_index].position(elapsed)

    def draw(self, snapshot, artwork, elapsed):
        if self._background is None:
            return
        x, y, width, height = artwork
        snapshot.save()
        snapshot.translate(Graphene.Point().init(x, y))
        snapshot.scale(width / SOURCE_WIDTH, height / SOURCE_HEIGHT)
        snapshot.append_node(self._background)
        for tip_index, sprite in self._sprites:
            snapshot.save()
            snapshot.translate(Graphene.Point().init(
                0, self.offset(tip_index, elapsed) * SOURCE_HEIGHT,
            ))
            snapshot.append_node(sprite)
            snapshot.restore()
        snapshot.restore()
