# CustomLevels (vendored)

`custom_levels.lua` is an unmodified copy of
<https://github.com/jaythebusinessgoose/CustomLevels> at commit
`0d5cc502d7cb549d60400ad0dd91971920c7ba0e` (2025-01-07), Apache License 2.0
(see `LICENSE`).

It loads a `.lvl` file as a level of any size up to 8 x 15 rooms, with a custom
theme, and removes the procedural spawns a hand-built level does not want.
`src/level.lua` is the only file that uses it.

To update: replace `custom_levels.lua` with the newer file and change the commit
above. Do not edit it in place.

## One thing we undo

`src/level.lua` clears the library's `floor_spread_callback` after every load
(through `custom_levels.state`). That callback destroys every entity spawned as
"floor spreading", and the engine classes any floor a script places during
level generation as exactly that, so it deleted our whole level. When updating
the library, check that `state.floor_spread_callback` still exists;
`tests/test_game_flow.py` covers our side.
