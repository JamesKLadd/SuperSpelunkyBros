"""tools/build_assets.py: the generated hero sheet and blank level files."""

import importlib.util
import pathlib
import re

import pytest
from PIL import Image

from conftest import PACK

spec = importlib.util.spec_from_file_location("build_assets", PACK / "tools" / "build_assets.py")
build_assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_assets)


@pytest.fixture(scope="module")
def sheet(tmp_path_factory):
    path = tmp_path_factory.mktemp("assets") / "hero.png"
    build_assets.build_hero(path)
    return Image.open(path).convert("RGBA")


def cell(sheet, col, row):
    return sheet.crop((col * 128, row * 128, (col + 1) * 128, (row + 1) * 128))


def test_the_sheet_is_a_vanilla_character_sheet_shape(sheet):
    """src/assets.lua reuses the vanilla definition: 2048 x 2048 in 128-pixel cells."""
    assert sheet.size == (2048, 2048)


# (column, row) of cells the engine reads for a character, from modlunky2's
# character sheet map: one from every animation the hero can be in.
USED = {
    "standing": (0, 0), "walk first": (1, 0), "walk last": (8, 0), "knocked out": (9, 0),
    "duck": (2, 1), "crawl": (5, 1), "stun": (0, 2), "flip": (4, 2), "hold": (11, 2),
    "teeter": (0, 3), "ledge": (8, 3), "whip": (0, 4), "throw": (6, 4), "enter": (0, 5),
    "exit": (11, 5), "ladder": (0, 6), "push": (6, 6), "rope climb": (0, 7), "look up": (0, 8),
    "jump first": (0, 9), "jump last": (11, 9), "rope coiled": (12, 9), "ghost": (0, 10),
    "icon": (0, 11), "skid (ours)": (11, 11), "rope segment": (0, 12), "whip item": (15, 12),
    "stars": (0, 13), "petting": (0, 14), "portrait": (13, 3),
}


@pytest.mark.parametrize("name", USED)
def test_the_cell_is_drawn(sheet, name):
    col, row = USED[name]
    assert cell(sheet, col, row).getbbox() is not None, f"{name} cell ({col}, {row}) is empty"


def test_the_skid_frame_matches_hero_lua():
    src = (PACK / "src" / "hero.lua").read_text(encoding="utf-8")
    assert "local SKID_FRAME = 11 * 16 + 11" in src
    assert USED["skid (ours)"] == (11, 11)


def test_the_hero_stands_on_the_engine_feet_line(sheet):
    """The engine draws the feet 17/128 up from the bottom of the cell."""
    box = cell(sheet, 0, 0).getbbox()
    assert 110 <= box[3] <= 118, f"standing sprite's lowest pixel row is {box[3]}"
    assert 40 <= (box[0] + box[2]) / 2 <= 88, "roughly centred"


def test_pixels_are_crisp(sheet):
    """Drawn at 32 x 32 and enlarged 4x: every 4 x 4 block is one colour."""
    stand = cell(sheet, 0, 0)
    small = stand.resize((32, 32), Image.NEAREST)
    assert small.resize((128, 128), Image.NEAREST).tobytes() == stand.tobytes()


def test_the_build_is_deterministic(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    build_assets.build_hero(a)
    build_assets.build_hero(b)
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("height", range(2, 15, 2))
def test_blank_levels(tmp_path, height):
    build_assets.build_levels(tmp_path)
    text = (tmp_path / f"ssb_blank_8x{height}.lvl").read_text(encoding="utf-8")
    assert f"\\-size 8 {height}" in text
    assert "\\?empty 0" in text and "\\?entrance 9" in text
    templates = re.findall(r"^\\\.setroom(\d+)_(\d+)\n((?:[0-9]{10}\n){8})", text, flags=re.M)
    assert len(templates) == 8 * height, "one 10 x 8 room per cell of the level"
    assert {(int(y), int(x)) for y, x, _ in templates} == {(y, x) for y in range(height) for x in range(8)}
    cells = "".join(rows for _, _, rows in templates)
    assert cells.count("9") == 1, "exactly one entrance"
    assert set(cells) <= set("09\n")


def test_the_entrance_is_at_the_level_start(tmp_path):
    """The door must be where src/levelgrid.lua says every level starts."""
    src = (PACK / "src" / "levelgrid.lua").read_text(encoding="utf-8")
    col = int(re.search(r"Grid\.START_COL = (\d+)", src).group(1))
    row = int(re.search(r"Grid\.START_ROW = (\d+)", src).group(1))
    assert (build_assets.START_COL, build_assets.START_ROW) == (col, row)
    build_assets.build_levels(tmp_path)
    text = (tmp_path / "ssb_blank_8x4.lvl").read_text(encoding="utf-8")
    room = re.search(rf"\\\.setroom{row // 8}_{col // 10}\n((?:[0-9]{{10}}\n){{8}})", text).group(1).split("\n")
    assert room[row % 8][col % 10] == "9"


def test_level_lua_asks_for_a_file_this_script_writes(tmp_path):
    src = (PACK / "src" / "level.lua").read_text(encoding="utf-8")
    assert 'string.format("ssb_blank_8x%d.lvl", strips * 2)' in src
    names = {p.name for p in build_assets.build_levels(tmp_path)}
    assert names == {f"ssb_blank_8x{h}.lvl" for h in range(2, 15, 2)}
