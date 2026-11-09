#!/usr/bin/env python3
"""Build every generated file the mod needs. Run from anywhere:

    python tools/build_assets.py

Writes into the pack folder (the parent of tools/):

    res/hero.png                     the hero, in a vanilla character-sheet layout
    Data/Levels/ssb_blank_8x<h>.lvl  empty levels the Lua side fills with tiles

Everything written here is ignored by git: the repository holds this script, not
its output. The output is deterministic, so two machines build identical files.

Needs Pillow (`pip install pillow`).

Art is original and drawn by this script from the pose tables below. Nothing is
read from any game's files.
"""

from __future__ import annotations

import argparse
import math
import pathlib

from PIL import Image, ImageDraw

PACK = pathlib.Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------- hero
#
# A vanilla character sheet is 2048 x 2048: a 16 x 16 grid of 128-pixel cells.
# Each cell here is drawn on a 32 x 32 canvas and enlarged 4x without smoothing,
# so one drawn pixel is a crisp 4 x 4 block in game.
#
# The engine draws a character cell 1.25 tiles wide with the feet 17/128 of the
# way up from the bottom edge, which is row 28 of the 32-pixel canvas. Soles end on
# row FEET; the outline below them sits on that line.

CELL = 128
GRID = 16
ART = 32
SCALE = CELL // ART
FEET = 27
CENTER = 16

OUTLINE = (24, 20, 37, 255)
HELMET = (247, 198, 52, 255)
HELMET_DARK = (214, 150, 30, 255)
LAMP = (255, 250, 210, 255)
SKIN = (240, 190, 150, 255)
JACKET = (48, 150, 160, 255)
JACKET_DARK = (32, 105, 120, 255)
SCARF = (150, 80, 190, 255)
PANTS = (110, 80, 60, 255)
BOOT = (60, 45, 40, 255)
GLOVE = (230, 230, 220, 255)
ROPE = (196, 160, 100, 255)
ROPE_DARK = (150, 115, 70, 255)
WHIP = (120, 70, 40, 255)
STAR = (255, 230, 90, 255)
GHOST = (200, 225, 255, 180)
PAPER = (232, 214, 170, 255)


def blank() -> Image.Image:
    return Image.new("RGBA", (ART, ART), (0, 0, 0, 0))


def limb(draw: ImageDraw.ImageDraw, x: float, y: float, angle: float, length: float, color) -> tuple[int, int]:
    """A 2-pixel-thick limb from (x, y). Angle 0 points down, 90 forward, 180 up."""
    rad = math.radians(angle)
    ex = x + math.sin(rad) * length
    ey = y + math.cos(rad) * length
    draw.line([(round(x), round(y)), (round(ex), round(ey))], fill=color, width=2)
    return round(ex), round(ey)


def outline(img: Image.Image) -> Image.Image:
    """Add a one-pixel dark outline around everything drawn."""
    src = img.load()
    out = img.copy()
    dst = out.load()
    for y in range(ART):
        for x in range(ART):
            if src[x, y][3] != 0:
                continue
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < ART and 0 <= ny < ART and src[nx, ny][3] != 0:
                    dst[x, y] = OUTLINE
                    break
    return out


def settle(img: Image.Image) -> Image.Image:
    """Move the drawing down (or up) so its lowest pixel rests on the feet line."""
    box = img.getbbox()
    if box is None:
        return img
    out = blank()
    out.paste(img, (0, FEET - box[3]))
    return out


