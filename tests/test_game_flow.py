"""main.lua, run for real against tests/stub_engine.lua.

The stub is not Spelunky 2 (see its header): these tests prove the mod's Lua
executes end to end and keeps its own promises (input hidden from the engine,
camera never goes back, seam, restart, trace), not that the real engine honours
velocities the way the stub does. README.md's checklist covers that part.
"""

import pytest

from conftest import MANIFEST, boot, errors

I = MANIFEST["enums"]["INPUTS"]
RIGHT, LEFT, JUMP, RUN, BOMB, DOWN, ROPE, WHIP = (
    I["RIGHT"], I["LEFT"], I["JUMP"], I["RUN"], I["BOMB"], I["DOWN"], I["ROPE"], I["WHIP"])
CHAR = MANIFEST["enums"]["CHAR_STATE"]


@pytest.fixture
def game(pack):
    rt = boot(pack)
    rt.execute("Stub.start_level()")
    assert errors(rt) == []
    return rt


def step(rt, buttons, frames=1):
    fn = rt.eval("Stub.step")
    for _ in range(frames):
        fn(buttons)


def player(rt):
    return rt.eval("Stub.player")


def test_boot_registers_callbacks_without_errors(pack):
    rt = boot(pack)
    assert errors(rt) == []
    assert rt.eval("#Stub.callbacks") >= 6
    assert rt.eval("meta.unsafe") is True


def test_the_camp_is_left_alone(pack):
    rt = boot(pack)
    rt.execute("state.screen = SCREEN.CAMP; Stub.fire(ON.PRE_LOAD_LEVEL_FILES, {})")
    assert rt.eval("Stub.loaded") is None
    assert rt.eval("SSB.Level.active") is None
    rt.execute("Stub.new_player(10, 100); Stub.fire(ON.LEVEL)")
    step(rt, RIGHT, 5)
    assert rt.eval("Stub.seen") == RIGHT, "outside our levels the engine sees the real buttons"
    assert rt.eval("Stub.zoom") == 13.5
    assert errors(rt) == []


def test_a_level_load_asks_for_the_right_blank_level(game):
    assert game.eval("Stub.loaded.file") == "ssb_blank_8x4.lvl"  # test room: two strips
    assert game.eval("Stub.loaded.theme.width") == 8
    assert game.eval("Stub.loaded.theme.height") == 4
    assert game.eval("Stub.loaded.theme.theme") == MANIFEST["enums"]["THEME"]["DWELLING"]


def test_the_level_is_built_in_every_strip(game):
    assert game.eval("Stub.tile_count()") > 2 * 2 * 80 * 0.9, "two strips of two ground rows at least"
    # ground under the start, air at the start, in strip 0
    assert game.eval("Stub.solid(SSB.Level.world(0, 4, 14))")
    assert not game.eval("Stub.solid(SSB.Level.world(0, 4, 13))")
    # the same global column (60) seen from both strips: local 60 and local 8
    for row in (11, 13, 14):
        assert game.eval(f"Stub.solid(SSB.Level.world(0, 60, {row}))") == \
            game.eval(f"Stub.solid(SSB.Level.world(1, 8, {row}))")
    assert game.eval("Stub.solid(SSB.Level.world(0, 60, 11))"), "the low ceiling is there"


def test_the_level_librarys_floor_remover_is_disarmed(game):
    """Found in game: the level loaded empty and the hero fell through it.

    The library destroys anything spawned as "floor spreading", and the engine
    counts every floor a script places during level generation as that. The stub
    reproduces both halves; src/level.lua must clear the library's callback.
    """
    assert game.eval("Stub.floor_spread_callback") is None
    assert game.eval("Stub.tile_count()") > 300
    game.execute("local x, y = SSB.Level.world(0, 4, 14); underStart = get_grid_entity_at(x, y, LAYER.FRONT)")
    assert game.eval("underStart") != -1
    assert errors(game) == []


def test_tiles_that_did_not_survive_are_reported(pack):
    rt = boot(pack, before="function clear_callback() end  -- a build where disarming does nothing")
    rt.execute("Stub.start_level()")
    assert any("placed but are not in the level" in e for e in errors(rt))
    assert "under the start: uid -1" in (pack / "ssb_boot.log").read_text()


