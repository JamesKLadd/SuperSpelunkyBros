#!/usr/bin/env python3
"""Rebuild tests/api_manifest.json from an Overlunky checkout.

    git clone --depth 1 https://github.com/spelunky-fyi/overlunky
    python tools/update_api_manifest.py path/to/overlunky

The manifest is the list of names the Spelunky 2 Lua API really has: global
functions, enum members with their values, and field / method names. It is read
from the two files Overlunky generates from its own source:

    docs/game_data/spel2.lua       type definitions for editors
    docs/game_data/lua_enums.txt   every enum, with values

tests/test_api_usage.py checks every engine name our Lua uses against it, so a
misspelt or invented function fails a test instead of failing in the game. The
stub engine in tests/ also takes its enum values from here.

Re-run this when moving to a newer Playlunky / Overlunky, and commit the result.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

PACK = pathlib.Path(__file__).resolve().parent.parent
OUT = PACK / "tests" / "api_manifest.json"


def parse_enums(text: str) -> dict[str, dict[str, int]]:
    enums: dict[str, dict[str, int]] = {}
    current = None
    for line in text.splitlines():
        start = re.match(r"^(\w+) = \{$", line)
        if start:
            current = enums.setdefault(start.group(1), {})
            continue
        if line.startswith("}"):
            current = None
            continue
        member = re.match(r"^\s+(\w+) = (-?\d+),?$", line)
        if member and current is not None:
            current[member.group(1)] = int(member.group(2))
    return enums


def parse_definitions(text: str) -> tuple[list[str], list[str]]:
    functions = sorted(set(re.findall(r"^function (\w+)\(", text, flags=re.M)))
    fields = set(re.findall(r"^\s*---@field (\w+)\b", text, flags=re.M))
    # overloads and static methods are written as functions on the class
    fields.update(re.findall(r"^function \w+[.:](\w+)\(", text, flags=re.M))
    return functions, sorted(fields)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    root = pathlib.Path(sys.argv[1])
    data = root / "docs" / "game_data"
    functions, fields = parse_definitions((data / "spel2.lua").read_text(encoding="utf-8"))
    enums = parse_enums((data / "lua_enums.txt").read_text(encoding="utf-8"))
    commit = "unknown"
    try:
        commit = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%H %cs"],
                                capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    manifest = {
        "source": "https://github.com/spelunky-fyi/overlunky docs/game_data",
        "commit": commit,
        "functions": functions,
        "fields": fields,
        "enums": enums,
    }
    OUT.write_text(json.dumps(manifest, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}: {len(functions)} functions, {len(fields)} fields, {len(enums)} enums ({commit})")


if __name__ == "__main__":
    main()