def doll(
    legs=(0, 0),
    arms=(10, -10),
    crouch=0.0,
    rot=0.0,
    ox=0,
    oy=0,
    view="side",
    eyes="open",
    look_up=0.0,
    no_legs=False,
    rest=False,
    shade=0.0,
) -> Image.Image:
    """Draw the hero in one pose.

    legs / arms: (front, back) angles in degrees, see limb().
    crouch: 0 standing .. 1 fully ducked.
    rot: whole-body rotation, counter-clockwise, about the body centre.
    view: "side" (faces right; the engine mirrors it) or "back".
    rest: after rotating, drop the body onto the ground line.
    shade: 0 .. 1 darkening, for walking into a doorway.
    """
    img = blank()
    d = ImageDraw.Draw(img)
    cx = CENTER + ox
    base = FEET + oy
    leg_len = 5 - round(3 * crouch)
    hip_y = base - leg_len
    torso_h = 6 - round(crouch)
    shoulder_y = hip_y - torso_h
    head_top = shoulder_y - 8 + round(look_up)
    head_x = cx - round(look_up)

    # back arm, back leg
    limb(d, cx, shoulder_y + 1, arms[1], 5, JACKET_DARK)
    if not no_legs:
        fx, fy = limb(d, cx - 1, hip_y, legs[1], leg_len - 1, PANTS)
        d.rectangle([fx - 1, fy, fx + 1, fy + 1], fill=BOOT)

    # torso and scarf
    d.rectangle([cx - 3, shoulder_y, cx + 2, hip_y], fill=JACKET)
    d.rectangle([cx - 3, hip_y - 1, cx + 2, hip_y], fill=JACKET_DARK)
    d.rectangle([cx - 3, shoulder_y, cx + 2, shoulder_y], fill=SCARF)
    if view == "back":
        d.rectangle([cx - 1, shoulder_y + 1, cx, shoulder_y + 3], fill=SCARF)
    else:
        d.point([(cx - 4, shoulder_y + 1), (cx - 5, shoulder_y + 2)], fill=SCARF)

    # front leg
    if not no_legs:
        fx, fy = limb(d, cx + 1, hip_y, legs[0], leg_len - 1, PANTS)
        d.rectangle([fx - 1, fy, fx + 2, fy + 1], fill=BOOT)

    # head: face, then the helmet over its top half
    d.rectangle([head_x - 3, head_top + 1, head_x + 3, head_top + 7], fill=SKIN)
    d.rectangle([head_x - 4, head_top + 2, head_x + 4, head_top + 6], fill=SKIN)
    if view == "back":
        d.rectangle([head_x - 4, head_top, head_x + 4, head_top + 5], fill=HELMET)
        d.rectangle([head_x - 4, head_top + 5, head_x + 4, head_top + 5], fill=HELMET_DARK)
    else:
        d.rectangle([head_x - 4, head_top, head_x + 4, head_top + 3], fill=HELMET)
        d.rectangle([head_x - 4, head_top + 3, head_x + 5, head_top + 3], fill=HELMET_DARK)
        d.rectangle([head_x + 3, head_top + 1, head_x + 4, head_top + 2], fill=LAMP)
        eye_y = head_top + 5 - round(look_up)
        if eyes == "open":
            d.rectangle([head_x + 2, eye_y - 1, head_x + 2, eye_y], fill=OUTLINE)
        elif eyes == "closed":
            d.rectangle([head_x + 1, eye_y, head_x + 3, eye_y], fill=OUTLINE)
        else:  # "x": knocked out
            d.point([(head_x + 1, eye_y - 1), (head_x + 3, eye_y - 1), (head_x + 2, eye_y),
                     (head_x + 1, eye_y + 1), (head_x + 3, eye_y + 1)], fill=OUTLINE)

    # front arm and glove
    hx, hy = limb(d, cx, shoulder_y + 1, arms[0], 5, JACKET)
    d.rectangle([hx, hy, hx + 1, hy + 1], fill=GLOVE)

    if rot:
        img = img.rotate(rot, resample=Image.NEAREST, center=(CENTER, FEET - 9))
    if rest:
        img = settle(img)
    img = outline(img)
    if shade > 0:
        dark = Image.new("RGBA", img.size, (0, 0, 0, 255))
        mask = img.getchannel("A").point(lambda a: int(a * shade))
        img = Image.composite(dark, img, mask)
        img.putalpha(Image.eval(img.getchannel("A"), lambda a: a))
    return img


