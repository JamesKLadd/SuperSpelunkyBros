--- Per-frame trace file, switched on by a flag file.
---
--- Create an empty file named `ssb_trace.on` in this pack's folder (next to
--- main.lua) and every level writes `ssb_trace.log` there: a header, then one CSV
--- row per engine frame, with `# event` lines in between. Delete the flag file to
--- turn it off. The flag is re-read at every level start, so no restart is needed.
---
--- Rows are keyed on frame counts, never on wall-clock time, so two captures of
--- the same inputs line up.

local Trace = {}
SSB.Trace = Trace

local FLAG = "ssb_trace.on"
local LOG = "ssb_trace.log"
local FLUSH_EVERY = 30

local handle = nil
local unflushed = 0
local columns = nil

--- @return boolean
function Trace.enabled()
    return handle ~= nil
end

--- True when the flag file is present, whether or not a log is open.
--- @return boolean
function Trace.flagged()
    return PackFileExists(FLAG) or PackFileExists(FLAG .. ".txt")
end

function Trace.close()
    if handle ~= nil then
        pcall(function()
            handle:flush()
            handle:close()
        end)
    end
    handle = nil
    columns = nil
end

--- Open (truncating) the log if the flag file is there. Called at level start.
--- @param header string[] # free-form lines describing the run
--- @param cols string[] # CSV column names for Trace.row
function Trace.open(header, cols)
    Trace.close()
    if not Trace.flagged() then
        return
    end
    local ok = pcall(function()
        handle = io.open(PackPath(LOG), "w")
    end)
    if not ok or handle == nil then
        handle = nil
        print("[SSB] ssb_trace.on is present but ssb_trace.log could not be opened"
            .. " (is unsafe mode on?)")
        return
    end
    columns = cols
    pcall(function()
        for _, line in ipairs(header) do
            handle:write("# " .. line .. "\n")
        end
        handle:write(table.concat(cols, ",") .. "\n")
        handle:flush()
    end)
end

--- One frame. `values` is keyed by column name; missing columns are left empty.
--- @param values table
function Trace.row(values)
    if handle == nil then
        return
    end
    local out = {}
    for i, name in ipairs(columns) do
        local v = values[name]
        if v == nil then
            out[i] = ""
        elseif type(v) == "number" then
            if math.type(v) == "integer" then
                out[i] = tostring(v)
            else
                out[i] = string.format("%.5f", v)
            end
        elseif type(v) == "boolean" then
            out[i] = v and "1" or "0"
        else
            out[i] = tostring(v)
        end
    end
    pcall(function()
        handle:write(table.concat(out, ",") .. "\n")
        unflushed = unflushed + 1
        if unflushed >= FLUSH_EVERY then
            unflushed = 0
            handle:flush()
        end
    end)
end

--- A one-off line, flushed immediately: a crash right after it must not eat it.
--- @param text string
function Trace.event(text)
    if handle == nil then
        return
    end
    pcall(function()
        handle:write("# " .. tostring(text) .. "\n")
        handle:flush()
    end)
end

return Trace
