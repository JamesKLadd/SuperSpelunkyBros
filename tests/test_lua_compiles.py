"""Every Lua file must compile under a real Lua 5.4, not merely look right."""

import pytest

from conftest import ALL_LUA, PACK, new_lua

COMPILE = """
function compileError(src, name)
    local chunk, err = load(src, name)
    if chunk ~= nil then return "" end
    return tostring(err)
end
"""


@pytest.mark.parametrize("path", ALL_LUA, ids=lambda p: p.relative_to(PACK).as_posix())
def test_the_file_compiles(path):
    rt = new_lua(PACK)
    rt.execute(COMPILE)
    err = str(rt.eval("compileError")(path.read_text(encoding="utf-8"), "@" + path.name))
    assert err == "", f"{path.name} does not compile: {err}"
