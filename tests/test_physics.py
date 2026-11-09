"""The movement model's numbers, pinned.

These are the feel of the game written down: how high a jump goes, how long it
takes to reach a run, how far a skid slides. Changing src/physics.lua TUNING
moves them, and a test failing here is the prompt to decide that on purpose.
All distances are in tiles, all times in frames at 60 per second.
"""

import pytest

SIM = """
local P = require("src.physics")
local T = P.TUNING

function topSpeed(run, frames)
    local s = P.new()
    for _ = 1, frames do P.step(s, { right = true, run = run }, true) end
    return s.vx
end

function framesToSpeed(run, target)
    local s = P.new()
    for f = 1, 600 do
        P.step(s, { right = true, run = run }, true)
        if s.vx >= target then return f end
    end
    return -1
end

--- Jump from a given ground speed, holding jump for `hold` frames. Apex height.
function jumpApex(vx, hold)
    local s = P.new()
    s.vx = vx
    local vy = P.jump_velocity(s)
    P.takeoff(s, true)
    local y, apex = 0.0, 0.0
    for f = 1, 600 do
        y = y + vy
        if y > apex then apex = y end
        if y <= 0 and f > 1 then break end
        vy = math.max(vy - P.gravity(s, f <= hold, vy), -T.max_fall)
    end
    return apex
end

--- Distance covered by a full-hold jump at constant ground speed vx.
function jumpDistance(vx)
    local s = P.new()
    s.vx = vx
    local vy = P.jump_velocity(s)
    P.takeoff(s, true)
    local x, y = 0.0, 0.0
    for f = 1, 600 do
        x = x + P.step(s, { right = true, run = true }, false)
        y = y + vy
        if y <= 0 and f > 1 then break end
        vy = math.max(vy - P.gravity(s, true, vy), -T.max_fall)
    end
    return x
end

--- From full run right, hold left: frames until moving left, and distance slid.
function skid()
    local s = P.new()
    s.vx = T.run_max
    local x, frames, skidded = 0.0, 0, 0
    for f = 1, 600 do
        P.step(s, { left = true, run = true }, true)
        if s.skidding then skidded = skidded + 1 end
        x = x + s.vx
        if s.vx < 0 then frames = f break end
    end
    return frames, x, skidded, s.facing
end

function coast(vx)
    local s = P.new()
    s.vx = vx
    local x = 0.0
    for f = 1, 600 do
        P.step(s, {}, true)
        x = x + s.vx
        if s.vx == 0 then return f, x end
    end
    return -1, x
end

function airborne(vx0, inp, frames, takeoffSpeed)
    local s = P.new()
    s.vx = takeoffSpeed or vx0
    P.takeoff(s, true)
    s.vx = vx0
    for _ = 1, frames do P.step(s, inp, false) end
    return s.vx
end
"""


@pytest.fixture
def sim(pure_lua):
    pure_lua.execute(SIM)
    return pure_lua.globals()


@pytest.fixture
def held(pure_lua):
    """Build the Lua input table Physics.step takes: held("right", "run")."""
    return lambda *buttons: pure_lua.table_from({b: True for b in buttons})


@pytest.fixture
def tuning(pure_lua):
    return pure_lua.eval('require("src.physics").TUNING')


def test_walking_tops_out_at_walk_speed(sim, tuning):
    assert sim.topSpeed(False, 300) == pytest.approx(tuning.walk_max)
    assert tuning.walk_max == pytest.approx(1.5625 / 16)


def test_running_tops_out_at_run_speed(sim, tuning):
    assert sim.topSpeed(True, 300) == pytest.approx(tuning.run_max)
    assert tuning.run_max > tuning.walk_max * 1.5


def test_speed_builds_up_rather_than_snapping(sim, tuning):
    """Momentum: about 0.7 s to a full walk, about 0.75 s to a full run."""
    assert 35 <= sim.framesToSpeed(False, tuning.walk_max) <= 50
    assert 38 <= sim.framesToSpeed(True, tuning.run_max) <= 55
    assert sim.topSpeed(False, 5) < tuning.walk_max * 0.25


def test_standing_jump_clears_four_tiles_and_not_five(sim):
    apex = sim.jumpApex(0.0, 600)
    assert 4.0 < apex < 4.6


def test_running_jump_clears_five_tiles_and_not_six(sim, tuning):
    apex = sim.jumpApex(tuning.run_max, 600)
    assert 5.0 < apex < 5.9


def test_a_tap_is_a_hop(sim):
    """Variable height: letting go early cuts the jump to about a tile."""
    tap = sim.jumpApex(0.0, 1)
    assert 0.9 < tap < 1.8
    assert sim.jumpApex(0.0, 8) > tap
    assert sim.jumpApex(0.0, 600) > sim.jumpApex(0.0, 8)


def test_jump_distance_grows_with_speed(sim, tuning):
    walk = sim.jumpDistance(tuning.walk_max)
    run = sim.jumpDistance(tuning.run_max)
    assert 3.5 < walk < 6.5
    assert 8.0 < run < 11.5
    assert run > walk * 1.5


def test_reversing_at_a_run_skids(sim):
    frames, slid, skidded, facing = sim.skid()
    assert 15 <= frames <= 30, "about a third of a second to turn around"
    assert 1.0 < slid < 2.6, "slides a tile or two first"
    assert skidded >= 10
    assert facing == -1, "the hero faces the way the stick is held"


def test_letting_go_coasts_to_a_stop(sim, tuning):
    frames, slid = sim.coast(tuning.run_max)
    assert 40 <= frames <= 60
    assert 3.0 < slid < 5.0


def test_air_keeps_momentum_without_input(sim, tuning, held):
    assert sim.airborne(tuning.run_max, held(), 60) == pytest.approx(tuning.run_max)


def test_a_standing_jump_cannot_reach_run_speed_in_the_air(sim, tuning, held):
    vx = sim.airborne(0.0, held("right", "run"), 300, 0.0)
    assert vx == pytest.approx(tuning.walk_max)


def test_a_running_jump_keeps_run_speed_cap(sim, tuning, held):
    vx = sim.airborne(tuning.run_max, held("right", "run"), 60)
    assert vx == pytest.approx(tuning.run_max)


def test_air_control_can_pull_back(sim, tuning, held):
    vx = sim.airborne(tuning.walk_max, held("left"), 30)
    assert vx < tuning.walk_max * 0.5


def test_ducking_gives_no_push(pure_lua):
    pure_lua.execute("""
        local P = require("src.physics")
        local s = P.new()
        for _ = 1, 60 do P.step(s, { right = true, down = true }, true) end
        duckSpeed = s.vx
    """)
    assert pure_lua.globals().duckSpeed == 0


def test_walking_off_a_ledge_falls_heavily(pure_lua):
    pure_lua.execute("""
        local P = require("src.physics")
        local s = P.new()
        s.vx = P.TUNING.walk_max
        P.takeoff(s, false)
        heldGravity = P.gravity(s, true, 0.0)
        fallGravity = P.TUNING.gravity_fall[s.tier]
    """)
    g = pure_lua.globals()
    assert g.heldGravity == g.fallGravity, "holding jump must not float a walk-off"