def test_no_tile_is_placed_on_the_exit_door(pack):
    """The blank level has its exit at the far end of the last strip."""
    rt = boot(pack)
    rt.execute("""
        SSB.Level.defs[1] = SSB.Grid.new(100):finish({ name = "short" })  -- ends before the strip does
        Stub.start_level()
    """)
    assert rt.eval("SSB.Level.active.strips") == 2
    assert not rt.eval("Stub.solid(SSB.Level.world(1, 78, 13))"), "the door's cell is left clear"
    assert rt.eval("Stub.solid(SSB.Level.world(1, 77, 13))"), "past the end of the design is solid"
    assert rt.eval("Stub.solid(SSB.Level.world(1, 78, 14))"), "with ground under the door"


def test_breadcrumbs_name_every_step_of_a_level_load(pack):
    rt = boot(pack)
    rt.execute("Stub.fire(ON.PRE_LEVEL_GENERATION); Stub.start_level()")
    rt.execute("Stub.fire(ON.PRE_LEVEL_GENERATION); Stub.fire(ON.POST_ROOM_GENERATION)")
    step(rt, RIGHT, 3)
    lines = (pack / "ssb_boot.log").read_text().splitlines()
    wanted = ["require src.game", "script loaded", "pre_load_level_files: screen=12",
              "loading test_room as ssb_blank_8x4.lvl", "post_level_generation: placing tiles",
              "placed ", "level start: player uid", "hook set_pre_fall", "camera",
              "level start done", "first frame: pre_update", "first frame done: running"]
    position = 0
    for want in wanted:
        hits = [i for i, line in enumerate(lines) if i >= position and want in line]
        assert hits, f"no breadcrumb containing {want!r} after line {position}: {lines}"
        position = hits[0]
    assert sum("first frame done" in l for l in lines) == 1, "once per level, not once per frame"
    assert any("pre_level_generation" in l for l in lines)


def test_the_hero_is_set_up(game):
    p = player(game)
    assert p.inventory.bombs == 0
    assert p.inventory.ropes == 2
    assert game.eval("Stub.zoom") == pytest.approx(16.885, abs=0.01)
    assert game.eval("state.camera.focused_entity_uid") == -1
    hooks = set(p.hooks.keys())
    assert hooks == {"set_pre_calculate_jump_velocity", "set_pre_fall", "set_pre_apply_friction",
                     "set_pre_damage", "set_pre_stun", "set_post_update_state_machine"}


def test_direction_and_bomb_are_hidden_from_the_engine(game):
    step(game, RIGHT | BOMB | RUN | JUMP | ROPE | WHIP)
    seen = game.eval("Stub.seen")
    assert seen & (RIGHT | LEFT | BOMB) == 0
    assert seen & (RUN | JUMP | ROPE | WHIP) == RUN | JUMP | ROPE | WHIP, "whip, rope and jump still reach the engine"


def test_walking_reaches_walk_speed_through_the_model(game):
    x0 = player(game).x
    step(game, RIGHT, 5)
    assert 0 < player(game).velocityx < 0.03, "momentum: nowhere near top speed after 5 frames"
    step(game, RIGHT, 120)
    assert player(game).velocityx == pytest.approx(1.5625 / 16)
    assert player(game).x > x0 + 8


def test_running_reaches_run_speed(game):
    step(game, RIGHT | RUN, 120)
    assert player(game).velocityx == pytest.approx(2.5625 / 16)


def test_friction_is_the_models_not_the_engines(game):
    step(game, RIGHT | RUN, 120)
    step(game, 0, 10)
    # the stub's own friction halves speed every frame; the model's coasts
    assert player(game).velocityx > 0.1


def test_facing_follows_the_stick(game):
    bit = 1 << (MANIFEST["enums"]["ENT_FLAG"]["FACING_LEFT"] - 1)
    step(game, RIGHT, 3)
    assert player(game).flags & bit == 0
    step(game, LEFT, 3)
    assert player(game).flags & bit != 0


