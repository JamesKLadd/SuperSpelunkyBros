"""Shared helpers. Run everything with:  python -m pytest tests -q

Needs:  pip install pytest lupa pillow
"""

from __future__ import annotations

import json
import pathlib
import shutil

import pytest
from lupa import lua54  # the game embeds Lua 5.4; lupa's default is newer

PACK = pathlib.Path(__file__).resolve().parent.parent
TESTS = PACK / "tests"
MANIFEST = json.loads((TESTS / "api_manifest.json").read_text(encoding="utf-8"))

#: Our own Lua, without third-party code.
OWN_LUA = sorted([PACK / "main.lua"] + [p for p in (PACK / "src").rglob("*.lua") if "vendor" not in p.parts])
ALL_LUA = sorted([PACK / "main.lua"] + list((PACK / "src").rglob("*.lua")))


def new_lua(root: pathlib.Path) -> lua54.LuaRuntime:
    """A Lua whose `require("src.x")` finds files under `root`."""
    rt = lua54.LuaRuntime(unpack_returned_tuples=True)
    rt.globals().package.path = f"{root.as_posix()}/?.lua"
    return rt


def enum_source() -> str:
    """Lua source defining every engine enum with its real values."""
    out = []
    for name, members in MANIFEST["enums"].items():
        body = ", ".join(f'["{k}"] = {v}' for k, v in members.items())
        out.append(f"{name} = {{ {body} }}")
    return "\n".join(out)


@pytest.fixture
def pure_lua():
    """Lua with only the SSB table: for the modules that make no engine calls."""
    rt = new_lua(PACK)
    rt.execute("SSB = {}")
    return rt


@pytest.fixture
def pack(tmp_path):
    """A scratch copy of the pack, so tests can add flag files and outputs to it."""
    root = tmp_path / "Mods" / "Packs" / "SuperSpelunkyBros"
    root.mkdir(parents=True)
    shutil.copy(PACK / "main.lua", root / "main.lua")
    shutil.copytree(PACK / "src", root / "src")
    return root


def boot(root: pathlib.Path, before: str = "") -> lua54.LuaRuntime:
    """Run main.lua from `root` against the stub engine. `before` is Lua run first."""
    rt = new_lua(root)
    rt.execute(enum_source())
    rt.execute((TESTS / "stub_engine.lua").read_text(encoding="utf-8"))
    if before:
        rt.execute(before)
    rt.execute(f'dofile("{(root / "main.lua").as_posix()}")')
    return rt


def errors(rt: lua54.LuaRuntime) -> list[str]:
    return [line for line in rt.eval("Stub.printed").values() if "ERROR" in line]
