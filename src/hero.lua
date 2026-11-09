--- The hero: connects src/physics.lua to the player entity.
---
--- What is taken from the engine, and how:
---   * LEFT / RIGHT / BOMB are removed from the player's input before the engine
---     reads it, so the engine never applies its own walk acceleration and never
---     throws a bomb. The real buttons are kept in `raw` and drive the model.
---   * Horizontal speed: the model's `vx` is written to velocityx every frame,
---     before the engine moves the entity. The engine still does the collision.
---   * Friction: the engine's is skipped (apply_friction hook); the model has its own.
---   * Jump strength: the engine still decides WHEN a jump happens (button, ground
---     check, coyote time). How strong comes from the model.
---   * Gravity: skipped while airborne (fall hook) and replaced by the model's,
---     which is light while rising with jump held and heavy otherwise.
---   * Facing and the walk / skid animation: set here, since the engine sees no
---     direction held and would show the hero standing still.
---
--- Everything here runs in update callbacks and entity hooks, on frame counts.

local Physics = require("src.physics")
local Level = require("src.level")
local Camera = require("src.camera")
local Trace = require("src.trace")

local Hero = {}
SSB.Hero = Hero

local HAS_INPUT_PHASE = ON.POST_PROCESS_INPUT ~= nil

local STRIP_ALWAYS = INPUTS.BOMB
local STRIP_MOVE = INPUTS.LEFT | INPUTS.RIGHT

--- States in which the model drives horizontal speed. In the others (on a rope,
--- stunned, walking through a door) the engine keeps full control and its inputs.
local DRIVEN = {
    [CHAR_STATE.STANDING] = true,
    [CHAR_STATE.DUCKING] = true,
    [CHAR_STATE.JUMPING] = true,
    [CHAR_STATE.FALLING] = true,
    [CHAR_STATE.ATTACKING] = true,
    [CHAR_STATE.THROWING] = true,
}

--- States in which we also set which way the hero faces.
local TURNABLE = {
    [CHAR_STATE.STANDING] = true,
    [CHAR_STATE.DUCKING] = true,
    [CHAR_STATE.JUMPING] = true,
    [CHAR_STATE.FALLING] = true,
}

Hero.START_ROPES = 2

--- Sheet cell (row 11, column 11) the hero sheet uses for the skid pose; vanilla
--- character sheets leave it empty. See tools/build_assets.py.
local SKID_FRAME = 11 * 16 + 11
local WALK_FIRST, WALK_COUNT = 1, 8
--- Walk-cycle frames advanced per tile travelled.
local WALK_FRAMES_PER_TILE = 3.5

local uid = -1          -- the hero entity this module is driving, -1 for none
local model = nil       -- Physics state
local raw = 0           -- buttons really held this frame, before stripping
local last_written = -1 -- what we last left in the input field
local strip_move = false
local tick = 0          -- frames driven this level
local was_grounded = true
local prev_state = -1
local x_before = nil
local y_before = nil
local blocked_frames = 0
local jump_hook_tick = -1
local walk_phase = 0.0
local hooks_installed = {}
local last_vy = 0.0     -- vertical speed after the previous frame, to restore

--- Read-only snapshot for the debug overlay.
Hero.debug = {}

local function held(button)
    return (raw & button) ~= 0
end

--- Take the real buttons and hide the ones the engine must not act on.
---
--- Runs twice a frame: straight after the engine fills the field, and again in
--- PRE_UPDATE once this frame's state is known. Whenever the field is not what
--- we last wrote, something refilled it (the engine, or another mod such as an
--- input-sync layer) and that is taken as the real buttons.
--- @param fresh boolean # the field was just filled from the devices
local function filter_input(fresh)
    local slot = state.player_inputs.player_slot_1
    local buttons = slot.buttons_gameplay
    if fresh or buttons ~= last_written then
        raw = buttons
    end
    local mask = STRIP_ALWAYS
    if strip_move then
        mask = mask | STRIP_MOVE
    end
    last_written = raw & ~mask
    slot.buttons_gameplay = last_written