def apex(rt, buttons_while_held, hold):
    y0 = player(rt).y
    top = y0
    for f in range(200):
        step(rt, buttons_while_held if f < hold else buttons_while_held & ~JUMP)
        top = max(top, player(rt).y)
        if f > 2 and player(rt).standing_on_uid != -1:
            break
    return top - y0


def test_a_held_standing_jump_is_about_four_tiles(game):
    """Clears four tiles, even though the stub applies gravity before moving."""
    assert 4.0 < apex(game, JUMP, 200) < 4.3


def test_jump_height_does_not_depend_on_the_engines_update_order(pack):
    """Gravity-then-move and move-then-gravity engines give the same jump."""
    heights = []
    for after in ("false", "true"):
        rt = boot(pack, before=f"Stub.gravity_after_move = {after}")
        rt.execute("Stub.start_level()")
        heights.append(apex(rt, JUMP, 200))
        assert errors(rt) == []
    assert all(4.0 < h < 4.3 for h in heights), heights
    assert abs(heights[0] - heights[1]) < 0.02


def test_a_tapped_jump_is_a_hop(game):
    assert 0.8 < apex(game, JUMP, 1) < 2.0


def test_a_running_jump_is_higher(game):
    step(game, RIGHT | RUN, 60)
    assert 5.0 < apex(game, RIGHT | RUN | JUMP, 200) < 5.4


def test_the_jump_still_works_if_the_velocity_hook_is_missing(pack):
    rt = boot(pack, before='Stub.missing_hooks = { set_pre_calculate_jump_velocity = true }')
    rt.execute("Stub.start_level()")
    assert any("set_pre_calculate_jump_velocity is not available" in e for e in errors(rt))
    assert 3.7 < apex(rt, JUMP, 200) < 4.7, "the fallback writes the jump velocity directly"


def test_the_walk_animation_runs_while_moving(game):
    frames = set()
    for _ in range(60):
        step(game, RIGHT)
        frames.add(player(game).animation_frame)
    assert frames <= set(range(0, 9))
    assert len(frames) >= 6, "cycles through the walk cells 1..8"


def test_the_skid_frame_shows_when_reversing(game):
    step(game, RIGHT | RUN, 90)
    step(game, LEFT | RUN, 4)
    assert player(game).animation_frame == 11 * 16 + 11


def test_the_camera_only_moves_forward(game):
    cam = lambda: game.eval("state.camera.focus_x")
    start = cam()
    step(game, RIGHT | RUN, 240)
    step(game, 0, 80)  # coast to a stop: a skid would still carry the camera forward
    assert player(game).velocityx == 0
    far = cam()
    assert far > start + 10
    step(game, LEFT | RUN, 240)
    assert cam() == far, "walking back does not scroll back"
    wall = game.eval("SSB.Camera.left_wall()")
    assert player(game).x >= wall - 1e-6, "the left edge of the screen is a wall"
    assert player(game).velocityx == 0
    assert game.eval("state.camera.focus_y") == pytest.approx(122 - 7.5)


def test_a_skid_still_carries_the_camera_forward(game):
    step(game, RIGHT | RUN, 120)
    before = game.eval("state.camera.focus_x")
    step(game, LEFT | RUN, 5)
    assert game.eval("state.camera.focus_x") > before


def test_the_first_frame_of_a_level_already_hides_direction(game):
    step(game, RIGHT)
    assert game.eval("Stub.seen") & RIGHT == 0


def test_direction_comes_back_the_frame_a_rope_is_grabbed(game):
    step(game, RIGHT, 10)
    player(game).state = CHAR["CLIMBING"]
    player(game).standing_on_uid = -1
    step(game, RIGHT)
    assert game.eval("Stub.seen") & RIGHT != 0, "no one-frame gap in either direction"
    player(game).state = CHAR["FALLING"]
    step(game, RIGHT)
    assert game.eval("Stub.seen") & RIGHT == 0


