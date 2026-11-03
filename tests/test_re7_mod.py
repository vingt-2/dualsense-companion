"""Runs the RE7 script (mods/re7) against a stand-in for REFramework and checks what it writes,
then feeds that to the app's parser. Needs lupa (pip install lupa):
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
                      "reframework", "autorun", "dualsense_companion_re7.lua")

# Only what the script uses, shaped as the probe found it in the game (2026-11-01):
# app.InteractManager._PlayerStatus.EquipManager, get_equipWeaponItemIDRight (a string),
# get_equipWeaponRight():get_loadNum().
FAKE_REFRAMEWORK = r"""
world = { item = "Handgun_G17", ammo = 10, player = true, pads = 1, last_pad = nil, t = 0,
          hp = 1000, max_hp = 1000 }
local hooks = {}
re = { on_frame = function(f) hooks.frame = f end,
       on_script_reset = function(f) hooks.reset = f end,
       on_draw_ui = function(f) hooks.ui = f end }
os.clock = function() return world.t end
log = { info = function() end }
json = { load_file = function() return saved_config end, dump_file = function() end }
-- REFramework's imgui, recording the in-game warning
world.screen_h, world.font_sizes, world.windows = 2160, {}, 0
imgui = { tree_node = function() return false end,
          get_display_size = function() return { x = 3840, y = world.screen_h } end,
          load_font = function(path, size) table.insert(world.font_sizes, size); return "font" end,
          push_font = function() end, pop_font = function() end,
          begin_window = function() world.windows = world.windows + 1; return true end,
          end_window = function() end, text = function() end,
          button = function() return false end }
local weapon = { call = function(self, m) if m == "get_loadNum" then return world.ammo end end }
local equip = { call = function(self, m)
    if m == "get_equipWeaponItemIDRight" then return world.item end
    if m == "get_equipWeaponRight" then return weapon end
  end }
local status = { get_field = function(self, f) if f == "EquipManager" then return equip end end }
local interact = { get_field = function(self, f)
    if f == "_PlayerStatus" then return world.player and status or nil end end }
-- the player object (app.ObjectManager.PlayerObj) and its app.DamageController
local damage = { call = function(self, m)
    if m == "get_health" then return world.hp end
    if m == "get_maxHealth" then return world.max_hp end
  end }
local player_obj = { call = function(self, m, t)
    if m == "getComponent(System.Type)" and t == "app.DamageController" then return damage end
  end }
local objects = { get_field = function(self, f)
    if f == "PlayerObj" then return world.player and player_obj or nil end end }
-- the engine's gamepad service counts connected pads (Steam Input's XInput pad included);
-- app.PadManager knows the last-used pad
local pads = { call = function(self, m) if m == "get_lastInputDevice" then return world.last_pad end end }
sdk = { get_managed_singleton = function(name)
          if name == "app.InteractManager" then return interact end
          if name == "app.ObjectManager" then return objects end
          if name == "app.PadManager" then return pads end end,
        get_native_singleton = function(name) if name == "via.hid.GamePad" then return "gamepad" end end,
        find_type_definition = function(name) return name end,
        typeof = function(name) return name end,
        call_native_func = function(obj, td, method)
            assert(obj == "gamepad" and method == "getConnectingDevicesCount")
            return world.pads end }
