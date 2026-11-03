"""Runs the RE4 Remake script (mods/re4-remake) against a stand-in for REFramework and checks
what it writes, then feeds that to the app's parser. Needs lupa (pip install lupa):
python tests\\test_re4_mod.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
try:
    import lupa
except ImportError:
    print("SKIP: pip install lupa to test the RE4 script")
    sys.exit(0)
import dsx

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mods", "re4-remake",
                      "reframework", "autorun", "dualsense_companion_re4.lua")

# A minimal REFramework: one player whose weapon and loaded ammo the test sets.
FAKE_REFRAMEWORK = r"""
world = { weapon = 4000, ammo = 10, player = true, t = 0, hp = 1200, max_hp = 1200 }
local hooks = {}
re = { on_frame = function(f) hooks.frame = f end,
       on_script_reset = function(f) hooks.reset = f end,
       on_draw_ui = function(f) hooks.ui = f end }
os.clock = function() return world.t end
log = { info = function() end }
json = { load_file = function() return saved_config end, dump_file = function() end }
imgui = { tree_node = function() return false end }
-- the player: CharacterManager -> context -> head object -> PlayerEquipment
local equipment = { call = function(self, name) return world.weapon end }
local head = { call = function(self, m, t)
    if m == "getComponent(System.Type)" then return t == "chainsaw.PlayerEquipment" and equipment or nil end
  end }
-- the player's health: the context's HitPoint (current / default hit points)
local hit_point = { call = function(self, m)
    if m == "get_CurrentHitPoint" then return world.hp end
    if m == "get_DefaultHitPoint" then return world.max_hp end
  end }
local context = { call = function(self, m)
    if m == "get_HeadGameObject" then return head end
    if m == "get_HitPoint" then return hit_point end
  end }
local character_manager = { call = function() return world.player and context or nil end }
-- the ammo: InventoryManager._ControllerTable -> CsInventoryController -> equipped weapon
local weapon_item = { call = function(self, m) if m == "get_CurrentAmmoCount" then return world.ammo end end }
local function controller(type_name)
    return { get_type_definition = function() return { get_full_name = function() return type_name end } end,
             call = function(self, m) if m == "getEquippedWeapon" then return weapon_item end end }
end
local controllers = { controller("chainsaw.KeyItemInventoryController"),
                      controller("chainsaw.CsInventoryController") }
local function enumerator(list)
    local i = 0
    return { call = function(self, m)
        if m == "MoveNext" then i = i + 1; return i <= #list end
        if m == "get_Current" then return list[i] end
    end }
end
local controller_table = { call = function(self, m)
    if m == "get_Values" then return { call = function() return enumerator(controllers) end } end
  end }
local inventory_manager = { get_field = function(self, f) if f == "_ControllerTable" then return controller_table end end }
local scene = { call = function() return nil end }
sdk = { get_managed_singleton = function(name)
            return ({ ["chainsaw.CharacterManager"] = character_manager,
                      ["chainsaw.InventoryManager"] = inventory_manager })[name] end,
        get_native_singleton = function(name) return name == "via.SceneManager" and {} or nil end,
        find_type_definition = function(name) return name end,
        call_native_func = function(obj, td, method)
            assert(td == "via.SceneManager" and method == "get_CurrentScene") return scene end,
        typeof = function(t) return t end }
function step() world.t = world.t + 1; hooks.frame() end
function script_reset() hooks.reset() end
"""


def start(config=None):
    """A fresh game with the script loaded; config is what re4_config.json holds."""
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
    out = os.path.join(work, "DualSenseCompanion", "re4_triggers.json")

    def rgb(hp):
        world.hp = hp
        L.globals().step()
        o = dsx.Overrides()
        o.apply(dsx.parse(open(out, encoding="ascii").read()), "re4")
        return o.rgb

    assert rgb(1200) == (0, 255, 40)          # fine
    assert rgb(700) == (255, 200, 0)          # caution
    assert rgb(400) == (255, 90, 0)           # caution, lower
    assert rgb(100) == (255, 0, 0)            # danger
    assert rgb(0) == (255, 0, 0)


def main():
    health_lightbar()
    # the rest checks the weapon colours too: the lightbar per weapon, as set in the menu
    L, work = start({"lightbar_health": False})
    world = L.globals().world
    out = os.path.join(work, "DualSenseCompanion", "re4_triggers.json")

    def written():
        with open(out, encoding="ascii") as f:
            text = f.read()
        json.loads(text)
        return dsx.parse(text)

    def effects(weapon=None, ammo=None, player=True):
        if weapon is not None:
            world.weapon = weapon
        if ammo is not None:
            world.ammo = ammo
        world.player = player
        L.globals().step()
        o = dsx.Overrides()
        o.apply(written(), "re4")
        return o

    # pistol: Weapon wall 3-6 at force 8, fire point 190, blue
    o = effects(4000, 10)
    assert written()[0] == (7, [0]), "every payload starts clean"
    assert o.r2 == dsx.encode_trigger(22, [3, 6, 1]) and o.thresholds[dsx.R2] == 190, o.thresholds
    assert o.l2 == dsx.OFF and o.rgb == (0, 120, 255)
    # empty magazine: light early click, no fire point
    o = effects(ammo=0)
    assert o.r2 == dsx.encode_trigger(22, [2, 4, 3]) and o.thresholds[dsx.R2] == 0
    # shotgun, bolt thrower, magnum by their ID family
    assert effects(4100, 5).thresholds[dsx.R2] == 205
    o = effects(4600, 1)
    assert o.r2 == dsx.encode_trigger(22, [5, 8, 6]) and o.thresholds[dsx.R2] == 230
    assert effects(4502, 3).r2 == dsx.encode_trigger(22, [3, 7, 5])
    # extras outside their family: Skull Shaker is a shotgun, Sentinel Nine a pistol
    assert effects(6001, 2).thresholds[dsx.R2] == 205
    assert effects(6000, 9).thresholds[dsx.R2] == 190
    assert effects(6103, 9).thresholds[dsx.R2] == 190       # Ada's Blacktail AC
    assert effects(6104, 9).thresholds[dsx.R2] == 0         # Ada's TMP: an SMG, no wall
    o = effects(5400)                                        # hand grenade
    assert o.r2 == dsx.encode_trigger(13, [0, 3]) and o.rgb == (0, 255, 60)
    # knife: no wall, no threshold left over from the gun
    o = effects(5000)
    assert o.r2 == dsx.OFF and o.thresholds[dsx.R2] == 0 and o.rgb == (255, 255, 255)
    # unknown weapon: light L2, nothing else
    o = effects(5814)
    assert o.l2 == dsx.encode_trigger(13, [0, 1]) and o.r2 == dsx.OFF and o.rgb is None
    # every class's effects must be ones the app accepts (an invalid one would be dropped)
    for weapon in (4000, 6000, 4100, 4200, 4400, 4500, 4600, 4900, 5000, 5400, 6103, 6107):
        for ammo in (5, 0):
            o = effects(weapon, ammo)
            assert o.l2 is not None and o.r2 is not None, (weapon, ammo, written())
    # no player (menus): reset only
    effects(player=False)
    assert written() == [(7, [0])]
    # script reset in REFramework: reset
    effects(4000, 10)
    L.globals().script_reset()
    assert written() == [(7, [0])]
    print("OK: RE4 script writes the expected trigger payloads for each weapon class, "
          "and the lightbar shows health")


if __name__ == "__main__":
    main()