def test_another_mod_rewriting_the_input_is_respected(game):
    """An input-sync layer writes buttons_gameplay between the input phase and the
    update. Whatever it leaves there is what the hero must act on."""
    game.execute("""
        set_callback(function()
            state.player_inputs.player_slot_1.buttons_gameplay = INPUTS.LEFT
        end, ON.POST_PROCESS_INPUT)
    """)
    step(game, RIGHT, 30)
    assert player(game).velocityx < 0, "moved by the rewritten input (left), not the device (right)"
    assert game.eval("Stub.seen") & (LEFT | RIGHT) == 0


def test_the_camera_keeps_the_hero_left_of_centre(game):
    step(game, RIGHT | RUN, 240)
    assert game.eval("state.camera.focus_x") - player(game).x == pytest.approx(1.0)


def run_to_strip(rt, strip, limit=3000):
    for _ in range(limit):
        if rt.eval("SSB.Level.active.strip") == strip:
            return True
        step(rt, RIGHT)
    return False


def test_the_seam_moves_hero_and_camera_together(game):
    # walk (not run): stay under the height-2 ledge... the floor is clear to the seam
    before = None
    for _ in range(3000):
        p = player(game)
        before = (p.x, p.y, game.eval("state.camera.focus_x"), game.eval("state.camera.focus_y"))
        step(game, RIGHT)
        if game.eval("SSB.Level.active.strip") == 1:
            break
    else:
        pytest.fail("never reached the second strip")
    p = player(game)
    # one frame of walking, then everything 52 left and 16 down
    assert p.x == pytest.approx(before[0] - 52 + p.velocityx, abs=0.01)
    assert p.y == pytest.approx(before[1] - 16)
    assert game.eval("state.camera.focus_x") == pytest.approx(before[2] - 52, abs=0.2)
    assert game.eval("state.camera.focus_y") == pytest.approx(before[3] - 16)
    assert game.eval("state.camera.adjusted_focus_y") == pytest.approx(before[3] - 16), "a cut, not a pan"
    # what is on screen is the same before and after: the view sits inside the shared columns
    grid = game.eval("SSB.Grid")
    cam_local = game.eval("state.camera.focus_x") - 3
    half = game.eval("SSB.Camera.VIEW_W") / 2
    assert cam_local - half >= -0.5 and cam_local + half <= grid.OVERLAP - 0.5 + 1.0
    assert errors(game) == []


def test_play_continues_in_the_second_strip(game):
    assert run_to_strip(game, 1)
    x = player(game).x
    step(game, RIGHT, 30)
    assert player(game).x > x + 2
    assert game.eval("SSB.Level.global_x(Stub.player.x)") > 66
    assert game.eval("#Stub.warps") == 0


def test_falling_out_restarts_the_level(pack):
    rt = boot(pack, before="")
    rt.execute("""
        local Grid = SSB.Grid
        local g = Grid.new(40)
        g:pit(8, 11)
        SSB.Level.defs[1] = g:finish({ name = "pit" })
        Stub.start_level()
    """)
    assert rt.eval("Stub.loaded.file") == "ssb_blank_8x2.lvl"
    for _ in range(400):
        step(rt, RIGHT)
        if rt.eval("#Stub.warps") > 0:
            break
    assert rt.eval("#Stub.warps") == 1, "warped exactly once"
    assert list(rt.eval("Stub.warps[1]").values()) == [1, 1, MANIFEST["enums"]["THEME"]["DWELLING"]]
    step(rt, RIGHT, 20)
    assert rt.eval("#Stub.warps") == 1, "and not again while the reload is pending"
    assert errors(rt) == []


def test_an_unusable_level_is_reported_not_loaded(pack):
    rt = boot(pack)
    rt.execute("""
        local g = SSB.Grid.new(40)
        g:pit(4, 4)
        SSB.Level.defs[1] = g:finish({ name = "broken" })
        state.screen = SCREEN.LEVEL
        Stub.fire(ON.PRE_LOAD_LEVEL_FILES, {})
    """)
    assert rt.eval("SSB.Level.active") is None
    assert any("broken is not usable" in e for e in errors(rt))


def test_non_driven_states_give_control_back(game):
    """On a rope the engine needs LEFT / RIGHT (to jump off sideways)."""
    step(game, RIGHT, 30)
    player(game).state = CHAR["CLIMBING"]
    player(game).standing_on_uid = -1
    step(game, LEFT, 2)
    assert game.eval("Stub.seen") & LEFT != 0
    assert game.eval("Stub.seen") & BOMB == 0


