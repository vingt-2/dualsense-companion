"""Runs the RE7 script (mods/re7) against a stand-in for REFramework and checks what it writes,
then feeds that to the bridge's parser. Needs lupa (pip install lupa):
python tests\\test_re7_mod.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
try:
    import lupa
except ImportError:
    print("SKIP: pip install lupa to test the RE7 script")
    sys.exit(0)
import dsx

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mods", "re7",
                      "reframework", "autorun", "dualsense_bridge_re7.lua")

# Only what the script uses, shaped as the probe found it in the game (2026-11-01):
# app.InteractManager._PlayerStatus.EquipManager, get_equipWeaponItemIDRight (a string),
# get_equipWeaponRight():get_loadNum().
FAKE_REFRAMEWORK = r"""
world = { item = "Handgun_G17", ammo = 10, player = true, t = 0 }
local hooks = {}
re = { on_frame = function(f) hooks.frame = f end,
       on_script_reset = function(f) hooks.reset = f end,
       on_draw_ui = function(f) hooks.ui = f end }
os.clock = function() return world.t end
log = { info = function() end }
json = { load_file = function() return nil end, dump_file = function() end }
imgui = { tree_node = function() return false end }
local weapon = { call = function(self, m) if m == "get_loadNum" then return world.ammo end end }
local equip = { call = function(self, m)
    if m == "get_equipWeaponItemIDRight" then return world.item end
    if m == "get_equipWeaponRight" then return weapon end
  end }
local status = { get_field = function(self, f) if f == "EquipManager" then return equip end end }
local interact = { get_field = function(self, f)
    if f == "_PlayerStatus" then return world.player and status or nil end end }
sdk = { get_managed_singleton = function(name)
          if name == "app.InteractManager" then return interact end end }
function step() world.t = world.t + 1; hooks.frame() end
function script_reset() hooks.reset() end
"""


def main():
    work = tempfile.mkdtemp()
    os.makedirs(os.path.join(work, "DualSenseBridge"))
    os.chdir(work)                        # REFramework resolves io paths in reframework/data
    L = lupa.LuaRuntime()
    L.execute(FAKE_REFRAMEWORK)
    L.execute(open(SCRIPT, encoding="utf-8").read())
    world = L.globals().world
    out = os.path.join(work, "DualSenseBridge", "re7_triggers.json")

    def written():
        with open(out, encoding="ascii") as f:
            text = f.read()
        json.loads(text)
        return dsx.parse(text)

    def effects(item=None, ammo=None, player=True):
        if item is not None:
            world.item = item
        if ammo is not None:
            world.ammo = ammo
        world.player = player
        L.globals().step()
        o = dsx.Overrides()
        o.apply(written(), "re7")
        return o

    # handguns of every campaign: Weapon wall 3-6 at force 8, fire point 190
    for item in ("Handgun_G17", "Handgun_M19", "Handgun_MPM", "Handgun_Albert_C"):
        o = effects(item, 9)
        assert written()[0] == (7, [0]), "every payload starts clean"
        assert o.r2 == dsx.encode_trigger(22, [3, 6, 8]) and o.thresholds[dsx.R2] == 190, item
    # empty magazine: light early click, no fire point
    o = effects(ammo=0)
    assert o.r2 == dsx.encode_trigger(22, [2, 4, 3]) and o.thresholds[dsx.R2] == 0
    # classes from the item IDs
    assert effects("Shotgun_M37", 4).thresholds[dsx.R2] == 205
    assert effects("Shotgun_Albert", 4).thresholds[dsx.R2] == 205
    assert effects("Magnum", 6).r2 == dsx.encode_trigger(22, [4, 8, 8])
    assert effects("MachineGun", 30).r2 == dsx.encode_trigger(23, [3, 5, 15])
    assert effects("GrenadeLauncher", 1).thresholds[dsx.R2] == 230      # not a throwable
    o = effects("Grenadebomb")
    assert o.r2 == dsx.encode_trigger(13, [0, 3]) and o.rgb == (0, 255, 60)
    o = effects("CKnife")
    assert o.r2 == dsx.OFF and o.thresholds[dsx.R2] == 0 and o.rgb == (255, 255, 255)
    assert effects("ChainSaw").r2 == dsx.encode_trigger(23, [1, 6, 40])
    o = effects("SomethingNew")                                       # unknown: light L2 only
    assert o.l2 == dsx.encode_trigger(13, [0, 2]) and o.r2 == dsx.OFF and o.rgb is None
    # every class's effects are ones the bridge accepts
    for item in ("Handgun_G17", "Shotgun_M37", "Magnum", "MachineGun", "Burner",
                 "GrenadeLauncher", "MiaKnife", "CircularSaw", "LiquidBomb"):
        for ammo in (5, 0):
            o = effects(item, ammo)
            assert o.l2 is not None and o.r2 is not None, (item, ammo, written())
    # no player (menus): reset only; script reset: reset
    effects(player=False)
    assert written() == [(7, [0])]
    effects("Handgun_G17", 10)
    L.globals().script_reset()
    assert written() == [(7, [0])]
    print("OK: RE7 script writes the expected trigger payloads for each weapon class")


if __name__ == "__main__":
    main()
