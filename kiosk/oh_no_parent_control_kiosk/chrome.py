"""Visual chrome for the shared request GUI.

Look-and-feel only: pixel-art icons, stone-and-iron panels, rivets, HUD
plates, and the bundled Minecraft-inspired form font. Request behavior stays
in ``request_content``.
"""

from __future__ import annotations

import math
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Graphene, Gsk, Gtk, PangoCairo

FORM_FONT_FAMILY = "Monocraft"
FORM_FONT_FILE = Path(__file__).resolve().parent / "fonts" / "Monocraft.ttf"
BOARD_RIVET_INSET = 12.0
# Chains terminate on dedicated lugs in the vertical rails, away from the
# fragile-looking outer vertices. Export both coordinates so the projected
# chain geometry and painted mount hardware always coincide.
BOARD_CHAIN_ANCHOR_SIDE_INSET = 12.0
BOARD_CHAIN_ANCHOR_END_INSET = 34.0


def register_form_font() -> bool:
    """Load the bundled form font into the process-wide Pango map."""
    if not FORM_FONT_FILE.is_file():
        return False
    return bool(PangoCairo.FontMap.get_default().add_font_file(str(FORM_FONT_FILE)))


register_form_font()


def _parse_sprite(sprite: str, palette: dict) -> tuple[tuple[tuple[int, int, int, int] | None, ...], ...]:
    rows = []
    for line in sprite.strip("\n").split("\n"):
        rows.append(tuple(palette.get(character) for character in line))
    return tuple(rows)


def _texture_from_pixels(rows) -> Gdk.MemoryTexture:
    height = len(rows)
    width = len(rows[0])
    buf = bytearray(width * height * 4)
    index = 0
    for row in rows:
        for pixel in row:
            if pixel is None:
                buf[index:index + 4] = b"\x00\x00\x00\x00"
            else:
                red, green, blue, alpha = pixel
                buf[index] = red * alpha // 255
                buf[index + 1] = green * alpha // 255
                buf[index + 2] = blue * alpha // 255
                buf[index + 3] = alpha
            index += 4
    return Gdk.MemoryTexture.new(
        width,
        height,
        Gdk.MemoryFormat.R8G8B8A8_PREMULTIPLIED,
        GLib.Bytes.new(bytes(buf)),
        width * 4,
    )


_SKIN = (198, 134, 66, 255)
_SKIN_SHADOW = (166, 107, 50, 255)
_EYE_WHITE = (242, 242, 242, 255)
_EYE = (45, 32, 18, 255)
_MOUTH = (138, 75, 46, 255)
_CHILD_HAIR = (89, 55, 22, 255)
_CHILD_HAIR_DARK = (59, 35, 20, 255)
_APPROVER_HAIR = (62, 38, 22, 255)
_APPROVER_HAIR_DARK = (36, 22, 14, 255)

CHILD_HEAD = _parse_sprite(
    """
HHHHHHHH
HhHHHHHh
HhSSSShh
HSWBWBSH
HSSSSSSH
HSsMMsSH
HhSSSShh
HHHHHHHH
""",
    {
        "H": _CHILD_HAIR_DARK,
        "h": _CHILD_HAIR,
        "S": _SKIN,
        "s": _SKIN_SHADOW,
        "W": _EYE_WHITE,
        "B": _EYE,
        "M": _MOUTH,
    },
)

APPROVER_HEAD = _parse_sprite(
    """
NNNNNNNN
NnNNNNNn
NnSSSSnn
NSWBWBSN
NSSSSSSN
NSsMMsSN
NnSSSSnn
NNNNNNNN
""",
    {
        "N": _APPROVER_HAIR_DARK,
        "n": _APPROVER_HAIR,
        "S": _SKIN,
        "s": _SKIN_SHADOW,
        "W": _EYE_WHITE,
        "B": _EYE,
        "M": _MOUTH,
    },
)

