--- Movement test room. Not a real level: a set of rulers for tuning the physics,
--- and two strips so the seam and the forward-only camera get exercised too.
---
--- Left to right (global columns):
---    4 - 27   flat runway: acceleration, top speeds, skid turnaround
---   30 - 55   height ruler: ledges 2, 3, 4, 5 and 6 tiles up, walkable underneath
---   57 - 62   low ceiling 3 tiles up: head bonk
---   66 - 99   distance ruler: trenches 2, 3, 4 and 6 tiles wide (not lethal)
---  ~66        the strip seam passes here (camera centre at column 66)
---  104 - 107  staircase up 1-2-3-4
---  112 - 114  a real pit: falling in restarts the level
---  120        a 3-tile wall to press against: no wall-cling, no ledge-grab
---  131        end wall

local Grid = require("src.levelgrid")

local g = Grid.new(132)

-- left wall, so the first screen has an edge
g:fill(0, 0, 0, Grid.GROUND_ROW - 1, Grid.GROUND)

-- height ruler
g:shelf(30, 31, 2)
g:shelf(35, 36, 3)
g:shelf(40, 41, 4)
g:shelf(46, 47, 5) -- needs a run-up
g:shelf(53, 54, 6) -- out of reach on purpose

-- low ceiling
g:shelf(57, 62, 3, Grid.GROUND)

-- distance ruler
g:trench(66, 67)
g:trench(72, 74)
g:trench(80, 83)
g:trench(94, 99) -- needs a run-up

-- staircase
for step = 1, 4 do
    g:pillar(103 + step, step)
end

-- real pit
g:pit(112, 114)

-- wall to press against
g:pillar(120, 3)

-- end wall
g:fill(131, 0, 131, Grid.GROUND_ROW - 1, Grid.GROUND)

return g:finish({ name = "test_room" })