def swing(i: int, n: int, amount: float) -> float:
    """A smooth back-and-forth over n frames."""
    return amount * math.sin(2 * math.pi * i / n)


def ghost(i: int) -> Image.Image:
    """The hero as a ghost: pale, legless, with a wavy hem that drifts."""
    body = doll(no_legs=True, arms=(40, -40), eyes="closed", oy=-3 + round(swing(i, 16, 1.5)))
    alpha = body.getchannel("A")
    img = Image.new("RGBA", body.size, GHOST)
    img.putalpha(alpha.point(lambda a: 180 if a else 0))
    d = ImageDraw.Draw(img)
    for x in range(CENTER - 4, CENTER + 4):
        wave = round(1.5 * math.sin((x + i) * 1.2))
        d.line([(x, FEET - 7), (x, FEET - 4 + wave)], fill=GHOST)
    return img


def rope_piece(kind: str, i: int = 0) -> Image.Image:
    img = blank()
    d = ImageDraw.Draw(img)

    def strand(y0, y1):
        d.rectangle([CENTER - 1, y0, CENTER, y1], fill=ROPE)
        for y in range(y0, y1 + 1, 3):
            d.point((CENTER - 1 + (y // 3) % 2, y), fill=ROPE_DARK)

    if kind == "segment":
        strand(0, ART - 1)
    elif kind == "top":
        strand(12, ART - 1)
        d.rectangle([CENTER - 3, 9, CENTER + 2, 12], fill=ROPE_DARK)
        d.rectangle([CENTER - 2, 6, CENTER + 1, 9], fill=(170, 170, 180, 255))
    elif kind == "end":
        strand(0, 18)
        d.point([(CENTER - 2, 19), (CENTER + 1, 20), (CENTER - 1, 21)], fill=ROPE_DARK)
    elif kind == "short":
        strand(0, 14)
    elif kind == "coiled":
        d.ellipse([CENTER - 6, 14, CENTER + 5, 25], fill=ROPE)
        d.ellipse([CENTER - 3, 17, CENTER + 2, 22], fill=ROPE_DARK)
        return outline(img)
    elif kind == "uncoiling":
        size = 6 - i
        strand(0, 12 + i * 3)
        d.ellipse([CENTER - size, 12 + i * 3, CENTER + size - 1, 12 + i * 3 + size * 2 - 1], fill=ROPE)
        return outline(img)
    elif kind in ("burned", "burning"):
        strand(0, ART - 1 - i * 6 if kind == "burning" else 20)
        tip = ART - 1 - i * 6 if kind == "burning" else 20
        colour = (40, 36, 36, 255) if kind == "burned" else (255, 140, 40, 255)
        d.rectangle([CENTER - 2, max(tip - 2, 0), CENTER + 1, tip], fill=colour)
    return img


def whip_piece(i: int) -> Image.Image:
    """Six frames: coiled behind the hand, then unrolling to a straight lash."""
    img = blank()
    d = ImageDraw.Draw(img)
    y = 17
    reach = [5, 9, 14, 20, 27, 30][i]
    curl = [8, 6, 4, 2, 1, 0][i]
    points = []
    for step in range(reach + 1):
        t = step / max(reach, 1)
        points.append((1 + step, y - round(curl * math.sin(t * math.pi))))
    d.line(points, fill=WHIP, width=2)
    d.rectangle([0, y - 1, 2, y + 1], fill=OUTLINE)
    return img


def stars(i: int) -> Image.Image:
    """Three stars circling where the head is, for the stunned effect."""
    img = blank()
    d = ImageDraw.Draw(img)
    for k in range(3):
        angle = 2 * math.pi * (i / 12 + k / 3)
        x = CENTER + round(9 * math.cos(angle))
        y = 10 + round(3 * math.sin(angle))
        d.point([(x, y), (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)], fill=STAR)
    return outline(img)


def icon() -> Image.Image:
    """The head, large, for the HUD."""
    head = doll().crop((CENTER - 7, FEET - 21, CENTER + 8, FEET - 8))
    big = head.resize((head.width * 2, head.height * 2), Image.NEAREST)
    img = blank()
    img.paste(big, ((ART - big.width) // 2, (ART - big.height) // 2))
    return img


def simple(kind: str) -> Image.Image:
    img = blank()
    d = ImageDraw.Draw(img)
    if kind == "bag":
        d.rectangle([10, 14, 21, 25], fill=PANTS)
        d.rectangle([13, 11, 18, 14], fill=ROPE_DARK)
    elif kind == "wanted":
        d.rectangle([6, 4, 25, 27], fill=PAPER)
        small = doll().crop((CENTER - 7, FEET - 21, CENTER + 8, FEET - 8))
        img.paste(small, (9, 9), small)
    elif kind == "pointer":
        d.polygon([(CENTER, 22), (CENTER - 6, 12), (CENTER + 6, 12)], fill=HELMET)
    return outline(img)


def hero_cells() -> dict[tuple[int, int], Image.Image]:
    """Every cell of the sheet, keyed by (column, row), in the vanilla layout."""
    cells: dict[tuple[int, int], Image.Image] = {}

    def put(col: int, row: int, img: Image.Image) -> None:
        cells[(col, row)] = img

    walk = lambda i: doll(legs=(swing(i, 8, 38), -swing(i, 8, 38)),
                          arms=(-swing(i, 8, 45), swing(i, 8, 45)),
                          oy=-1 if i % 4 in (1, 2) else 0)

    # row 0: standing, walk cycle, knocked out, swimming
    put(0, 0, doll())
    for i in range(8):
        put(1 + i, 0, walk(i))
    put(9, 0, doll(rot=90, eyes="x", arms=(150, 30), rest=True))
    for i in range(6):
        put(10 + i, 0, doll(rot=-80, legs=(swing(i, 6, 30), -swing(i, 6, 30)),
                            arms=(160, 140), oy=-4))

    # row 1: ducking down, crawling
    for i, amount in enumerate((0.35, 0.7, 1.0, 1.0, 1.0)):
        put(i, 1, doll(crouch=amount, arms=(30, -10)))
    for i in range(7):
        put(5 + i, 1, doll(crouch=1.0, legs=(swing(i, 7, 50), -swing(i, 7, 50)), arms=(70, 40)))

    # row 2: knocked through the air, flipping, holding something out
    for i in range(4):
        put(i, 2, doll(rot=60 + i * 30, eyes="x", arms=(150, 60), legs=(30, -30)))
    for i in range(7):
        put(4 + i, 2, doll(rot=-(i + 1) * 45, legs=(60, 30), arms=(100, 60), oy=-3))
    put(11, 2, doll(arms=(90, -10)))

    # row 3: wobbling on an edge, hanging from one
    for i in range(8):
        put(i, 3, doll(rot=swing(i, 8, 9), arms=(120 + swing(i, 8, 30), -120)))
    for i in range(4):
        put(8 + i, 3, doll(arms=(175, 165), legs=(swing(i, 4, 15), swing(i, 4, 10)), oy=-2))

    # row 4: whipping, throwing
    for i, arm in enumerate((-130, -165, 160, 110, 85, 70)):
        put(i, 4, doll(arms=(arm, -20), legs=(15, -15)))
    for i, arm in enumerate((-120, 175, 115, 70, 35)):
        put(6 + i, 4, doll(arms=(arm, -20), legs=(20, -20)))

    # row 5: walking into a doorway (seen from behind, fading), and back out
    for i in range(6):
        put(i, 5, doll(view="back", legs=(swing(i, 6, 25), -swing(i, 6, 25)),
                       arms=(15, -15), shade=i / 6))
    for i in range(6):
        put(6 + i, 5, doll(legs=(swing(i, 6, 25), -swing(i, 6, 25)), shade=1 - (i + 1) / 6))

    # row 6: climbing a ladder (from behind), pushing
    for i in range(6):
        up = swing(i, 6, 30)
        put(i, 6, doll(view="back", arms=(150 + up, -150 + up), legs=(up, -up)))
    for i in range(6):
        put(6 + i, 6, doll(rot=-10, arms=(85, 80), legs=(swing(i, 6, 35), -swing(i, 6, 35))))

    # row 7: climbing a rope, ducking on a mount
    for i in range(10):
        up = swing(i, 10, 25)
        put(i, 7, doll(arms=(165 + up, 165 - up), legs=(40 + up, 20 - up)))
    for i, amount in enumerate((0.3, 0.6, 1.0, 1.0, 1.0)):
        put(10 + i, 7, doll(crouch=amount, legs=(70, 60)))

    # row 8: looking up, sitting, looking up while sitting
    for i in range(7):
        put(i, 8, doll(look_up=min(1.0, (i + 1) / 3)))
    put(7, 8, doll(crouch=1.0, legs=(80, 70), arms=(40, 20)))
    for i in range(7):
        put(8 + i, 8, doll(crouch=1.0, legs=(80, 70), arms=(40, 20), look_up=min(1.0, (i + 1) / 3)))

    # row 9: jumping (rising, top, falling), then rope items
    for i in range(12):
        if i < 4:
            pose = doll(legs=(55, -25), arms=(150, -40), oy=-1)
        elif i < 8:
            pose = doll(legs=(40, 20), arms=(120, -90), oy=-1)
        else:
            pose = doll(legs=(25, -35), arms=(165, -150), oy=-1)
        put(i, 9, pose)
    put(12, 9, rope_piece("coiled"))
    put(13, 9, rope_piece("top"))
    put(14, 9, rope_piece("short"))
    put(15, 9, rope_piece("burned"))

    # row 10: ghost
    for i in range(16):
        put(i, 10, ghost(i))

    # row 11: HUD icon, bag, wanted poster, pointer, riding, stunned ghost
    put(0, 11, icon())
    put(1, 11, simple("bag"))
    put(2, 11, simple("wanted"))
    put(3, 11, simple("pointer"))
    for i in range(6):
        put(4 + i, 11, doll(crouch=0.6, legs=(70, 60), arms=(150 + swing(i, 6, 25), 30)))
    put(10, 11, ghost(4))
    # (11, 11) is empty on vanilla sheets. Ours: the skid pose, src/hero.lua SKID_FRAME.
    put(11, 11, doll(rot=14, legs=(50, 25), arms=(-60, -100)))

    # row 12: rope pieces, whip
    put(0, 12, rope_piece("segment"))
    for i in range(4):
        put(1 + i, 12, rope_piece("uncoiling", i))
    put(5, 12, rope_piece("end"))
    for i in range(4):
        put(6 + i, 12, rope_piece("burning", i))
    for i in range(6):
        put(10 + i, 12, whip_piece(i))

    # row 13: stars around a stunned head
    for i in range(12):
        put(i, 13, stars(i))

    # row 14: petting
    for i in range(8):
        put(i, 14, doll(crouch=0.8, arms=(70 + swing(i, 8, 20), 10)))

    return cells


def build_hero(path: pathlib.Path) -> None:
    sheet = Image.new("RGBA", (CELL * GRID, CELL * GRID), (0, 0, 0, 0))
    for (col, row), img in hero_cells().items():
        big = img.resize((CELL, CELL), Image.NEAREST)
        sheet.paste(big, (col * CELL, row * CELL))
    # portrait: columns 12-15, rows 1-6. The standing pose, large.
    portrait = doll().crop((CENTER - 8, FEET - 22, CENTER + 8, FEET + 2))
    portrait = portrait.resize((portrait.width * 32, portrait.height * 32), Image.NEAREST)
    sheet.paste(portrait, (12 * CELL, 1 * CELL))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


# ------------------------------------------------------------------- levels
#
# The Lua side places every tile itself, so the .lvl files are empty rooms, one
# entrance and one exit. src/levelgrid.lua fixes where a level starts (START_COL, START_ROW);
# the entrance below is that cell: room row 1, room column 0, row 5, column 4.

ROOM_W, ROOM_H = 10, 8
START_COL, START_ROW = 4, 13
LEVEL_WIDTH_ROOMS = 8


# Level settings, copied from a level file known to load with CustomLevels
# (jaythebusinessgoose/ExampleKaizo). When a level file replaces the game's own,
# nothing supplies defaults for these, and every random-room and floor-spreading
# feature has to be switched off by hand.
LEVEL_SETTINGS = [
    ("altar_room_chance", "0"),
    ("back_room_chance", "0"),
    ("back_room_hidden_door_cache_chance", "0"),
    ("back_room_hidden_door_chance", "0"),
    ("back_room_interconnection_chance", "0"),
    ("flagged_liquid_rooms", "0"),
    ("floor_bottom_spread_chance", "0"),
    ("floor_side_spread_chance", "0"),
    ("idol_room_chance", "0"),
    ("machine_bigroom_chance", "0"),
    ("machine_rewardroom_chance", "0"),
    ("machine_tallroom_chance", "0"),
    ("machine_wideroom_chance", "0"),
    ("max_liquid_particles", "0"),
    ("mount_chance", "0"),
    ("background_chance", "10"),
    ("ground_background_chance", "10"),
]

# The exit door: the game expects every level to have one. It goes at the far end
# of the last strip, one column in from the edge, on the ground row.
# src/level.lua leaves this cell clear (Level.exit_cell).
EXIT_LOCAL_COL = LEVEL_WIDTH_ROOMS * ROOM_W - 2


def blank_level(height_rooms: int) -> str:
    lines = [
        "// Generated by tools/build_assets.py. Do not edit: edit the script.",
        "// Empty rooms, an entrance and an exit; src/level.lua fills in the tiles.",
        "",
    ]
    for name, value in LEVEL_SETTINGS:
        lines.append(f"\\-{name:<38} {value}")
    lines.append(f"\\-{'size':<38} {LEVEL_WIDTH_ROOMS} {height_rooms}")
    lines += [
        "",
        f"\\?{'empty':<32} 0",
        f"\\?{'floor':<32} 1",
        f"\\?{'entrance':<32} E",
        f"\\?{'exit':<32} e",
        "",
    ]
    exit_row = (height_rooms - 2) * ROOM_H + START_ROW
    for ry in range(height_rooms):
        for rx in range(LEVEL_WIDTH_ROOMS):
            lines.append(f"\\.setroom{ry}_{rx}")
            for row in range(ROOM_H):
                cells = ["0"] * ROOM_W
                gx, gy = rx * ROOM_W, ry * ROOM_H + row
                if gx <= START_COL < gx + ROOM_W and gy == START_ROW:
                    cells[START_COL - gx] = "E"
                if gx <= EXIT_LOCAL_COL < gx + ROOM_W and gy == exit_row:
                    cells[EXIT_LOCAL_COL - gx] = "e"
                lines.append("".join(cells))
            lines.append("")
    return "\n".join(lines)


def build_levels(folder: pathlib.Path) -> list[pathlib.Path]:
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for height in range(2, 15, 2):  # one to seven strips of two rooms
        path = folder / f"ssb_blank_8x{height}.lvl"
        path.write_text(blank_level(height), encoding="utf-8", newline="\n")
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=pathlib.Path, default=PACK,
                        help="pack folder to write into (default: this repository)")
    args = parser.parse_args()

    hero = args.out / "res" / "hero.png"
    build_hero(hero)
    print(f"wrote {hero}")
    for path in build_levels(args.out / "Data" / "Levels"):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