SHIELD = _parse_sprite(
    """
..CCCC..
.CccccC.
CcGGGGCc
CcGggGCc
.CcGGCc.
..CccC..
...CC...
........
""",
    {
        "C": (36, 89, 70, 255),
        "c": (91, 172, 106, 255),
        "G": (81, 151, 91, 255),
        "g": (164, 215, 158, 255),
    },
)

LOCK = _parse_sprite(
    """
..bbbb..
.b....b.
.b....b.
BBBBBBBB
BB.WW.BB
BB.WW.BB
BBBBBBBB
.BBBBBB.
""",
    {
        "B": (190, 144, 33, 255),
        "b": (126, 91, 22, 255),
        "W": (63, 50, 24, 255),
    },
)

POINTER = _parse_sprite(
    """
...MM...
..MLLM..
.MLLLLM.
MLLLLLLM
MLLLLLLM
.MLLLLM.
..MLLM..
...MM...
""",
    {
        "M": (46, 49, 44, 255),
        "L": (190, 184, 151, 255),
    },
)

SPEAKER = _parse_sprite(
    """
................
.......WW.......
......W.W.......
.....W..W...W...
....W...W....W..
...W....W.....W.
.WW.....W......W
.W......W......W
.W......W......W
.W......W......W
.WW.....W......W
...W....W.....W.
....W...W....W..
.....W..W...W...
......W.W.......
.......WW.......
""",
    {
        "W": (241, 238, 248, 255),
    },
)

SPEAKER_MUTED = _parse_sprite(
    """
................
.......WW.......
......W.W.......
.....W..W.......
....W...W.......
...W....W...W..W
.WW.....W....WW.
.W......W.....W.
.W......W....WW.
.W......W...W..W
.WW.....W.......
...W....W.......
....W...W.......
.....W..W.......
......W.W.......
.......WW.......
""",
    {
        "W": (241, 238, 248, 255),
    },
)

MENU = _parse_sprite(
    """
................
................
................
..WWWWWWWWWWWW..
..WWWWWWWWWWWW..
................
..WWWWWWWWWWWW..
..WWWWWWWWWWWW..
................
..WWWWWWWWWWWW..
..WWWWWWWWWWWW..
................
................
................
................
................
""",
    {
        "W": (241, 238, 248, 255),
    },
)

HELP = _parse_sprite(
    """
..WWWW..
.WW..WW.
.....WW.
...WWW..
...WW...
........
...WW...
...WW...
""",
    {"W": (241, 238, 248, 255)},
)

ABOUT = _parse_sprite(
    """
...WW...
........
...WW...
..WWW...
...WW...
...WW...
..WWWW..
........
""",
    {"W": (241, 238, 248, 255)},
)


class PixelIcon(Gtk.Widget):
    """Nearest-neighbor pixel sprite used as decorative form chrome."""

    __gtype_name__ = "OhNoPixelIcon"

    def __init__(self, pixels, *, display_size=16, label=""):
        super().__init__()
        self._texture = _texture_from_pixels(pixels)
        self._display_size = display_size
        self.add_css_class("oh-no-parent-control-pixel-icon")
        self.set_size_request(display_size, display_size)
        if label:
            self.set_tooltip_text(label)

    def set_pixels(self, pixels):
        """Replace the sprite while keeping the same on-screen size."""
        self._texture = _texture_from_pixels(pixels)
        self.queue_draw()

    def do_measure(self, orientation, for_size):
        size = self._display_size
        return size, size, -1, -1

    def do_snapshot(self, snapshot):
        width = self.get_width()
        height = self.get_height()
        if width <= 0 or height <= 0:
            return
        snapshot.append_scaled_texture(
            self._texture,
            Gsk.ScalingFilter.NEAREST,
            Graphene.Rect().init(0, 0, width, height),
        )


def _rectangle(context, x, y, width, height, red, green, blue, alpha=1.0):
    context.rectangle(x, y, max(0, width), max(0, height))
    context.set_source_rgba(red, green, blue, alpha)
    context.fill()


