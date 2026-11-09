--- Ties the modules to the engine's callbacks and fixes the order they run in.
---
---   POST_PROCESS_INPUT  hero takes the real buttons, hides some from the engine
---   PRE_UPDATE          kill plane -> strip seam -> hero model writes velocity
---   (engine update)     collision, jump start, our gravity / friction hooks
---   POST_UPDATE         camera follows -> hero observes the result, trace row
---   GUIFRAME            debug overlay: draws only, reads only
---
--- Nothing that affects the simulation runs in a render callback.

local Level = require("src.level")
local Camera = require("src.camera")
local Hero = require("src.hero")
local Trace = require("src.trace")
local Assets = require("src.assets")
local Physics = require("src.physics")

local Game = {}
SSB.Game = Game

local overlay = false
local first_frame = false -- breadcrumb the first driven frame of each level

--- The hero entity, if the one we took over at level start is still the player.
local function hero()
    if not Hero.active() or Level.active.restarting then
        return nil
    end
    local p = SafePlayer(1)
    if p == nil or p.uid ~= Hero.uid() then
        return nil
    end
    return p
end

local function stop()
    if Hero.uid() ~= -1 then
        Hero.stop()
        Camera.stop()
        Trace.close()
        zoom_reset()
        set_time_ghost_enabled(true)
    end
end

set_callback(function()
    SafeCall("game/level_start", function()
        Hero.stop()
        if Level.active == nil then
            return
        end
        local p = SafePlayer(1)
        if p == nil then
            errorf("level start: there is no player 1")
            return
        end
        local x0, y0 = get_position(p.uid)
        Crumb(string.format("level start: player uid %s at %.2f, %.2f state %s",
            tostring(p.uid), x0, y0, tostring(p.state)))
        Crumb("hero texture")
        local dressed = Assets.dress_hero(p)
        Crumb(dressed)
        Hero.start(p)
        Crumb("hooks: " .. Hero.hook_report())
        Crumb("camera")
        Camera.start(p)
        set_time_ghost_enabled(false) -- these levels have their own clock, later
        first_frame = true
        overlay = Trace.flagged()
        local x, y = get_position(p.uid)
        Trace.open({
            "Super Spelunky Bros " .. tostring(meta.version) .. "  level " .. Level.active.def.name,
            string.format("strips %d  start x %.2f y %.2f  zoom %.3f  view width %.2f tiles",
                Level.active.strips, x, y, Camera.ZOOM, Camera.VIEW_W),
            "hooks: " .. Hero.hook_report(),
            "input phase: " .. (ON.POST_PROCESS_INPUT ~= nil and "POST_PROCESS_INPUT" or "PRE_UPDATE only"),
            dressed,
            "units: tiles and tiles/frame. state is CHAR_STATE, raw is the INPUTS bitmask.",
        }, Hero.TRACE_COLUMNS)
        Crumb("level start done")
    end)
end, ON.LEVEL)

set_callback(function()
    SafeCall("game/screen", function()
        if state.screen ~= SCREEN.LEVEL then
            stop()
        end
    end)
end, ON.SCREEN)

if ON.POST_PROCESS_INPUT ~= nil then
    set_callback(function()
        SafeCall("game/input", Hero.input_phase)
    end, ON.POST_PROCESS_INPUT)
end

set_callback(function()
    SafeCall("game/pre_update", function()
        local p = hero()
        if p == nil then
            return
        end
        if first_frame then
            Crumb("first frame: pre_update")
        end
        if Level.check_fell_out(p) then
            return
        end
        local dx = Level.seam(p, Camera.x())
        if dx ~= nil then
            Camera.shift(dx)
        end
        Hero.pre_update(p)
    end)
    -- never return true from PRE_UPDATE: that freezes the engine
end, ON.PRE_UPDATE)

set_callback(function()
    SafeCall("game/post_update", function()
        local p = hero()
        if p == nil then
            return
        end
        if first_frame then
            Crumb("first frame: engine update finished, post_update")
        end
        Camera.update(p)
        Hero.post_update(p)
        if first_frame then
            first_frame = false
            Crumb("first frame done: running")
        end
    end)
end, ON.POST_UPDATE)

set_callback(function(draw_ctx)
    if not overlay or not Hero.active() then
        return
    end
    local d = Hero.debug
    if d.vx == nil then
        return
    end
    -- speeds in 8-bit pixels per frame (16 to a tile), the unit the tuning is written in
    local text = string.format("vx %+.2f px/f (walk %.2f run %.2f)  vy %+.2f  %s%s  tier %d  x %.1f  strip %d  state %d",
        d.vx * 16, Physics.TUNING.walk_max * 16, Physics.TUNING.run_max * 16, d.vy * 16,
        d.grounded and "ground" or "air", d.skid and " SKID" or "", d.tier, d.gx, d.strip, d.state)
    draw_ctx:draw_text(-0.95, 0.72, 22, text, rgba(255, 255, 255, 255))
end, ON.GUIFRAME)

set_callback(function()
    stop()
    Assets.restore()
end, ON.SCRIPT_DISABLE)

return Game