end

--- @return boolean # true while this module is driving a hero in one of our levels
function Hero.active()
    return uid ~= -1 and Level.active ~= nil and state.screen == SCREEN.LEVEL and state.pause == 0
end

--- ON.POST_PROCESS_INPUT: straight after the engine filled the input fields.
function Hero.input_phase()
    if Hero.active() then
        filter_input(true)
    end
end

-- -------------------------------------------------------------- entity hooks

local function on_jump_velocity(_self, _dont_ignore_liquid)
    if model == nil then
        return nil
    end
    jump_hook_tick = tick
    return Physics.jump_velocity(model)
end

--- A jump has really started: fix its tier. Safe to call more than once.
local function begin_jump()
    if not model.jumped then
        Physics.takeoff(model, true)
        Trace.event(string.format("jump: tier %d from vx %.4f (tick %d)", model.tier, model.vx, tick))
    end
end

local function on_fall(self, _scale)
    if model == nil or self.standing_on_uid ~= -1 or not DRIVEN[self.state] then
        return false -- on the ground, on a rope, stunned: the engine's own
    end
    if jump_hook_tick == tick and self.velocityy > 0 then
        -- the engine applies gravity in the same update that starts the jump;
        -- without this the first frame would get the heavy, not-jumping gravity
        begin_jump()
    end
    local vy = self.velocityy - Physics.gravity(model, held(INPUTS.JUMP), self.velocityy)
    local max_fall = Physics.TUNING.max_fall
    if vy < -max_fall then
        vy = -max_fall
    end
    self.velocityy = vy
    return true
end

local function on_friction(self, _a, vertical, _b)
    return model ~= nil and not vertical and DRIVEN[self.state] == true
end

local function on_damage(_self, _dealer, amount, damage_flags)
    -- The health system comes with the power-up milestone. Until then nothing
    -- hurts the hero; the trace records what would have.
    Trace.event(string.format("damage ignored: amount=%s flags=%s tick=%d",
        tostring(amount), tostring(damage_flags), tick))
    return false
end

local function on_stun(_self, framecount)
    Trace.event(string.format("stun ignored: frames=%s tick=%d", tostring(framecount), tick))
    return true
end

local function on_animate(self)
    if model == nil or self.state ~= CHAR_STATE.STANDING or self.standing_on_uid == -1 then
        return
    end
    if model.skidding then
        self.animation_frame = SKID_FRAME
    elseif math.abs(model.vx) > 0.004 then
        self.animation_frame = WALK_FIRST + math.floor(walk_phase) % WALK_COUNT
    end
end

-- ---------------------------------------------------------- no ledge grabs
--
-- The engine grabs a ledge even with no direction held, so hiding the stick does
-- not prevent it (seen in game at the 5-high ledge). The grab is a state of the
-- player's state machine, so it is taken out there: the hanging state may never
-- force itself, and jumping / falling may never choose it as their next state.
--
-- Behaviours are shared engine objects wrapped once per script; each new player
-- entity gets the wrappers swapped in. An empty file `ssb_vanilla_ledge.on` in
-- the pack folder skips all of this, in case a build dislikes it.

local AIR_STATES = { CHAR_STATE.JUMPING, CHAR_STATE.FALLING }

local function swap_behavior(p, state_id, configure)
    local base = p:get_base_behavior(state_id)
    if base == nil then
        return "no vanilla behaviour"
    end
    local custom = make_custom_behavior("ssb_state_" .. state_id, state_id, base)
    configure(custom)
    p:clear_behavior(base)
    p:add_behavior(custom)
    return "ok"
end

