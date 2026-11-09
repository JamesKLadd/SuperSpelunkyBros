--- The hero's movement model. Pure Lua: no engine calls, so tests/ can run it.
---
--- Units are tiles per frame (and tiles per frame^2) at the engine's 60 fps,
--- which is what Movable.velocityx / velocityy hold. The numbers are a classic
--- 8-bit platformer feel expressed in 16-pixel tiles: momentum on the ground, a
--- skid when reversing, a jump whose height depends on how long the button is held
--- and whose strength depends on run-up speed, and momentum kept in the air.
---
--- src/hero.lua owns the engine side: it feeds this the buttons and whether the
--- hero is standing, writes `vx` to the entity, and asks it for the jump impulse
--- and for gravity. Collision stays the engine's job.

local Physics = {}
SSB.Physics = Physics

local PX = 1 / 16 -- one 8-bit pixel, in tiles

--- Every number that shapes the feel. Tune here; tests/test_physics.py pins the
--- resulting jump heights and distances so a change is a visible decision.
Physics.TUNING = {
    -- ground
    walk_max = 1.5625 * PX,         -- top walking speed
    run_max = 2.5625 * PX,          -- top running speed (run button held)
    min_walk = 0.07421875 * PX,     -- speed snapped to when starting from rest
    walk_accel = 0.037109375 * PX,
    run_accel = 0.0556640625 * PX,
    release_decel = 0.05078125 * PX, -- no direction held
    skid_decel = 0.1015625 * PX,     -- opposite direction held
    skid_turn_speed = 0.5625 * PX,   -- below this a skid ends and the hero turns

    -- air: which backward acceleration applies depends on speed at takeoff
    air_brake_threshold = 1.8125 * PX,

    -- jump, in three tiers picked by horizontal speed at takeoff
    tier_speed = { 1.0 * PX, 2.3125 * PX }, -- below [1]: tier 1, below [2]: tier 2, else 3
    jump_velocity = { 4.0 * PX, 4.0 * PX, 5.0 * PX },
    gravity_hold = { 0.125 * PX, 0.1171875 * PX, 0.15625 * PX }, -- rising, jump held
    gravity_fall = { 0.4375 * PX, 0.375 * PX, 0.5625 * PX },     -- everything else
    max_fall = 4.0 * PX,
}

--- @return table # fresh movement state
function Physics.new()
    return {
        vx = 0.0,
        facing = 1,        -- 1 right, -1 left
        skidding = false,
        tier = 1,          -- jump tier chosen at the last takeoff
        takeoff_speed = 0.0,
        air_cap = Physics.TUNING.walk_max,
        jumped = false,    -- airborne because of a jump (not a walk-off)
    }
end

local function approach(value, target, step)
    if value < target then
        return math.min(value + step, target)
    end
    return math.max(value - step, target)
end

--- Advance horizontal speed by one frame.
--- @param s table # state from Physics.new
--- @param inp table # { left, right, run, down } booleans
--- @param grounded boolean
--- @return number vx
function Physics.step(s, inp, grounded)
    local T = Physics.TUNING
    local dir = (inp.right and 1 or 0) - (inp.left and 1 or 0)
    if grounded and inp.down then
        dir = 0 -- ducking: slide on what momentum there is
    end
    local vx = s.vx
    s.skidding = false

    if grounded then
        local max = inp.run and T.run_max or T.walk_max
        local accel = inp.run and T.run_accel or T.walk_accel
        if dir == 0 then
            vx = approach(vx, 0.0, T.release_decel)
        elseif vx ~= 0 and (vx > 0) ~= (dir > 0) then
            s.skidding = true
            vx = approach(vx, 0.0, T.skid_decel)
            if math.abs(vx) < T.skid_turn_speed then
                vx = 0.0
            end
        elseif math.abs(vx) > max then
            -- let go of run at full speed: ease down to a walk, don't snap
            vx = approach(vx, dir * max, T.release_decel)
        else
            local speed = math.abs(vx)
            if speed < T.min_walk then
                speed = T.min_walk
            end
            vx = dir * math.min(speed + accel, max)
        end
    elseif dir ~= 0 then
        local forward = vx == 0 or (vx > 0) == (dir > 0)
        local accel
        if forward then
            accel = math.abs(vx) < T.walk_max and T.walk_accel or T.run_accel
        elseif math.abs(vx) >= T.walk_max then
            accel = T.run_accel
        elseif s.takeoff_speed < T.air_brake_threshold then
            accel = T.walk_accel
        else
            accel = T.release_decel
        end
        vx = vx + dir * accel
        if vx > s.air_cap then
            vx = s.air_cap
        elseif vx < -s.air_cap then
            vx = -s.air_cap
        end
    end
    -- no direction in the air: momentum is kept as is

    if dir ~= 0 then
        s.facing = dir
    end
    s.vx = vx
    return vx
end

--- Which jump tier a horizontal speed selects.
--- @param speed number # absolute horizontal speed
--- @return integer # 1, 2 or 3
function Physics.tier_for_speed(speed)
    local T = Physics.TUNING
    if speed < T.tier_speed[1] then
        return 1
    elseif speed < T.tier_speed[2] then
        return 2
    end
    return 3
end

--- The hero has just left the ground. Fixes the jump tier and the air speed cap
--- for this whole airtime from the speed at that moment.
--- @param s table
--- @param jumped boolean # true for a jump, false for walking off a ledge
function Physics.takeoff(s, jumped)
    local T = Physics.TUNING
    local speed = math.abs(s.vx)
    s.tier = Physics.tier_for_speed(speed)
    s.takeoff_speed = speed
    s.air_cap = speed > T.walk_max and T.run_max or T.walk_max
    s.jumped = jumped
end

--- Upward speed for a jump started now, at the current horizontal speed.
--- Does not change the state: the engine may ask more than once.
--- @param s table
--- @return number
function Physics.jump_velocity(s)
    return Physics.TUNING.jump_velocity[Physics.tier_for_speed(math.abs(s.vx))]
end

--- Gravity for this frame, as a positive number to subtract from velocityy.
--- Light while rising with jump held, heavy otherwise: that is the variable jump.
--- @param s table
--- @param jump_held boolean
--- @param vy number # current vertical speed, up is positive
--- @return number
function Physics.gravity(s, jump_held, vy)
    local T = Physics.TUNING
    if s.jumped and jump_held and vy > 0 then
        return T.gravity_hold[s.tier]
    end
    return T.gravity_fall[s.tier]
end

--- @param s table
function Physics.land(s)
    s.jumped = false
end

--- The engine stopped the hero against something solid.
--- @param s table
function Physics.hit_wall(s)
    s.vx = 0.0
    s.skidding = false
end

return Physics