def test_bombs_stay_hidden_on_a_rope(game):
    player(game).state = CHAR["CLIMBING"]
    step(game, BOMB, 3)
    assert game.eval("Stub.seen") & BOMB == 0


def test_leaving_the_level_restores_zoom_and_the_ghost(game):
    assert game.eval("Stub.ghost") is False, "no time-limit ghost in our levels"
    game.execute("state.screen = SCREEN.CAMP; Stub.fire(ON.SCREEN)")
    assert game.eval("Stub.zoom") == 13.5
    assert game.eval("Stub.ghost") is True
    assert game.eval("SSB.Hero.uid()") == -1


def test_script_disable_puts_textures_back(pack):
    (pack / "res").mkdir()
    (pack / "res" / "hero.png").write_bytes(b"png")
    rt = boot(pack)
    rt.execute("Stub.start_level()")
    char = MANIFEST["enums"]["TEXTURE"]["DATA_TEXTURES_CHAR_GREEN_0"]  # the stub's player 1
    assert rt.eval("Stub.defined_path") == "res/hero.png"
    assert rt.eval(f"Stub.replaced[{char}]") == 9001
    rt.execute("Stub.fire(ON.SCRIPT_DISABLE)")
    assert rt.eval(f"Stub.replaced[{char}]") is None
    assert errors(rt) == []


def with_sheet(pack, before=""):
    (pack / "res").mkdir()
    (pack / "res" / "hero.png").write_bytes(b"png")
    return boot(pack, before=before)


def test_the_hero_sheet_is_in_place_before_the_player_spawns(pack):
    """Found in game: the first level showed the vanilla character, because the
    sheet was replaced at level start, after the player entity already existed."""
    rt = with_sheet(pack)
    rt.execute("""
        set_callback(function()
            replacedBeforeSpawn = Stub.replaced[state.items.player_select[1].texture]
            playerExisted = Stub.player ~= nil
        end, ON.PRE_LEVEL_GENERATION)
        Stub.start_level()
    """)
    assert rt.eval("playerExisted") is False
    assert rt.eval("replacedBeforeSpawn") == 9001
    assert rt.eval("Stub.player.texture") == rt.eval("state.items.player_select[1].texture"), \
        "the entity keeps its own sheet id; the sheet behind it is what changed"
    assert "hero texture: replaced vanilla texture 290" in (pack / "ssb_boot.log").read_text()


def test_the_camp_does_not_get_the_hero_sheet(pack):
    rt = with_sheet(pack)
    rt.execute("state.screen = SCREEN.CAMP; Stub.fire(ON.PRE_LOAD_LEVEL_FILES, {})")
    assert rt.eval("next(Stub.replaced)") is None


def test_the_player_entity_is_dressed_directly_when_the_early_path_fails(pack):
    rt = with_sheet(pack, before="""
        state.items = nil  -- a build where the selection cannot be read
        Stub.player_texture = 290
    """)
    rt.execute("Stub.start_level()")
    assert rt.eval("Stub.replaced[290]") == 9001
    assert rt.eval("Stub.player.texture") == 9001, "set on the entity too, so the first level is right"
    assert errors(rt) == []


@pytest.mark.parametrize("mechanism", ["ledge_by_force", "ledge_by_next_state"])
def test_the_hero_never_hangs_from_a_ledge(pack, mechanism):
    """Found in game: the engine grabbed the 5-high ledge with no direction held.
    Whichever way the state machine reaches the hanging state, it must not."""
    rt = boot(pack, before=f"Stub.{mechanism} = true")
    rt.execute("Stub.start_level()")
    apex(rt, JUMP, 200)
    assert rt.eval("Stub.hung") is None
    assert errors(rt) == []
    crumbs = (pack / "ssb_boot.log").read_text()
    for state_id in (CHAR["HANGING"], CHAR["JUMPING"], CHAR["FALLING"]):
        assert f"ledge grab: state {state_id} ok" in crumbs