local function remove_ledge_grab(p)
    if PackFileExists("ssb_vanilla_ledge.on") then
        Crumb("ledge grab: left to the engine (ssb_vanilla_ledge.on)")
        return
    end
    local function try(state_id, configure)
        Crumb("ledge grab: wrapping state " .. state_id)
        local ok, result = pcall(swap_behavior, p, state_id, configure)
        Crumb("ledge grab: state " .. state_id .. " " .. tostring(result))
        if not ok then
            errorf("hero: could not wrap state %d (%s)", state_id, tostring(result))
        end
    end
    try(CHAR_STATE.HANGING, function(custom)
        custom:set_force_state(function(_movable, _base_fun)
            return false
        end)
    end)
    for _, state_id in ipairs(AIR_STATES) do
        try(state_id, function(custom)
            custom:set_get_next_state_id(function(movable, base_fun)
                local next_id = base_fun(movable)
                if next_id == CHAR_STATE.HANGING then
                    return state_id
                end
                return next_id
            end)
        end)
    end
end

--- Install one entity hook, tolerating a build that does not have it.
local function hook(p, name, fn)
    Crumb("hook " .. name)
    local ok, err = pcall(function()
        p[name](p, fn)
    end)
    hooks_installed[#hooks_installed + 1] = name .. (ok and "=ok" or "=MISSING")
    if not ok then
        errorf("hero: %s is not available on this build (%s)", name, tostring(err))
    end
end

-- ------------------------------------------------------------------ lifecycle

Hero.TRACE_COLUMNS = {
    "tick", "strip", "gx", "x", "y", "dx", "dy", "vx_model", "vx_ent", "vy_ent",
    "state", "grounded", "raw", "skid", "tier", "jumped", "blocked", "cam_x", "anim",
}

--- Level start: take over the player entity.
--- @param p userdata
function Hero.start(p)
    uid = p.uid
    model = Physics.new()
    raw = 0
    last_written = -1
    strip_move = DRIVEN[p.state] == true
    tick = 0
    was_grounded = true
    prev_state = p.state
    x_before, y_before = nil, nil
    blocked_frames = 0
    jump_hook_tick = -1
    walk_phase = 0.0
    hooks_installed = {}

    hook(p, "set_pre_calculate_jump_velocity", on_jump_velocity)
    hook(p, "set_pre_fall", on_fall)
    hook(p, "set_pre_apply_friction", on_friction)
    hook(p, "set_pre_damage", on_damage)
    hook(p, "set_pre_stun", on_stun)
    hook(p, "set_post_update_state_machine", on_animate)
    remove_ledge_grab(p)
    last_vy = 0.0

    p.inventory.bombs = 0
    p.inventory.ropes = Hero.START_ROPES
end

function Hero.stop()
    uid = -1
    model = nil
    Hero.debug = {}
end

--- @return integer
function Hero.uid()
    return uid
end

--- @return string # which hooks this build accepted, for the trace header
function Hero.hook_report()
    return table.concat(hooks_installed, " ")
end

-- ------------------------------------------------------------------ per frame

--- ON.PRE_UPDATE, before the engine moves anything.
--- @param p userdata
function Hero.pre_update(p)
    tick = tick + 1

    local st = p.state
    local driven = DRIVEN[st] == true
    strip_move = driven
    filter_input(not HAS_INPUT_PHASE)

    p.falling_timer = 0 -- no fall stun or fall damage

    local x, y = get_position(p.uid)
    x_before, y_before = x, y

    if not driven then
        -- the engine is in charge: follow it so we resume from its speed
        model.vx = p.velocityx
        model.skidding = false
        Physics.land(model)
        was_grounded = p.standing_on_uid ~= -1
        return
    end

    local grounded = p.standing_on_uid ~= -1
    if was_grounded and not grounded and not model.jumped then
        Physics.takeoff(model, false) -- walked off a ledge
    elseif grounded and (not was_grounded or (model.jumped and st ~= CHAR_STATE.JUMPING)) then
        Physics.land(model)
    end
    was_grounded = grounded

    local vx = Physics.step(model, {
        left = held(INPUTS.LEFT),
        right = held(INPUTS.RIGHT),
        run = held(INPUTS.RUN),
        down = held(INPUTS.DOWN),
    }, grounded)

    -- the left edge of the screen is a wall
    local wall = Camera.left_wall()
    if x < wall then
        p.x = wall
        x = wall
        x_before = wall
    end
    if vx < 0 and x + vx < wall then
        Physics.hit_wall(model)
        vx = 0.0
    end

    p.velocityx = vx

    if TURNABLE[st] then
        if model.facing < 0 then
            p.flags = set_flag(p.flags, ENT_FLAG.FACING_LEFT)
        else
            p.flags = clr_flag(p.flags, ENT_FLAG.FACING_LEFT)
        end
    end
end

--- ON.POST_UPDATE, after the engine moved everything.
--- @param p userdata
function Hero.post_update(p)
    -- Backstop for remove_ledge_grab: if the engine hung the hero on a ledge
    -- anyway, drop it in the same frame and carry on with the speeds it had.
    if p.state == CHAR_STATE.HANGING then
        pcall(function()
            p:let_go()
        end)
        p.velocityx = model.vx
        p.velocityy = last_vy
        Trace.event(string.format("ledge grab undone (tick %d): state now %s", tick, tostring(p.state)))
    end
    last_vy = p.velocityy

    local x, y = get_position(p.uid)
    local st = p.state
    local dx = x_before ~= nil and (x - x_before) or 0.0
    local dy = y_before ~= nil and (y - y_before) or 0.0

    -- a jump started this frame
    if st == CHAR_STATE.JUMPING and prev_state ~= CHAR_STATE.JUMPING then
        if jump_hook_tick ~= tick then
            local impulse = Physics.jump_velocity(model)
            p.velocityy = impulse
            Trace.event(string.format("jump: velocity hook did not fire, wrote %.4f directly (tick %d)",
                impulse, tick))
        end
        begin_jump()
        -- If the engine applies gravity before it moves the entity, the first
        -- step of the jump comes out one gravity step short, and the jump about
        -- an eighth of a tile lower than tuned. Give that one step back, so the
        -- height does not depend on the engine's internal order.
        local expected = Physics.TUNING.jump_velocity[model.tier]
        local g = Physics.TUNING.gravity_hold[model.tier]
        if p.velocityy > 0 and dy > 0 and dy < expected - g * 0.5 then
            p.velocityy = p.velocityy + g
            Trace.event(string.format("jump: first step was %.4f not %.4f, one gravity step given back (tick %d)",
                dy, expected, tick))
        end
    end
    prev_state = st

    -- stopped by something solid: the model must not keep pushing into it
    local blocked = false
    if DRIVEN[st] and math.abs(model.vx) > 0.01 and math.abs(dx) < math.abs(model.vx) * 0.25 then
        blocked_frames = blocked_frames + 1
        if blocked_frames >= 2 then
            blocked = true
            Physics.hit_wall(model)
        end
    else
        blocked_frames = 0
    end

    walk_phase = walk_phase + math.abs(dx) * WALK_FRAMES_PER_TILE

    local grounded = p.standing_on_uid ~= -1
    Hero.debug = {
        vx = model.vx, vy = p.velocityy, state = st, grounded = grounded,
        gx = Level.global_x(x), strip = Level.active.strip, tier = model.tier,
        skid = model.skidding,
    }
    if Trace.enabled() then
        Trace.row({
            tick = tick, strip = Level.active.strip, gx = Level.global_x(x), x = x, y = y,
            dx = dx, dy = dy, vx_model = model.vx, vx_ent = p.velocityx, vy_ent = p.velocityy,
            state = st, grounded = grounded, raw = raw, skid = model.skidding,
            tier = model.tier, jumped = model.jumped, blocked = blocked,
            cam_x = Camera.x(), anim = p.animation_frame,
        })
    end
end

return Hero
