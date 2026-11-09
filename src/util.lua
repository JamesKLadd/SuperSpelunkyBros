--- Logging, error-safety and path helpers. Global, loaded first by main.lua.
--- Same shape as Modded-Online's src/util.lua (dbg / SafeCall / PackPath).

SSB = SSB or {}

--- Flip from the console for on-screen messages. The trace file does not need it.
SSB_DEBUG = SSB_DEBUG or false

local TAG = "[SSB] "

--- @param msg string
function dbg(msg)
    if SSB_DEBUG then
        print(TAG .. tostring(msg))
    end
end

--- @param fmt string
function dbgf(fmt, ...)
    if SSB_DEBUG then
        local ok, msg = pcall(string.format, fmt, ...)
        print(TAG .. (ok and msg or tostring(fmt)))
    end
end

--- A real problem: always printed, and written to the trace file if it is open.
--- @param fmt string
function errorf(fmt, ...)
    local ok, msg = pcall(string.format, fmt, ...)
    if not ok then
        msg = tostring(fmt)
    end
    print("[SSB ERROR] " .. msg)
    local trace = rawget(SSB, "Trace")
    if trace ~= nil and trace.event ~= nil then
        pcall(trace.event, "ERROR " .. msg)
    end
end

--- Errors already reported, so a callback that throws every frame says so once.
local reported = {}

--- Call fn(...) and report instead of throwing. An error inside an engine callback
--- otherwise disables the callback silently, or spams the screen 60 times a second.
--- @param callerName string
--- @param fn function
--- @return boolean ok, any result
function SafeCall(callerName, fn, ...)
    if type(fn) ~= "function" then
        if not reported[callerName] then
            reported[callerName] = true
            errorf("%s: not a function (%s)", callerName, type(fn))
        end
        return false, nil
    end
    local results = table.pack(xpcall(fn, function(err)
        return debug.traceback(tostring(err), 2)
    end, ...))
    if not results[1] then
        local key = callerName .. tostring(results[2]):sub(1, 80)
        if not reported[key] then
            reported[key] = true
            errorf("%s: %s", callerName, tostring(results[2]))
        end
        return false, nil
    end
    return true, table.unpack(results, 2, results.n)
end

--- get_player() normalised. Modded-Online observed it returning a NUMBER on 2.5
--- with the engine's player array in a bad state, which defeats every nil guard.
--- @param slot integer
--- @return userdata?
function SafePlayer(slot)
    local ok, p = pcall(get_player, slot, false)
    if not ok or p == nil or type(p) == "number" then
        return nil
    end
    return p
end

-- ----------------------------------------------------------------- pack path
--
-- Where this pack lives, taken from the path the engine loaded this very file
-- from. A pack unzipped one folder too deep still resolves correctly.

local FALLBACK_ROOT = "Mods/Packs/SuperSpelunkyBros"
local packRoot = nil

pcall(function()
    local info = debug.getinfo(1, "S")
    if info ~= nil and type(info.source) == "string" and info.source:sub(1, 1) == "@" then
        local source = info.source:sub(2):gsub("\\", "/")
        local root = source:match("^(.+)/src/util%.lua$")
        if root ~= nil then
            packRoot = root:gsub("^%./", "")
        end
    end
end)

--- @return string # e.g. "Mods/Packs/SuperSpelunkyBros"
function PackRootPath()
    return packRoot or FALLBACK_ROOT
end

--- A path inside this pack, in the forward-slash form io.open wants.
--- @param rest string
--- @return string
function PackPath(rest)
    return PackRootPath() .. "/" .. rest
end

--- True if a file exists in the pack folder. Needs unsafe mode (io); false without.
--- @param name string
--- @return boolean
function PackFileExists(name)
    local ok, found = pcall(function()
        local f = io.open(PackPath(name), "r")
        if f == nil then
            return false
        end
        f:close()
        return true
    end)
    return ok and found == true
end

return SSB
