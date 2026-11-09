-- Super Spelunky Bros (working title): a momentum platformer inside Spelunky 2.
--
-- Playlunky script mod for Spelunky 2 v2.5. Start a run from the camp as usual;
-- every level is replaced by one of ours. README.md has the install steps and the
-- test checklist, docs/COMPROMISES.md what was bent to fit the engine.

meta = {
    name = "Super Spelunky Bros",
    version = "0.1.0",
    description = "Momentum platforming with stomps, power-ups, a whip and two ropes",
    author = "JamesKLadd",
    online_safe = false,
    unsafe = true, -- io: the trace file and the flag-file check
}

require("src.util")

-- Order matters only in that each module's requires come before it; listing them
-- all here makes a load failure name the module it happened in.
local MODULES = {
    "src.trace",
    "src.physics",
    "src.levelgrid",
    "src.level",
    "src.camera",
    "src.assets",
    "src.hero",
    "src.game",
}

for _, path in ipairs(MODULES) do
    SafeCall("main/require " .. path, require, path)
end

dbg("loaded " .. meta.version .. " from " .. PackRootPath())
