--- Level grids and the strip layout. Pure Lua: no engine calls, so tests/ can run it.
---
--- A level is one long grid, GRID_ROWS tall and as wide as the design needs. The
--- engine's tile grid is only 86 columns wide (8 rooms), so a long level cannot
--- exist in one piece. It is cut into STRIPS stacked vertically in the engine
--- level, each STRIP_W columns wide, each repeating the last OVERLAP columns of
--- the one before. When the camera reaches the repeated part, src/level.lua moves
--- the hero and the camera down one strip to the same spot in the next: the screen
--- shows the same tiles before and after, so the cut is not seen.
---
---   global columns   0 ........ 51 52 ........ 79 80 ....... 103 104 ...
---   strip 0          [0 ........................ 79]
---   strip 1                        [0 ......... 27 28 ........................ 79]
---
--- Rows: 0 is the top. Rows 1..14 are on screen, row 14 is the visible ground row,
--- row 15 is ground below the screen edge, row 0 is hidden sky.

local Grid = {}
SSB.Grid = Grid

Grid.ROWS = 16          -- two engine rooms
Grid.STRIP_W = 80       -- eight engine rooms
Grid.OVERLAP = 28       -- must exceed the widest view the camera can have
Grid.STEP = Grid.STRIP_W - Grid.OVERLAP
Grid.GROUND_ROW = 14
Grid.START_COL = 4      -- every level starts here: the blank .lvl puts the door here
Grid.START_ROW = 13
--- Camera centre, in strip-local columns, at which the next strip takes over.
--- Half the overlap in: the view is inside the repeated part on both sides of it.
Grid.SEAM_LOCAL = Grid.STEP + Grid.OVERLAP / 2

Grid.AIR = "."
Grid.GROUND = "#"
Grid.BLOCK = "B"

local SOLID = { ["#"] = true, ["B"] = true }

--- @param ch string
--- @return boolean
function Grid.is_solid(ch)
    return SOLID[ch] == true
end

local Builder = {}
Builder.__index = Builder

--- A blank level of `width` columns with solid ground along the bottom.
--- Columns and rows are 0-based throughout.
--- @param width integer
function Grid.new(width)
    local g = setmetatable({ width = width, cells = {} }, Builder)
    for r = 0, Grid.ROWS - 1 do
        local row = {}
        for c = 0, width - 1 do
            row[c] = r >= Grid.GROUND_ROW and Grid.GROUND or Grid.AIR
        end
        g.cells[r] = row
    end
    return g
end

function Builder:set(c, r, ch)
    assert(c >= 0 and c < self.width, "column out of range: " .. tostring(c))
    assert(r >= 0 and r < Grid.ROWS, "row out of range: " .. tostring(r))
    self.cells[r][c] = ch
    return self
end

function Builder:fill(c0, r0, c1, r1, ch)
    for r = r0, r1 do
        for c = c0, c1 do
            self:set(c, r, ch)
        end
    end
    return self
end

--- A bottomless gap in the ground, columns c0..c1.
function Builder:pit(c0, c1)
    return self:fill(c0, Grid.GROUND_ROW, c1, Grid.ROWS - 1, Grid.AIR)
end

--- A one-tile-deep dip: the visible ground row removed, the row below kept.
function Builder:trench(c0, c1)
    return self:fill(c0, Grid.GROUND_ROW, c1, Grid.GROUND_ROW, Grid.AIR)
end

--- A solid pillar `height` tiles tall standing on the ground at column c.
function Builder:pillar(c, height, ch)
    return self:fill(c, Grid.GROUND_ROW - height, c, Grid.GROUND_ROW - 1, ch or Grid.GROUND)
end

--- A floating ledge whose top surface is `height` tiles above the ground.
function Builder:shelf(c0, c1, height, ch)
    local r = Grid.GROUND_ROW - height
    return self:fill(c0, r, c1, r, ch or Grid.BLOCK)
end

--- @param meta table # { name = string }
--- @return table # { name, width, rows = string[16] (index 1 = top row) }
function Builder:finish(meta)
    local rows = {}
    for r = 0, Grid.ROWS - 1 do
        local chars = {}
        for c = 0, self.width - 1 do
            chars[c + 1] = self.cells[r][c]
        end
        rows[r + 1] = table.concat(chars)
    end
    return { name = meta.name, width = self.width, rows = rows }
end

--- The cell at global column c, row r. Past the right end of the design it is
--- solid, so the last strip closes with a wall instead of an open edge.
--- @return string
function Grid.cell(level, c, r)
    if c < 0 or c >= level.width then
        return Grid.GROUND
    end
    return level.rows[r + 1]:sub(c + 1, c + 1)
end

--- How many strips a level of this width needs.
--- @param width integer
--- @return integer
function Grid.strip_count(width)
    if width <= Grid.STRIP_W then
        return 1
    end
    return math.ceil((width - Grid.STRIP_W) / Grid.STEP) + 1
end

--- Global column of local column 0 in strip k (0-based).
function Grid.strip_origin(k)
    return k * Grid.STEP
end

--- Problems with a level, as a list of strings. Empty means it is usable.
--- @return string[]
function Grid.validate(level)
    local problems = {}
    if #level.rows ~= Grid.ROWS then
        problems[#problems + 1] = "expected " .. Grid.ROWS .. " rows, got " .. #level.rows
        return problems
    end
    for i, row in ipairs(level.rows) do
        if #row ~= level.width then
            problems[#problems + 1] = "row " .. (i - 1) .. " is " .. #row .. " wide, not " .. level.width
        end
    end
    if #problems > 0 then
        return problems
    end
    if Grid.is_solid(Grid.cell(level, Grid.START_COL, Grid.START_ROW)) then
        problems[#problems + 1] = "the start cell is solid"
    end
    if not Grid.is_solid(Grid.cell(level, Grid.START_COL, Grid.START_ROW + 1)) then
        problems[#problems + 1] = "there is no ground under the start cell"
    end
    if Grid.strip_count(level.width) * 2 > 15 then
        problems[#problems + 1] = "too wide: needs more than 15 engine rooms of height"
    end
    return problems
end

return Grid