def test_the_stub_does_hang_when_left_alone(pack):
    """The test above means something only if the stub grabs ledges by itself."""
    (pack / "ssb_vanilla_ledge.on").write_text("")
    rt = boot(pack, before="Stub.ledge_by_next_state = true")
    rt.execute("Stub.start_level()")
    assert "left to the engine" in (pack / "ssb_boot.log").read_text()
    step(rt, JUMP, 3)
    assert rt.eval("Stub.hung") >= 1


def test_a_hang_that_gets_through_is_undone_the_same_frame(pack):
    """Backstop: with the state machine left alone, the hero is dropped at once
    and keeps the speed it had, instead of stopping dead on the ledge."""
    (pack / "ssb_vanilla_ledge.on").write_text("")
    (pack / "ssb_trace.on").write_text("")
    rt = boot(pack)
    rt.execute("Stub.start_level()")
    step(rt, RIGHT | RUN, 60)
    step(rt, RIGHT | RUN | JUMP, 5)
    vy = player(rt).velocityy
    assert vy > 0.2
    rt.execute("Stub.ledge_by_next_state = true")
    step(rt, RIGHT | RUN | JUMP)
    rt.execute("Stub.ledge_by_next_state = false")
    p = player(rt)
    assert p.state != CHAR["HANGING"]
    assert p.velocityx == pytest.approx(2.5625 / 16)
    assert p.velocityy == pytest.approx(vy, abs=0.02)
    rt.execute("state.screen = SCREEN.CAMP; Stub.fire(ON.SCREEN)")
    assert "ledge grab undone" in (pack / "ssb_trace.log").read_text()


def test_wrapping_failing_is_reported_and_play_goes_on(pack):
    rt = boot(pack, before="function make_custom_behavior() error('not on this build') end")
    rt.execute("Stub.start_level()")
    assert any("could not wrap state" in e for e in errors(rt))
    step(rt, RIGHT, 30)
    assert player(rt).x > 8


def test_without_the_hero_sheet_the_mod_says_how_to_build_it(game):
    printed = list(game.eval("Stub.printed").values())
    assert any("python tools/build_assets.py" in line for line in printed)
    assert game.eval("Stub.defined_path") is None


def test_no_trace_without_the_flag_file(pack):
    rt = boot(pack)
    rt.execute("Stub.start_level()")
    step(rt, RIGHT, 10)
    assert not (pack / "ssb_trace.log").exists()


def test_the_trace_file(pack):
    (pack / "ssb_trace.on").write_text("")
    rt = boot(pack)
    rt.execute("Stub.start_level()")
    step(rt, RIGHT | RUN, 40)
    step(rt, RIGHT | RUN | JUMP, 40)
    rt.execute("state.screen = SCREEN.CAMP; Stub.fire(ON.SCREEN)")  # closes the file
    lines = (pack / "ssb_trace.log").read_text().splitlines()
    header = [l for l in lines if l.startswith("#")]
    assert any("level test_room" in l for l in header)
    assert any("hooks:" in l and "set_pre_fall=ok" in l for l in header)
    assert any("jump: tier" in l for l in header)
    columns = next(l for l in lines if l.startswith("tick,"))
    names = columns.split(",")
    rows = [l.split(",") for l in lines if l and l[0].isdigit()]
    assert len(rows) == 80
    assert all(len(r) == len(names) for r in rows)
    first = dict(zip(names, rows[0]))
    last = dict(zip(names, rows[-1]))
    assert first["tick"] == "1" and last["tick"] == "80"
    assert float(last["gx"]) > float(first["gx"])
    assert int(last["raw"]) == RIGHT | RUN | JUMP, "the trace has the real buttons, not the stripped ones"
    assert errors(rt) == []


def test_every_callback_survives_a_thrown_error(pack):
    """SafeCall: a bug in one frame must not take the callback down or freeze the engine."""
    rt = boot(pack)
    rt.execute("Stub.start_level()")
    rt.execute("SSB.Camera.update = function() error('boom') end")
    step(rt, RIGHT, 5)
    found = [e for e in errors(rt) if "boom" in e]
    assert len(found) == 1, "reported once, not once per frame"
