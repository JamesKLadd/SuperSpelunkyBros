"""Every engine name our Lua uses must exist in the real API.

Nobody can run Spelunky 2 in CI, so the next best thing: the names are checked
against tests/api_manifest.json, generated from Overlunky's own definitions
(tools/update_api_manifest.py). An invented or misspelt function, enum member or
field fails here instead of in the game.

This checks NAMES, not behaviour: that a hook does what its documentation says is
what the in-game checklist in README.md is for.
"""

import re

import pytest

from conftest import MANIFEST, OWN_LUA, PACK

FUNCTIONS = set(MANIFEST["functions"])
FIELDS = set(MANIFEST["fields"])
ENUMS = MANIFEST["enums"]

LUA_GLOBALS = {
    "assert", "error", "ipairs", "pairs", "pcall", "xpcall", "print", "rawget", "rawset",
    "require", "select", "setmetatable", "getmetatable", "tostring", "tonumber", "type",
    "next", "load", "dofile",
}
LUA_KEYWORDS = {"function", "if", "elseif", "while", "for", "and", "or", "not", "return", "until", "in"}

#: Variables that hold engine objects in our code. An attribute read off one of
#: these must be a real field or method of some engine type.
ENGINE_ROOTS = {"state", "p", "self", "cam", "slot", "draw_ctx", "def"}
#: ...except in files where `self`/`def` are our own tables.
OWN_TABLE_FILES = {"levelgrid.lua": {"self", "def"}, "level.lua": {"def"}}


def strip_comments_and_strings(src: str) -> str:
    src = re.sub(r"--\[\[.*?\]\]", "", src, flags=re.S)
    src = re.sub(r"--[^\n]*", "", src)
    src = re.sub(r'"(?:\\.|[^"\\])*"', '""', src)
    src = re.sub(r"'(?:\\.|[^'\\])*'", "''", src)
    return src


def own_definitions(sources: dict) -> set[str]:
    names = set()
    for src in sources.values():
        names.update(re.findall(r"\bfunction\s+([A-Za-z_]\w*)\s*\(", src))
        names.update(re.findall(r"\blocal\s+function\s+([A-Za-z_]\w*)", src))
        names.update(re.findall(r"\blocal\s+([A-Za-z_]\w*)\s*=", src))
        for group in re.findall(r"\bfunction\s*\(([^)]*)\)|\bfunction\s+[\w.:]+\s*\(([^)]*)\)", src):
            for params in group:
                names.update(n.strip() for n in params.split(",") if n.strip() and n.strip() != "...")
    return names


SOURCES = {p: strip_comments_and_strings(p.read_text(encoding="utf-8")) for p in OWN_LUA}
OWN = own_definitions(SOURCES)


@pytest.mark.parametrize("path", OWN_LUA, ids=lambda p: p.relative_to(PACK).as_posix())
def test_global_functions_exist(path):
    src = SOURCES[path]
    unknown = set()
    for match in re.finditer(r"(?<![\w.:])([A-Za-z_]\w*)\s*\(", src):
        name = match.group(1)
        if name in LUA_GLOBALS or name in LUA_KEYWORDS or name in OWN:
            continue
        if name not in FUNCTIONS:
            unknown.add(name)
    assert not unknown, f"not in the Spelunky 2 Lua API: {sorted(unknown)}"


@pytest.mark.parametrize("path", OWN_LUA, ids=lambda p: p.relative_to(PACK).as_posix())
def test_enum_members_exist(path):
    src = SOURCES[path]
    unknown = set()
    for enum, member in re.findall(r"\b([A-Z][A-Z_]+)\.([A-Z_][A-Z_0-9]*)\b", src):
        if enum in ENUMS and member not in ENUMS[enum]:
            unknown.add(f"{enum}.{member}")
    assert not unknown, f"not in the Spelunky 2 Lua API: {sorted(unknown)}"


@pytest.mark.parametrize("path", OWN_LUA, ids=lambda p: p.relative_to(PACK).as_posix())
def test_engine_fields_exist(path):
    src = SOURCES[path]
    roots = ENGINE_ROOTS - OWN_TABLE_FILES.get(path.name, set())
    unknown = set()
    for chain in re.findall(r"(?<![\w.:])([A-Za-z_]\w*(?:[.:][A-Za-z_]\w*)+)", src):
        parts = re.split(r"[.:]", chain)
        if parts[0] not in roots:
            continue
        for name in parts[1:]:
            if name not in FIELDS:
                unknown.add(chain)
    assert not unknown, f"fields or methods not in the Spelunky 2 Lua API: {sorted(unknown)}"


def test_the_checks_can_fail():
    """Guard against a scanner that silently matches nothing."""
    assert "spawn_grid_entity" in FUNCTIONS and "definitely_not_a_function" not in FUNCTIONS
    assert "POST_PROCESS_INPUT" in ENUMS["ON"] and "NOT_AN_EVENT" not in ENUMS["ON"]
    assert "velocityx" in FIELDS and "velocityxx" not in FIELDS
    used = set()
    for src in SOURCES.values():
        used.update(re.findall(r"(?<![\w.:])([A-Za-z_]\w*)\s*\(", src))
    assert {"set_callback", "spawn_grid_entity", "warp", "zoom"} <= used
