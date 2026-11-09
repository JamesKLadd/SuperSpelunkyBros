# Compromises

Where the mod bends to fit Spelunky 2's engine, and what was done about it.
Each entry says whether it has been seen in the game yet: nothing here can be
run outside it, so "untested" means exactly that.

## Levels

**Levels are cut into strips.** The engine's tile grid is 86 x 126
(`layer.hpp`), which is 8 rooms across. A level longer than 80 tiles is built
as several 80-wide strips stacked vertically, each repeating the last 28
columns of the one before. When the camera centre reaches the middle of the
repeated part, the hero and camera are moved 52 left and 16 down in one frame.
`src/levelgrid.lua` has the layout. *Untested in game.*

Consequences:

- A level can be at most 7 strips: 80 + 6 x 52 = 392 tiles long.
- Anything that moves and is on screen at the cut has to be moved too. Right
  now only the hero is. A rope thrown inside the repeated part will be left
  behind in the old strip. To fix when ropes get their balancing pass.
- The cave background and the dirt tiles pick random variants, so the picture
  can visibly change at the cut even though the layout is identical. This goes
  away when the level art is replaced with our own tiles and backdrop.
- Blocks that can change (bricks, item blocks) will need their state applied
  to both copies when they sit in a repeated part.

**The visible area is 14 rows by about 25 columns.** The zoom is set so
exactly 14 rows fit (`src/camera.lua`); Spelunky's picture is 16:9, so that is
24.9 columns, wider than a 4:3 console screen. Levels are 16 rows tall with
rows 1 to 14 on screen. The numbers assume a 16:9 window; an ultrawide window
shows more columns than the 28-column overlap allows for.

**Tiles are placed from Lua, not authored in `.lvl` files.** The `.lvl` files
are blank rooms plus an entrance and an exit door.

**Every level has a vanilla exit door** at the far end of its last strip,
because the engine expects one. In the test room it is reachable and leads to
the next level, which is the test room again. Real levels will end at their own
goal; what to do with the door then (wall it in, or use it as the way out after
the goal) is open.

## Movement

**The engine still does collision.** The model in `src/physics.lua` decides
speeds; the engine moves the entity and resolves contact. Sub-pixel behaviour
at corners is Spelunky's.

**The engine still decides when a jump starts** (button press, ground check,
its coyote time and jump buffering). Only the strength and the gravity are
ours. If Spelunky's coyote window feels wrong it can be changed through
`Player.coyote_timer`.

**Jump height is corrected for update order.** Whether the engine applies
gravity before or after moving is not known. `src/hero.lua` detects a short
first step and gives one gravity step back, so a standing jump tops out a
little over 4 tiles either way. *Untested in game; the trace says which order
it is.*

**Friction and gravity are replaced through entity hooks**
(`set_pre_apply_friction`, `set_pre_fall`), only while the hero is in a normal
state and, for gravity, only while airborne. On ropes, when stunned and in
doorways the engine's own apply. *Untested in game.*

**Ledge-grab is removed in the player's state machine.** The engine grabs a
ledge even with no direction held (seen in game). The hanging state is wrapped
so it can never force itself, and the jumping and falling states so they can
never choose it (`src/hero.lua`, `remove_ledge_grab`). If a grab still gets
through, the hero is dropped in the same frame with the speed it had. An empty
`ssb_vanilla_ledge.on` in the pack folder turns the wrapping off. *The wrapping
is untested in game.*

**Facing changes in the air.** A strict 8-bit platformer locks facing while
airborne; here the hero turns with the stick so the whip can be aimed.

**No fall damage or fall stun.** `falling_timer` is cleared every frame.

## Hero

**Nothing can hurt the hero yet.** All damage and stuns are cancelled and
written to the trace. The three-hit health system and the level-restart /
back-to-camp rules arrive with the power-up milestone. Falling out of the
bottom of the level restarts it.

**The whole character sheet is replaced.** The hero's sheet replaces whichever
character player 1 picked (`replace_texture`), because the whip and rope are
drawn from the same sheet. It is done before the level is generated: an entity
that already exists keeps the sheet it was created with. It is put back when
the script is disabled.

With the **Keep my selected character** option on, nothing is replaced and the
skid pose is not shown: vanilla-layout sheets have no cell for it.

**Tiles and background are still the Dwelling's.** Only the layout is ours so
far. Our own tile set and backdrop come with the blocks milestone.

## Not possible, as far as is known

- Pixel-exact 8-bit collision.
- A 4:3 picture.
