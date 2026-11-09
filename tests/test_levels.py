"""Level grids and the strip layout (src/levelgrid.lua, src/levels/*)."""

import pathlib
import re

import pytest

from conftest import PACK

LEVELS = sorted(p.stem for p in (PACK / "src" / "levels").glob("*.lua"))

# src/camera.lua: the widest the view can be, in tiles, for a 16:9 picture.
ZF = 0.737
ZOOM = 7.0 / (ZF * 9.0 / 16.0)
VIEW_W = 2.0 * ZF * ZOOM


@pytest.fixture
def grid(pure_lua):
    return pure_lua.eval('(require("src.levelgrid"))')


@pytest.mark.parametrize("name", LEVELS)
def test_the_level_is_valid(pure_lua, grid, name):
    level = pure_lua.eval(f'(require("src.levels.{name}"))')
    problems = list(grid.validate(level).values())
    assert problems == []
    assert level.name == name


@pytest.mark.parametrize("name", LEVELS)
def test_only_known_cells(pure_lua, name):
    level = pure_lua.eval(f'(require("src.levels.{name}"))')
    for row in level.rows.values():
        assert set(row) <= set(".#B"), f"unknown cell in {row!r}"


def test_the_camera_constants_match_camera_lua():
    src = (PACK / "src" / "camera.lua").read_text(encoding="utf-8")
    assert "local ZF = 0.737" in src
    assert "Camera.ZOOM = 7.0 / (ZF * 9.0 / 16.0)" in src
    assert "Camera.VIEW_W = 2.0 * ZF * Camera.ZOOM" in src


def test_the_view_fits_inside_the_repeated_part(grid):
    """The seam is invisible only if everything on screen exists in both strips.

    At the moment of the cut the camera centre is at SEAM_LOCAL in the old strip
    and SEAM_LOCAL - STEP in the new one; the view around it must lie inside the
    columns the two strips share, and inside each strip.
    """
    half = VIEW_W / 2
    assert VIEW_W < grid.OVERLAP
    assert grid.SEAM_LOCAL - half >= grid.STEP - 0.5, "view starts before the shared columns"
    assert grid.SEAM_LOCAL + half <= grid.STRIP_W - 0.5, "view runs past the old strip"
    assert grid.SEAM_LOCAL - grid.STEP - half >= -0.5, "view starts before the new strip"


def test_strips_fit_the_engine_grid(grid):
    """The engine level is at most 8 rooms of 10 wide and 15 rooms of 8 tall."""
    assert grid.STRIP_W == 80
    assert grid.ROWS == 16
    assert grid.STEP + grid.OVERLAP == grid.STRIP_W


@pytest.mark.parametrize("width,strips", [(1, 1), (80, 1), (81, 2), (132, 2), (133, 3), (184, 3), (185, 4)])
def test_strip_count(grid, width, strips):
    assert grid.strip_count(width) == strips


@pytest.mark.parametrize("name", LEVELS)
def test_every_column_is_in_a_strip_and_neighbours_agree(pure_lua, grid, name):
    level = pure_lua.eval(f'(require("src.levels.{name}"))')
    strips = grid.strip_count(level.width)
    covered = set()
    for k in range(strips):
        origin = grid.strip_origin(k)
        covered.update(range(origin, origin + grid.STRIP_W))
        if k + 1 < strips:
            # the last OVERLAP columns of strip k are the first OVERLAP of strip k + 1
            nxt = grid.strip_origin(k + 1)
            assert origin + grid.STEP == nxt
    assert set(range(level.width)) <= covered


def test_past_the_end_of_a_level_is_solid(pure_lua, grid):
    level = pure_lua.eval('(require("src.levels.test_room"))')
    for row in range(grid.ROWS):
        assert grid.is_solid(grid.cell(level, level.width, row))
        assert grid.is_solid(grid.cell(level, level.width + 50, row))


def test_builder_shapes(pure_lua, grid):
    pure_lua.execute("""
        local Grid = require("src.levelgrid")
        local g = Grid.new(20)
        g:pit(6, 7):trench(9, 10):pillar(12, 3):shelf(14, 15, 4)
        built = g:finish({ name = "t" })
    """)
    level = pure_lua.globals().built
    cell = lambda c, r: grid.cell(level, c, r)
    assert cell(5, 14) == "#" and cell(5, 13) == "."
    assert cell(6, 14) == "." and cell(6, 15) == ".", "a pit goes all the way down"
    assert cell(9, 14) == "." and cell(9, 15) == "#", "a trench is one tile deep"
    assert [cell(12, r) for r in (10, 11, 12, 13)] == [".", "#", "#", "#"]
    assert cell(14, 10) == "B" and cell(14, 11) == "." and cell(14, 9) == "."


def test_validate_reports_a_bad_start(pure_lua, grid):
    pure_lua.execute("""
        local Grid = require("src.levelgrid")
        local g = Grid.new(20)
        g:pit(4, 4)
        noGround = g:finish({ name = "t" })
        g = Grid.new(20)
        g:set(4, 13, "#")
        blocked = g:finish({ name = "t" })
    """)
    g = pure_lua.globals()
    assert any("no ground" in p for p in grid.validate(g.noGround).values())
    assert any("start cell is solid" in p for p in grid.validate(g.blocked).values())


def test_the_test_room_has_what_its_header_says(pure_lua, grid):
    level = pure_lua.eval('(require("src.levels.test_room"))')
    cell = lambda c, r: grid.cell(level, c, r)
    ground = grid.GROUND_ROW
    for height, col in ((2, 30), (3, 35), (4, 40), (5, 46), (6, 53)):
        assert grid.is_solid(cell(col, ground - height)), f"ledge {height} up at column {col}"
        assert not grid.is_solid(cell(col, ground - 1)), "walkable underneath"
    for c0, c1 in ((66, 67), (72, 74), (80, 83), (94, 99)):
        assert all(cell(c, ground) == "." and cell(c, ground + 1) == "#" for c in range(c0, c1 + 1))
    assert all(cell(c, ground + 1) == "." for c in (112, 113, 114)), "the real pit"
    # nothing on the floor between the start and the seam: the run-up must be clear
    assert all(not grid.is_solid(cell(c, ground - 1)) for c in range(1, 66))
