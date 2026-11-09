--- Forward-only camera. It scrolls right to keep the hero just left of centre,
--- never scrolls back, and its height is locked to the strip. Its left edge is a
--- wall for the hero.
---
--- All of it runs from update callbacks and depends only on the hero's position,
--- so two machines fed the same inputs compute the same camera.

local Level = require("src.level")

local Camera = {}
SSB.Camera = Camera

--- Half the view width in tiles is ZF * zoom, half the height ZF * 9/16 * zoom
--- (overlunky state.hpp / state.cpp, for a 16:9 picture). The default zoom is 13.5,
--- about 20 x 11 tiles. This one shows exactly 14 rows.
local ZF = 0.737
Camera.ZOOM = 7.0 / (ZF * 9.0 / 16.0)
Camera.VIEW_W = 2.0 * ZF * Camera.ZOOM

--- The hero is held this many tiles left of the centre while scrolling.
Camera.LEAD = 1.0

--- How close to the left edge of the view the hero's centre may get.
Camera.WALL_MARGIN = 0.45

local x = nil -- world x of the camera centre; nil until a level starts

local function clamp_to_strip(value)
    local half = Camera.VIEW_W / 2
    local lo = Level.left_edge() + half
    local hi = Level.right_edge() - half
    if hi < lo then
        hi = lo
    end
    if value < lo then
        return lo
    end
    if value > hi then
        return hi
    end
    return value
end

--- Write our position to the engine camera.
--- @param snap boolean # also move the already-tweened position, for cuts
local function apply(snap)
    local cam = state.camera
    local y = Level.view_center_y()
    cam.focused_entity_uid = -1
    cam.focus_offset_x = 0
    cam.focus_offset_y = 0
    cam.focus_x = x
    cam.focus_y = y
    cam.inertia = 5.0 -- follow rigidly: 5 is "move the whole distance each frame"
    if snap then
        cam.adjusted_focus_x = x
        cam.adjusted_focus_y = y
        cam.calculated_focus_x = x
        cam.calculated_focus_y = y
    end
end

--- @return number? # world x of the camera centre
function Camera.x()
    return x
end

--- World x the hero's centre may not go left of.
function Camera.left_wall()
    return x - Camera.VIEW_W / 2 + Camera.WALL_MARGIN
end

--- Level start: zoom out and put the camera on the hero.
--- @param p userdata
function Camera.start(p)
    zoom(Camera.ZOOM)
    local px = get_position(p.uid)
    x = clamp_to_strip(px + Camera.LEAD)
    apply(true)
end

--- Everything was moved to the next strip: move with it, without a visible pan.
function Camera.shift(dx)
    x = clamp_to_strip(x + dx)
    apply(true)
end

--- Once per frame, after the hero has moved.
--- @param p userdata
function Camera.update(p)
    if x == nil then
        return
    end
    local px = get_position(p.uid)
    local target = px + Camera.LEAD
    if target > x then
        x = target
    end
    x = clamp_to_strip(x)
    apply(false)
end

function Camera.stop()
    x = nil
end

return Camera