def _paint_block_texture(context, x, y, width, height, *, dark=False):
    """Paint a restrained deterministic stone texture using square fragments."""
    if width <= 0 or height <= 0:
        return
    base = (0.105, 0.112, 0.108) if dark else (0.265, 0.270, 0.255)
    _rectangle(context, x, y, width, height, *base)
    tile = 8
    columns = max(1, int(width // tile) + 1)
    rows = max(1, int(height // tile) + 1)
    for row in range(rows):
        for column in range(columns):
            value = (column * 37 + row * 61 + column * row * 7) % 29
            if value not in {0, 2, 11, 17}:
                continue
            light = value in {2, 17}
            shade = 0.040 if light else -0.045
            fragment_width = tile * (2 if value == 11 else 1)
            _rectangle(
                context,
                x + column * tile,
                y + row * tile,
                min(fragment_width, x + width - (x + column * tile)),
                min(3, y + height - (y + row * tile)),
                max(0, base[0] + shade),
                max(0, base[1] + shade),
                max(0, base[2] + shade),
                0.66,
            )


def _paint_bevel(context, x, y, width, height, *, inset=False, heavy=False):
    thickness = 3.0 if heavy else 2.0
    light = (0.61, 0.62, 0.58)
    shade = (0.075, 0.080, 0.076)
    if inset:
        light, shade = shade, light
    context.set_line_width(thickness)
    context.set_line_cap(0)
    context.move_to(x + width, y + 1)
    context.line_to(x + 1, y + 1)
    context.line_to(x + 1, y + height)
    context.set_source_rgb(*light)
    context.stroke()
    context.move_to(x + width - 1, y)
    context.line_to(x + width - 1, y + height - 1)
    context.line_to(x, y + height - 1)
    context.set_source_rgb(*shade)
    context.stroke()


def _paint_rivet(context, x, y, radius=4.0):
    """Paint one square-backed, faceted Minecraft-style bolt."""
    plate = radius + 3
    _rectangle(
        context, x - plate, y - plate, plate * 2, plate * 2,
        0.25, 0.26, 0.25,
    )
    _paint_bevel(
        context, x - plate, y - plate, plate * 2, plate * 2,
    )
    context.arc(x + 1, y + 1, radius, 0, math.tau)
    context.set_source_rgb(0.055, 0.058, 0.056)
    context.fill()
    context.arc(x, y, radius, 0, math.tau)
    context.set_source_rgb(0.52, 0.53, 0.50)
    context.fill()
    context.arc(x, y, radius, 0, math.tau)
    context.set_source_rgb(0.08, 0.085, 0.08)
    context.set_line_width(1.2)
    context.stroke()
    context.arc(x - 1.3, y - 1.3, radius * 0.34, 0, math.tau)
    context.set_source_rgb(0.88, 0.89, 0.84)
    context.fill()
    context.arc(x + 0.8, y + 0.8, max(0.8, radius * 0.22), 0, math.tau)
    context.set_source_rgb(0.20, 0.21, 0.20)
    context.fill()


def _paint_hud_frame(context, x, y, width, height, *, compact=False,
                     fill_face=True):
    """Paint the stepped violet/cyan chassis used by HUD icon plates."""
    if width < 42 or height < 42:
        return
    edge = 12.0 if compact else 17.0
    corner = 13.0 if compact else 17.0
    right = x + width
    bottom = y + height

    # A hard offset shadow and multiple square rails reproduce the layered,
    # extruded construction in the artwork without any scale-blurred assets.
    if fill_face:
        _rectangle(context, x + 6, y + 7, width - 4, height - 4,
                   0.025, 0.025, 0.045, 0.88)
        _rectangle(context, x + 3, y + 2, width - 8, height - 8,
                   0.08, 0.055, 0.13)
    else:
        _rectangle(context, x + 3, y + 2, width - 8, 8,
                   0.08, 0.055, 0.13)
        _rectangle(context, x + 3, bottom - 11, width - 8, 8,
                   0.045, 0.035, 0.075)
        _rectangle(context, x + 3, y + 10, 8, height - 21,
                   0.08, 0.055, 0.13)
        _rectangle(context, right - 11, y + 10, 8, height - 21,
                   0.035, 0.028, 0.06)
    _paint_bevel(context, x + 3, y + 2, width - 8, height - 8, heavy=True)
    _rectangle(context, x + 7, y + 5, width - 16, 3,
               0.55, 0.24, 0.82)
    _rectangle(context, x + 7, bottom - 10, width - 16, 3,
               0.20, 0.10, 0.34)
    _rectangle(context, x + 6, y + 8, 3, height - 18,
               0.31, 0.15, 0.52)
    _rectangle(context, right - 11, y + 8, 3, height - 18,
               0.08, 0.045, 0.15)

    # The face is inset behind a black lip, then picked out with the cyan and
    # magenta light strips visible on the gateway itself.
    if fill_face:
        _rectangle(context, x + edge - 3, y + edge - 3,
                   width - edge * 2 + 6, height - edge * 2 + 6,
                   0.035, 0.030, 0.060)
        _rectangle(context, x + edge, y + edge,
                   width - edge * 2, height - edge * 2,
                   0.145, 0.135, 0.225)
    else:
        _rectangle(context, x + edge - 3, y + edge - 3,
                   width - edge * 2 + 6, 3, 0.035, 0.030, 0.060)
        _rectangle(context, x + edge - 3, bottom - edge,
                   width - edge * 2 + 6, 3, 0.035, 0.030, 0.060)
        _rectangle(context, x + edge - 3, y + edge,
                   3, height - edge * 2, 0.035, 0.030, 0.060)
        _rectangle(context, right - edge, y + edge,
                   3, height - edge * 2, 0.035, 0.030, 0.060)
    _rectangle(context, x + edge - 2, y + edge - 2,
               width - edge * 2 + 4, 3, 0.08, 0.89, 0.88)
    _rectangle(context, x + edge - 2, y + edge + 1,
               3, height - edge * 2 + 1, 0.08, 0.79, 0.81)
    # Keep the complete inner aperture illuminated.  Dark violet lower/right
    # strips disappeared against the face once the top-right controls were
    # reduced to their compact size, making an intact frame look clipped.
    _rectangle(context, right - edge - 1, y + edge + 1,
               3, height - edge * 2 + 1, 0.08, 0.79, 0.81)
    _rectangle(context, x + edge + 1, bottom - edge - 1,
               width - edge * 2 - 1, 3, 0.08, 0.89, 0.88)

    # Square clamps intentionally interrupt every rail. They are decorative;
    # hit testing remains that of the ordinary GTK button beneath them.
    clamps = (
        (x + 2, y + 2),
        (right - corner - 2, y + 2),
        (x + 2, bottom - corner - 2),
        (right - corner - 2, bottom - corner - 2),
    )
    for clamp_x, clamp_y in clamps:
        _rectangle(context, clamp_x, clamp_y, corner, corner,
                   0.17, 0.15, 0.23)
        _paint_bevel(context, clamp_x, clamp_y, corner, corner)
        _rectangle(context, clamp_x + 2, clamp_y + 2, 4, 3,
                   0.13, 0.78, 0.79)
        _rectangle(context, clamp_x + corner - 6, clamp_y + 3, 3, 4,
                   0.43, 0.19, 0.62)
        _paint_rivet(
            context,
            clamp_x + corner / 2,
            clamp_y + corner / 2,
            1.45 if compact else 1.8,
        )


def _paint_hud_menu_surface(snapshot, width, height):
    if width < 80 or height < 60:
        return
    context = snapshot.append_cairo(Graphene.Rect().init(0, 0, width, height))
    _rectangle(context, 5, 6, width - 5, height - 5, 0.02, 0.025, 0.04, 0.88)
    _rectangle(context, 1, 1, width - 7, height - 7, 0.19, 0.19, 0.22)
    _rectangle(context, 12, 13, width - 30, height - 29, 0.12, 0.12, 0.15)


def _paint_hud_menu_frame(snapshot, width, height):
    if width < 80 or height < 60:
        return
    context = snapshot.append_cairo(Graphene.Rect().init(0, 0, width, height))
    right = width - 7
    bottom = height - 7
    rail = 11
    _rectangle(context, 1, 1, right, rail, 0.27, 0.27, 0.30)
    _rectangle(context, 1, bottom - rail, right, rail, 0.13, 0.14, 0.15)
    _rectangle(context, 1, rail, rail, bottom - rail * 2, 0.23, 0.24, 0.25)
    _rectangle(context, right - rail, rail, rail, bottom - rail * 2,
               0.09, 0.09, 0.11)
    _rectangle(context, 4, 2, right - 8, 2, 0.15, 0.91, 0.88)
    _rectangle(context, 17, 5, right - 34, 3, 0.57, 0.23, 0.78)
    _rectangle(context, 4, 5, 3, bottom - 10, 0.48, 0.49, 0.48)
    _rectangle(context, right - 6, 5, 3, bottom - 10, 0.035, 0.04, 0.05)
    _rectangle(context, 4, bottom - 7, right - 8, 4, 0.045, 0.05, 0.055)
    _paint_bevel(context, 11, 11, right - 22, bottom - 22, inset=True, heavy=True)
    for rivet_x, rivet_y in (
        (10, 10), (right - 10, 10),
        (right - 10, bottom - 10), (10, bottom - 10),
    ):
        _paint_rivet(context, rivet_x, rivet_y, 2.5)


def _paint_hud_menu_stem(snapshot, width, height, source_width):
    if width < source_width or height < 12:
        return
    context = snapshot.append_cairo(Graphene.Rect().init(0, 0, width, height))
    stem_width = 28.0
    # Gtk.Popover aligns the right edge of this content with the right edge of
    # its source button.  Inset the narrower stem by the remaining button width
    # so its vertical axis, rather than its right edge, meets the icon center.
    center = max(stem_width / 2, width - source_width + stem_width / 2)
    _rectangle(context, center - stem_width / 2 + 4, 3,
               stem_width, height, 0.02, 0.025, 0.045, 0.85)
    _rectangle(context, center - stem_width / 2, 0,
               stem_width, height, 0.16, 0.14, 0.22)
    _paint_bevel(context, center - stem_width / 2, 0,
                 stem_width, height + 5, heavy=True)
    _rectangle(context, center - 5, 0, 3, height,
               0.10, 0.83, 0.82)
    _rectangle(context, center + 3, 0, 3, height,
               0.45, 0.18, 0.65)
    _paint_rivet(context, center, height - 5, 2.4)


def _paint_panel(snapshot, width, height, kind):
    if width < 8 or height < 8:
        return
    context = snapshot.append_cairo(Graphene.Rect().init(0, 0, width, height))
    dark = kind in {"header", "well", "footer"}
    _paint_block_texture(context, 0, 0, width, height, dark=dark)
    inset = kind == "well"
    _paint_bevel(context, 0, 0, width, height, inset=inset, heavy=True)
    if kind == "well":
        _rectangle(context, 5, 5, width - 10, 3, 0.035, 0.038, 0.036)
        _rectangle(
            context, 5, height - 8, width - 10, 3,
            0.37, 0.38, 0.35, 0.72,
        )
    elif kind in {"header", "footer"}:
        _rectangle(
            context, 5, height - 5, width - 10, 2,
            0.035, 0.038, 0.036, 0.9,
        )


def _paint_panel_hardware(snapshot, width, height, kind):
    if width < 28 or height < 22:
        return
    context = snapshot.append_cairo(Graphene.Rect().init(0, 0, width, height))
    if kind == "header":
        for x, y in ((9, 9), (width - 9, 9)):
            _paint_rivet(context, x, y, 2.7)
    elif kind == "footer":
        # Short nameplate: keep the rivets on the caption midline.
        rivet_y = height / 2.0
        for x in (12, width - 12):
            _paint_rivet(context, x, rivet_y, 2.7)
    elif kind == "well":
        # Square notches make the recessed menu read as a fitted iron tray.
        for x, y in ((4, 4), (width - 10, 4), (4, height - 10),
                     (width - 10, height - 10)):
            _rectangle(context, x, y, 6, 6, 0.07, 0.075, 0.07)


def paint_board_surface(snapshot, width, height):
    """Lay a low-contrast block texture over the board's CSS base."""
    if width < 48 or height < 48:
        return
    context = snapshot.append_cairo(Graphene.Rect().init(0, 0, width, height))
    _paint_block_texture(context, 0, 0, width, height)
    # Slightly darker inner field leaves the surrounding rails prominent.
    _rectangle(context, 18, 22, width - 36, height - 44, 0.18, 0.185, 0.18, 0.28)


def paint_board_frame(snapshot, width, height):
    """Paint the stepped stone-and-iron perimeter over the board contents."""
    if width < 64 or height < 64:
        return
    context = snapshot.append_cairo(Graphene.Rect().init(0, 0, width, height))
    rail = 15.0
    # Four rails, with bright upper/left faces and nearly black lower faces.
    _rectangle(context, 0, 0, width, rail, 0.30, 0.31, 0.30)
    _rectangle(context, 0, height - rail, width, rail, 0.20, 0.205, 0.20)
    _rectangle(context, 0, rail, rail, height - rail * 2, 0.255, 0.26, 0.25)
    _rectangle(
        context, width - rail, rail, rail, height - rail * 2,
        0.16, 0.165, 0.16,
    )
    _rectangle(context, 3, 3, width - 6, 3, 0.62, 0.63, 0.60, 0.76)
    _rectangle(context, 3, 6, 3, height - 12, 0.50, 0.51, 0.48, 0.72)
    _rectangle(context, 3, height - 7, width - 6, 4, 0.045, 0.048, 0.045)
    _rectangle(context, width - 7, 3, 4, height - 6, 0.055, 0.058, 0.055)
    _paint_bevel(context, rail - 1, rail - 1, width - rail * 2 + 2,
                 height - rail * 2 + 2, inset=True, heavy=True)

    # Blocky corner armour and joints break up the otherwise perfect rectangle.
    corner = 27
    for x, y, flip_x, flip_y in (
        (0, 0, 1, 1),
        (width, 0, -1, 1),
        (width, height, -1, -1),
        (0, height, 1, -1),
    ):
        context.move_to(x, y)
        context.line_to(x + flip_x * corner, y)
        context.line_to(x + flip_x * corner, y + flip_y * 8)
        context.line_to(x + flip_x * 18, y + flip_y * 8)
        context.line_to(x + flip_x * 18, y + flip_y * corner)
        context.line_to(x, y + flip_y * corner)
        context.close_path()
        context.set_source_rgb(0.29, 0.30, 0.29)
        context.fill()

    # Short seams and chips keep the frame closer to forged game UI than a
    # modern, smooth dialog border.
    context.set_line_width(2)
    context.set_source_rgba(0.09, 0.095, 0.09, 0.76)
    for start, end in (
        ((41, 8), (85, 8)),
        ((width - 104, 11), (width - 58, 11)),
        ((7, 78), (7, 121)),
        ((width - 8, height * 0.55), (width - 8, height * 0.63)),
        ((52, height - 7), (109, height - 7)),
    ):
        context.move_to(*start)
        context.line_to(*end)
        context.stroke()

    inset = BOARD_RIVET_INSET
    for x, y in (
        (inset, inset),
        (width - inset, inset),
        (width - inset, height - inset),
        (inset, height - inset),
    ):
        _paint_rivet(context, x, y, 4.2)

    # Tall mounting plates give each chain a load-bearing connection on a
    # vertical rail. The link itself is behind the board and disappears under
    # this hardware, while the central fastener remains visibly in front.
    side = BOARD_CHAIN_ANCHOR_SIDE_INSET
    end = BOARD_CHAIN_ANCHOR_END_INSET
    for x, y in (
        (side, end),
        (width - side, end),
        (width - side, height - end),
        (side, height - end),
    ):
        connector_x = 0.0 if x == side else width - side
        _rectangle(
            context, connector_x, y - 5, side, 10,
            0.12, 0.045, 0.25,
        )
        _rectangle(
            context, connector_x, y - 3, side, 3,
            0.33, 0.18, 0.55,
        )
        _rectangle(
            context, connector_x, y - 3, side, 1,
            0.31, 0.76, 0.76, 0.78,
        )
        mount_width = 14.0
        mount_height = 20.0
        _rectangle(
            context,
            x - mount_width / 2,
            y - mount_height / 2,
            mount_width,
            mount_height,
            0.24,
            0.25,
            0.24,
        )
        _paint_bevel(
            context,
            x - mount_width / 2,
            y - mount_height / 2,
            mount_width,
            mount_height,
            heavy=True,
        )
        _paint_rivet(context, x, y, 3.2)


def paint_button_hardware(snapshot, width, height, kind):
    """Add corner clamps without changing the button's GTK allocation."""
    if kind not in {"request", "cancel", "hud", "hud-menu-item"} or width < 36 or height < 28:
        return
    context = snapshot.append_cairo(Graphene.Rect().init(0, 0, width, height))
    if kind == "hud":
        # Paint in a doubled logical coordinate space so the complete HUD
        # chassis—including rails, clamps, bevels, and rivets—is half as
        # thick without changing the GTK button allocation.
        context.scale(0.5, 0.5)
        _paint_hud_frame(
            context, 0, 0, width * 2, height * 2, fill_face=False,
        )
        return
    if kind == "hud-menu-item":
        _rectangle(context, 0, 0, width, 4, 0.48, 0.48, 0.52)
        _rectangle(context, 0, height - 4, width, 4, 0.055, 0.055, 0.07)
        _rectangle(context, 0, 0, 4, height, 0.35, 0.35, 0.39)
        _rectangle(context, width - 4, 0, 4, height, 0.06, 0.06, 0.08)
        _rectangle(context, 5, 5, width - 10, 2, 0.58, 0.24, 0.76)
        _rectangle(context, 5, 7, 2, height - 14, 0.10, 0.79, 0.78)
        _rectangle(context, width - 7, 7, 2, height - 14, 0.28, 0.12, 0.40)
        _paint_bevel(context, 4, 4, width - 8, height - 8, inset=True)
        for rivet_x, rivet_y in (
            (7, 7), (width - 7, 7),
            (width - 7, height - 7), (7, height - 7),
        ):
            _paint_rivet(context, rivet_x, rivet_y, 1.35)
        return
    size = min(14.0, height * 0.28)
    colour = (0.31, 0.32, 0.30) if kind == "cancel" else (0.27, 0.30, 0.25)
    rivet_radius = 2.2
    if kind == "request":
        # The reference uses a green inset held inside a separate iron cage.
        # Paint that cage over the normal button so hit testing and allocation
        # remain those of one ordinary GTK control.
        _rectangle(context, 0, 0, width, 4, *colour)
        _rectangle(context, 0, height - 4, width, 4, 0.10, 0.12, 0.09)
        _rectangle(context, 0, 0, 4, height, 0.39, 0.42, 0.36)
        _rectangle(context, width - 4, 0, 4, height, 0.10, 0.12, 0.09)
        _rectangle(context, 4, 4, width - 8, 1, 0.70, 0.73, 0.64, 0.72)
    for x, y in ((0, 0), (width - size, 0), (0, height - size),
                 (width - size, height - size)):
        _rectangle(context, x, y, size, size, *colour)
        _paint_bevel(context, x, y, size, size)
        _paint_rivet(context, x + size / 2, y + size / 2, rivet_radius)


class MetalPanel(Gtk.Box):
    """A textured layout panel whose visual chrome has no layout cost."""

    __gtype_name__ = "OhNoMetalPanel"

    def __init__(self, *args, panel_kind="metal", **kwargs):
        super().__init__(*args, **kwargs)
        self._panel_kind = panel_kind

    def do_snapshot(self, snapshot):
        width = self.get_width()
        height = self.get_height()
        _paint_panel(snapshot, width, height, self._panel_kind)
        Gtk.Box.do_snapshot(self, snapshot)
        _paint_panel_hardware(snapshot, width, height, self._panel_kind)


class ArmoredButton(Gtk.Button):
    """A normal GTK button with decorative, non-interactive corner clamps."""

    __gtype_name__ = "OhNoArmoredButton"

    def __init__(self, *args, armor_kind="request", **kwargs):
        super().__init__(*args, **kwargs)
        self._armor_kind = armor_kind

    def do_snapshot(self, snapshot):
        Gtk.Button.do_snapshot(self, snapshot)
        paint_button_hardware(
            snapshot, self.get_width(), self.get_height(), self._armor_kind,
        )


class ArmoredMenuButton(Gtk.MenuButton):
    """A GTK menu button with the same iron clamps as ``ArmoredButton``."""

    __gtype_name__ = "OhNoArmoredMenuButton"

    def __init__(self, *args, armor_kind="hud", **kwargs):
        super().__init__(*args, **kwargs)
        self._armor_kind = armor_kind

    def do_snapshot(self, snapshot):
        Gtk.MenuButton.do_snapshot(self, snapshot)
        paint_button_hardware(
            snapshot, self.get_width(), self.get_height(), self._armor_kind,
        )


class HudIconFrame(Gtk.Overlay):
    """A compact illuminated HUD chassis around a pixel-art menu icon."""

    __gtype_name__ = "OhNoHudIconFrame"

    def __init__(self, pixels, *, display_size=28):
        super().__init__(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.set_size_request(54, 54)
        self.add_css_class("oh-no-parent-control-hud-menu-icon")
        icon = PixelIcon(pixels, display_size=display_size, label="")
        icon.set_halign(Gtk.Align.CENTER)
        icon.set_valign(Gtk.Align.CENTER)
        self.set_child(icon)

    def do_snapshot(self, snapshot):
        width = self.get_width()
        height = self.get_height()
        context = snapshot.append_cairo(Graphene.Rect().init(0, 0, width, height))
        _paint_hud_frame(context, 0, 0, width, height, compact=True)
        Gtk.Overlay.do_snapshot(self, snapshot)


class HudMenuStem(Gtk.Widget):
    """Decorative bracket joining the menu plate to its source button."""

    __gtype_name__ = "OhNoHudMenuStem"

    def __init__(self, *, source_width=66):
        super().__init__(hexpand=True)
        self._source_width = source_width
        self.set_size_request(-1, 28)
        self.set_can_target(False)

    def do_snapshot(self, snapshot):
        _paint_hud_menu_stem(
            snapshot, self.get_width(), self.get_height(), self._source_width,
        )


class HudMenuBoard(Gtk.Box):
    """The dark, neon-trimmed plate holding the expanded HUD actions."""

    __gtype_name__ = "OhNoHudMenuBoard"

    def do_snapshot(self, snapshot):
        width = self.get_width()
        height = self.get_height()
        _paint_hud_menu_surface(snapshot, width, height)
        Gtk.Box.do_snapshot(self, snapshot)
        _paint_hud_menu_frame(snapshot, width, height)


class MetalBoard(Gtk.Box):
    """GTK box that paints Minecraft-style stone and iron around its content."""

    __gtype_name__ = "OhNoMetalBoard"

    def do_snapshot(self, snapshot):
        paint_board_surface(snapshot, self.get_width(), self.get_height())
        Gtk.Box.do_snapshot(self, snapshot)
        paint_board_frame(snapshot, self.get_width(), self.get_height())
