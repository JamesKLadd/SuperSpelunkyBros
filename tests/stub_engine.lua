--- A stand-in for the Spelunky 2 engine, just big enough to run this mod's Lua.
---
--- It is NOT a model of the real engine's physics: it exists so every callback
--- and hook in src/ executes under a real Lua before anyone launches the game,
--- which catches typos, nil indexes and wrong call orders. Its player update is
--- the simplest thing that honours the same contracts the real one does:
---   * walks and jumps only from the buttons left in buttons_gameplay
---   * asks the calculate_jump_velocity hook for the jump strength
---   * lets the fall and apply_friction hooks replace gravity and friction
---   * moves by velocityx / velocityy and stops at solid tiles
---
--- Enum tables (ON, SCREEN, INPUTS, ...) are defined by the Python side from
--- tests/api_manifest.json before this file runs, with the real values.

Stub = {
    callbacks = {},
    tiles = {},
    warps = {},
    printed = {},
    replaced = {},
    zoom = 13.5,
    ghost = true,
    frame = 0,
    next_uid = 100,
    player = nil,
    loaded = nil,     -- what the level library was asked to load
    seen = 0,         -- buttons the "engine" saw on the last frame
    prev_jump = false,
}

local real_print = print
function print(...)
    local parts = {}
    for i = 1, select("#", ...) do
        parts[i] = tostring((select(i, ...)))
    end
    Stub.printed[#Stub.printed + 1] = table.concat(parts, " ")
    if Stub.echo then
        real_print(...)
    end
end

function set_callback(fn, on)
    assert(type(fn) == "function", "set_callback: not a function")
    assert(on ~= nil, "set_callback: nil event (a missing ON member?)")
    Stub.callbacks[#Stub.callbacks + 1] = { fn = fn, on = on }
    return #Stub.callbacks
end

function Stub.fire(on, ...)
    assert(on ~= nil, "Stub.fire: nil event")
    for _, cb in ipairs(Stub.callbacks) do
        if cb.on == on then
            local result = cb.fn(...)
            if on == ON.PRE_UPDATE then
                assert(result ~= true, "a PRE_UPDATE callback returned true: that freezes the engine")
            end
        end
    end
end

state = {
    screen = SCREEN.CAMP,
    pause = 0,
    world = 1,
    level = 1,
    theme = THEME.DWELLING,
    camera = {
        focus_x = 0, focus_y = 0, adjusted_focus_x = 0, adjusted_focus_y = 0,
        calculated_focus_x = 0, calculated_focus_y = 0, focus_offset_x = 0, focus_offset_y = 0,
        focused_entity_uid = 0, inertia = 1.0,
    },
    player_inputs = { player_slot_1 = { buttons_gameplay = 0 } },
}

function get_frame() return Stub.frame end
function zoom(level) Stub.zoom = level end
function zoom_reset() Stub.zoom = 13.5 end
function set_time_ghost_enabled(enabled) Stub.ghost = enabled end
function warp(w, l, t) Stub.warps[#Stub.warps + 1] = { w, l, t } end
function rgba() return 0 end
function set_flag(flags, bit) return flags | (1 << (bit - 1)) end
function clr_flag(flags, bit) return flags & ~(1 << (bit - 1)) end
function test_flag(flags, bit) return flags & (1 << (bit - 1)) ~= 0 end

local function key(x, y)
    return math.floor(x + 0.5) .. "," .. math.floor(y + 0.5)
end

function spawn_grid_entity(entity_type, x, y, layer)
    assert(entity_type ~= nil, "spawn_grid_entity: nil entity type")
    assert(layer == LAYER.FRONT)
    Stub.next_uid = Stub.next_uid + 1
    -- As in the real engine: a floor spawned during level generation that is not
    -- from a tile code counts as floor spreading, and the level library destroys
    -- every such entity for as long as its callback is registered.
    if Stub.in_level_gen and Stub.floor_spread_callback ~= nil then
        return Stub.next_uid
    end
    Stub.tiles[key(x, y)] = Stub.next_uid
    return Stub.next_uid
end

function get_grid_entity_at(x, y, layer)
    assert(layer == LAYER.FRONT)
    return Stub.tiles[key(x, y)] or -1
end

function clear_callback(id)
    if id ~= nil and id == Stub.floor_spread_callback then
        Stub.floor_spread_callback = nil
    end
end

function Stub.solid(x, y)
    return Stub.tiles[key(x, y)] ~= nil
end

function Stub.tile_count()
    local n = 0
    for _ in pairs(Stub.tiles) do
        n = n + 1
    end
    return n
end

function get_texture_definition(_id)
    return { texture_path = "Data/Textures/char_yellow.png", width = 2048, height = 2048,
        tile_width = 128, tile_height = 128 }
end
function define_texture(def)
    Stub.defined_path = def.texture_path
    return 9001
end
function replace_texture(vanilla, custom)
    Stub.replaced[vanilla] = custom
    return true
end
function reset_texture(vanilla) Stub.replaced[vanilla] = nil end

function get_player(_slot, _or_ghost) return Stub.player end
function get_position(uid)
    assert(Stub.player ~= nil and uid == Stub.player.uid, "get_position: unknown uid")
    return Stub.player.x, Stub.player.y, LAYER.FRONT
end

local HOOKS = {
    "set_pre_calculate_jump_velocity", "set_pre_fall", "set_pre_apply_friction",
    "set_pre_damage", "set_pre_stun", "set_post_update_state_machine",
}

function Stub.new_player(x, y)
    Stub.next_uid = Stub.next_uid + 1
    local p = {
        uid = Stub.next_uid, x = x, y = y, velocityx = 0.0, velocityy = 0.0,
        state = CHAR_STATE.STANDING, standing_on_uid = 1, flags = 0, falling_timer = 0,
        animation_frame = 0, inventory = { bombs = 4, ropes = 4 }, hooks = {},
        texture = TEXTURE.DATA_TEXTURES_CHAR_YELLOW_0,
    }
    for _, name in ipairs(HOOKS) do
        if not (Stub.missing_hooks and Stub.missing_hooks[name]) then
            p[name] = function(self, fn)
                assert(type(fn) == "function")
                self.hooks[name] = fn
                return 1
            end
        end
    end
    function p:set_position(to_x, to_y) self.x, self.y = to_x, to_y end
    function p:get_texture() return self.texture end
    function p:set_texture(t) self.texture = t return true end
    function p:let_go() end
    Stub.player = p
    Stub.prev_jump = false
    return p
end

--- One engine frame with these buttons physically held.
function Stub.step(buttons)
    Stub.frame = Stub.frame + 1
    local slot = state.player_inputs.player_slot_1
    slot.buttons_gameplay = buttons
    if ON.POST_PROCESS_INPUT ~= nil then
        Stub.fire(ON.POST_PROCESS_INPUT)
    end
    Stub.fire(ON.PRE_UPDATE)

    local p = Stub.player
    local hooks = p.hooks
    local seen = slot.buttons_gameplay
    Stub.seen = seen
    local grounded = p.standing_on_uid ~= -1

    -- the engine's own walking, from whatever direction it can still see
    if seen & INPUTS.LEFT ~= 0 then
        p.velocityx = -0.0725
    elseif seen & INPUTS.RIGHT ~= 0 then
        p.velocityx = 0.0725
    end

    local jump = seen & INPUTS.JUMP ~= 0
    if jump and not Stub.prev_jump and grounded then
        local v = hooks.set_pre_calculate_jump_velocity and hooks.set_pre_calculate_jump_velocity(p, false)
        p.velocityy = v or 0.18
        p.state = CHAR_STATE.JUMPING
        p.standing_on_uid = -1
        grounded = false
    end
    Stub.prev_jump = jump

    if grounded then
        local skip = hooks.set_pre_apply_friction and hooks.set_pre_apply_friction(p, 1.0, false, 1.0)
        if not skip then
            p.velocityx = p.velocityx * 0.5
        end
    end
    -- Which comes first in the real engine, gravity or the move, is not known.
    -- Tests run both orders (Stub.gravity_after_move).
    local function gravity()
        local skip_fall = hooks.set_pre_fall and hooks.set_pre_fall(p, 1.0)
        if not skip_fall and p.standing_on_uid == -1 and p.state ~= CHAR_STATE.CLIMBING then
            p.velocityy = p.velocityy - 0.01
        end
    end
    if not Stub.gravity_after_move then
        gravity()
    end

    -- horizontal move, stopped by walls
    if p.velocityx ~= 0 then
        local nx = p.x + p.velocityx
        local edge = nx + (p.velocityx > 0 and 0.3 or -0.3)
        if Stub.solid(edge, p.y) then
            p.velocityx = 0.0
        else
            p.x = nx
        end
    end

    -- vertical move (a climbing player hangs where it is)
    if p.state == CHAR_STATE.CLIMBING then
        p.velocityy = 0.0
    elseif grounded then
        if not Stub.solid(p.x, p.y - 1) then
            p.standing_on_uid = -1
            p.state = CHAR_STATE.FALLING
        end
    else
        local ny = p.y + p.velocityy
        if p.velocityy > 0 and Stub.solid(p.x, ny + 0.45) then
            p.velocityy = 0.0 -- head bonk
        elseif p.velocityy <= 0 and Stub.solid(p.x, ny - 0.5) then
            p.y = math.floor(ny - 0.5 + 0.5) + 1
            p.velocityy = 0.0
            p.standing_on_uid = 1
            p.state = CHAR_STATE.STANDING
        else
            p.y = ny
            p.state = p.velocityy > 0 and CHAR_STATE.JUMPING or CHAR_STATE.FALLING
        end
    end

    if Stub.gravity_after_move then
        gravity()
    end

    if hooks.set_post_update_state_machine then
        hooks.set_post_update_state_machine(p)
    end
    Stub.fire(ON.POST_UPDATE)
end

--- Load one of our levels the way the engine would, and put the player at its start.
function Stub.start_level()
    state.screen = SCREEN.LEVEL
    Stub.tiles = {}
    Stub.fire(ON.PRE_LOAD_LEVEL_FILES, {})
    Stub.in_level_gen = true
    Stub.fire(ON.PRE_LEVEL_GENERATION)
    Stub.fire(ON.POST_ROOM_GENERATION)
    Stub.fire(ON.POST_LEVEL_GENERATION)
    Stub.in_level_gen = false
    local Grid = SSB.Grid
    local x, y = SSB.Level.world(0, Grid.START_COL, Grid.START_ROW)
    Stub.new_player(x, y)
    Stub.fire(ON.SCREEN)
    Stub.fire(ON.LEVEL)
end

package.preload["src.vendor.custom_levels.custom_levels"] = function()
    local lib = { state = {} }
    function lib.load_level_custom_theme(ctx, file_name, theme)
        assert(ctx ~= nil)
        Stub.loaded = { file = file_name, theme = theme }
        -- the real library registers its floor-spreading remover on every load
        Stub.floor_spread_callback = 7001
        lib.state.floor_spread_callback = 7001
    end
    function lib.unload_level()
        Stub.loaded = nil
        Stub.floor_spread_callback = nil
        lib.state.floor_spread_callback = nil
    end
    function lib.set_hide_entrance(_hide) end
    return lib
end
