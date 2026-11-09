--- Engine side of levels: loads a blank custom level, fills it with tiles from a
--- level grid (src/levelgrid.lua explains the strips), and handles the strip seam
--- and the bottom-of-screen kill plane.
---
--- The blank level comes from the vendored CustomLevels library and a generated
--- `Data/Levels/ssb_blank_8x<h>.lvl` (tools/build_assets.py). Tiles are placed from
--- Lua rather than authored in the .lvl because a grid cell will need to carry
--- more than a tile code can: what a block contains, where a pipe leads.

local custom_levels = require("src.vendor.custom_levels.custom_levels")
local Grid = require("src.levelgrid")

local Level = {}
SSB.Level = Level

--- World position of the centre of the top-left tile of an engine level.
local X0, Y0 = 3, 122

Level.defs = {
    require("src.levels.test_room"),
}

--- The level being played, or nil outside our levels:
--- { def, strips, strip (0-based, the one the hero is in), restarting }
Level.active = nil

--- World position of the centre of a cell in strip k.
--- @return number x, number y
function Level.world(k, local_col, row)
    return X0 + local_col, Y0 - (k * Grid.ROWS + row)
end

--- World x of the left edge of the playable area (the same for every strip).
function Level.left_edge()
    return X0 - 0.5
end

--- World x of the right edge of what may be shown in the current strip.
function Level.right_edge()
    local a = Level.active
    local remaining = a.def.width - Grid.strip_origin(a.strip)
    return X0 - 0.5 + math.min(Grid.STRIP_W, remaining)
end

--- World y the camera is locked to: rows 1..14 of the current strip fill the view.
function Level.view_center_y()
    return Y0 - (Level.active.strip * Grid.ROWS + 7.5)
end

--- Below this the hero has left the bottom of the screen.
function Level.kill_y()
    return Y0 - (Level.active.strip * Grid.ROWS + 14.9)
end

--- Where the blank .lvl puts the exit door (tools/build_assets.py): the far end
--- of the last strip, on the row the hero walks on. No tile is placed there.
--- @return integer strip, integer local_col, integer row
function Level.exit_cell()
    return Level.active.strips - 1, Grid.STRIP_W - 2, Grid.START_ROW
end

--- Position along the whole level, in tiles from its left end.
--- @param x number # world x
function Level.global_x(x)
    return Grid.strip_origin(Level.active.strip) + (x - X0)
end

-- ------------------------------------------------------------------- loading

set_callback(function(ctx)
    SafeCall("level/pre_load_level_files", function()
        Crumb(string.format("pre_load_level_files: screen=%s world=%s level=%s theme=%s",
            tostring(state.screen), tostring(state.world), tostring(state.level), tostring(state.theme)))
        if state.screen ~= SCREEN.LEVEL then
            custom_levels.unload_level()
            Level.active = nil
            return
        end
        local def = Level.defs[1]
        local problems = Grid.validate(def)
        if #problems > 0 then
            errorf("level %s is not usable: %s", tostring(def.name), table.concat(problems, "; "))
            custom_levels.unload_level()
            Level.active = nil
            return
        end
        local strips = Grid.strip_count(def.width)
        Level.active = { def = def, strips = strips, strip = 0, restarting = false }
        local file = string.format("ssb_blank_8x%d.lvl", strips * 2)
        Crumb("loading " .. def.name .. " as " .. file)
        custom_levels.set_hide_entrance(true)
        custom_levels.load_level_custom_theme(ctx, file,
            { theme = THEME.DWELLING, width = 8, height = strips * 2 })
        Crumb("level library accepted the level; the engine generates it next")
    end)
end, ON.PRE_LOAD_LEVEL_FILES)

-- Breadcrumbs through the engine's own level generation, to bracket a crash in it.
set_callback(function()
    if Level.active ~= nil then
        Crumb("pre_level_generation")
    end
end, ON.PRE_LEVEL_GENERATION)

set_callback(function()
    if Level.active ~= nil then
        Crumb(string.format("post_room_generation: level is %s x %s rooms",
            tostring(state.width), tostring(state.height)))
    end
end, ON.POST_ROOM_GENERATION)

set_callback(function()
    SafeCall("level/build", function()
        local a = Level.active
        if a == nil or state.screen ~= SCREEN.LEVEL then
            return
        end
        Crumb("post_level_generation: placing tiles")
        local placed = 0
        local exit_strip, exit_col, exit_row = Level.exit_cell()
        for k = 0, a.strips - 1 do
            local origin = Grid.strip_origin(k)
            for row = 0, Grid.ROWS - 1 do
                for lc = 0, Grid.STRIP_W - 1 do
                    local is_exit = k == exit_strip and lc == exit_col and row == exit_row
                    if not is_exit and Grid.is_solid(Grid.cell(a.def, origin + lc, row)) then
                        local x, y = Level.world(k, lc, row)
                        spawn_grid_entity(ENT_TYPE.FLOOR_GENERIC, x, y, LAYER.FRONT)
                        placed = placed + 1
                    end
                end
            end
        end
        Crumb(string.format("placed %d tiles in %d strips", placed, a.strips))
    end)
end, ON.POST_LEVEL_GENERATION)

-- ------------------------------------------------------------ during a level

--- Move the hero to the next strip once the camera is inside the repeated part.
--- @param p userdata # the hero
--- @param camera_x number # world x of the camera centre
--- @return number? dx, number? dy # how far everything moved, or nil
function Level.seam(p, camera_x)
    local a = Level.active
    if a.strip >= a.strips - 1 then
        return nil
    end
    if camera_x - X0 < Grid.SEAM_LOCAL then
        return nil
    end
    local dx, dy = -Grid.STEP, -Grid.ROWS
    local x, y = get_position(p.uid)
    p:set_position(x + dx, y + dy)
    a.strip = a.strip + 1
    SSB.Trace.event(string.format("seam: strip %d -> %d at frame %d", a.strip - 1, a.strip, get_frame()))
    return dx, dy
end

--- Reload the current level from its start.
--- @param why string
function Level.restart(why)
    local a = Level.active
    if a == nil or a.restarting then
        return
    end
    a.restarting = true
    SSB.Trace.event("restart: " .. why .. " at frame " .. get_frame())
    warp(state.world, state.level, state.theme)
end

--- @param p userdata
--- @return boolean # true if the hero fell out and a restart was started
function Level.check_fell_out(p)
    local _, y = get_position(p.uid)
    if y < Level.kill_y() then
        Level.restart("fell out of the level")
        return true
    end
    return false
end

return Level