function step() world.t = world.t + 1; hooks.frame() end
function script_reset() hooks.reset() end
"""


def start(config=None):
    """A fresh game with the script loaded; config is what re7_config.json holds."""
    work = tempfile.mkdtemp()
    os.makedirs(os.path.join(work, "DualSenseCompanion"))
    os.chdir(work)                        # REFramework resolves io paths in reframework/data
    L = lupa.LuaRuntime()
    L.execute(FAKE_REFRAMEWORK)
    if config is not None:
        L.globals().saved_config = L.table_from(config)
    L.execute(open(SCRIPT, encoding="utf-8").read())
    return L, work


def health_lightbar():
    """By default the lightbar shows health, as on PS5: green, yellow, orange, red."""
    L, work = start()
    world = L.globals().world
    out = os.path.join(work, "DualSenseCompanion", "re7_triggers.json")

    def rgb(hp):
        world.hp = hp
        L.globals().step()
        o = dsx.Overrides()
        o.apply(dsx.parse(open(out, encoding="ascii").read()), "re7")
        return o.rgb

    assert rgb(1000) == (0, 255, 40)          # fine
    assert rgb(600) == (255, 200, 0)          # caution
    assert rgb(300) == (255, 90, 0)           # caution, lower
    assert rgb(100) == (255, 0, 0)            # danger


def main():
    health_lightbar()
    # the rest checks the weapon colours too: the lightbar per weapon, as set in the menu
    L, work = start({"lightbar_health": False})
    world = L.globals().world
    out = os.path.join(work, "DualSenseCompanion", "re7_triggers.json")

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

    # handguns of every campaign: a light Weapon wall 3-6 (force 2), fire point 190, as in Village
    for item in ("Handgun_G17", "Handgun_M19", "Handgun_MPM", "Handgun_Albert_C"):
        o = effects(item, 9)
        assert written()[0] == (7, [0]), "every payload starts clean"
        assert o.r2 == dsx.encode_trigger(22, [3, 6, 2]) and o.thresholds[dsx.R2] == 190, item
        assert o.l2 == dsx.encode_trigger(13, [6, 1]), item
    # empty magazine: light early click, no fire point
    o = effects(ammo=0)
    assert o.r2 == dsx.encode_trigger(22, [2, 4, 3]) and o.thresholds[dsx.R2] == 0
    # classes from the item IDs
    assert effects("Shotgun_M37", 4).thresholds[dsx.R2] == 205
    assert effects("Shotgun_Albert", 4).thresholds[dsx.R2] == 205
    assert effects("Magnum", 6).r2 == dsx.encode_trigger(22, [4, 8, 8])
    o = effects("MachineGun", 30)                  # a Weapon wall like Village's SMGs
    assert o.r2 == dsx.encode_trigger(22, [3, 6, 3]) and o.thresholds[dsx.R2] == 190
    assert effects("Magnum", 6).l2 == dsx.encode_trigger(13, [0, 5])
    assert effects("GrenadeLauncher", 1).l2 == dsx.encode_trigger(13, [0, 8])
    assert effects("GrenadeLauncher", 1).thresholds[dsx.R2] == 230      # not a throwable
    o = effects("Grenadebomb")
    assert o.r2 == dsx.encode_trigger(13, [0, 3]) and o.rgb == (0, 255, 60)
    o = effects("CKnife")
    assert o.r2 == dsx.OFF and o.thresholds[dsx.R2] == 0 and o.rgb == (255, 255, 255)
    assert effects("ChainSaw").r2 == dsx.encode_trigger(23, [1, 6, 40])
    o = effects("SomethingNew")                                       # unknown: light L2 only
    assert o.l2 == dsx.encode_trigger(13, [0, 1]) and o.r2 == dsx.OFF and o.rgb is None
    # every class's effects are ones the app accepts
    for item in ("Handgun_G17", "Shotgun_M37", "Magnum", "MachineGun", "Burner",
                 "GrenadeLauncher", "MiaKnife", "CircularSaw", "LiquidBomb"):
        for ammo in (5, 0):
            o = effects(item, ammo)
            assert o.l2 is not None and o.r2 is not None, (item, ammo, written())
    # whether the game sees a controller goes to the app with the payload
    def seen():
        with open(out, "rb") as f:
            return dsx.controller_seen(f.read())
    world.pads = 1
    effects("Handgun_G17", 10)
    assert seen() is True
    world.pads = 0                                    # Steam Input off: no pad at all
    effects()
    assert seen() is False
    # after 2 s without a controller the game shows a warning, 32 px text on a 4K screen
    windows = world.windows
    for _ in range(1):
        L.globals().step()
    assert world.windows == windows, "warned too early"
    for _ in range(3):
        L.globals().step()
    assert world.windows > windows, "no in-game warning"
    assert list(world.font_sizes.values())[-1] == 32, list(world.font_sizes.values())
    world.pads = 1                                    # a controller shows up: warning gone
    L.globals().step()
    shown = world.windows
    L.globals().step()
    L.globals().step()
    assert world.windows == shown, "warning still shown with a controller"
    world.pads = 1
    # a pad that's been used counts even if the engine's count says none (and vice versa)
    world.pads, world.last_pad = 0, "pad"
    effects()
    assert seen() is True
    world.last_pad = None
    world.pads = 1
    # no player (menus): reset only; script reset: reset
    effects(player=False)
    assert written() == [(7, [0])]
    effects("Handgun_G17", 10)
    L.globals().script_reset()
    assert written() == [(7, [0])]
    print("OK: RE7 script writes the expected trigger payloads for each weapon class")


if __name__ == "__main__":
    main()
