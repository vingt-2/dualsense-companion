"""Runs the RE2, RE3 and Village scripts (mods/re2, re3, re8; generated from the RE7 one)
against a stand-in for REFramework and checks what they write. Needs lupa:
python tests\\test_remake_mods.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
try:
    import lupa
except ImportError:
    print("SKIP: pip install lupa to test the RE2/RE3 scripts")
    sys.exit(0)
import dsx

HERE = os.path.dirname(os.path.abspath(__file__))

# The calls the scripts use: <ns>.EquipmentManager:get_CurrentWeaponType() (an enum, whose
# names come from the method's return type), getPlayerEquipment() -> <EquipWeapon> ->
# getBulletNumber(); the engine's gamepad count.
FAKE = r"""
world = { type = 0, ammo = 10, pads = 1, t = 0, names = {}, hp = 1200, max_hp = 1200 }
local hooks = {}
re = { on_frame = function(f) hooks.frame = f end,
       on_script_reset = function(f) hooks.reset = f end,
       on_draw_ui = function(f) hooks.ui = f end }
os.clock = function() return world.t end
log = { info = function() end }
json = { load_file = function() return nil end, dump_file = function() end }
imgui = { tree_node = function() return false end, get_display_size = function() return { y = 2160 } end,
          load_font = function() return "font" end, push_font = function() end, pop_font = function() end,
          begin_window = function() world.warned = true; return true end, end_window = function() end,
          text = function() end, button = function() return false end }
local enum = { get_fields = function()
    local fields = {}
    for value, name in pairs(world.names) do
        fields[#fields + 1] = { is_static = function() return true end,
                                get_data = function() return value end,
                                get_name = function() return name end }
    end
    return fields
end }
local method = { get_return_type = function() return enum end }
local td = { get_method = function(self, name) if name == "get_CurrentWeaponType" then return method end end }
local gun = { call = function(self, m) if m == "getBulletNumber" then return world.ammo end end }
local equipment = { get_field = function(self, f) if f == "<EquipWeapon>k__BackingField" then return gun end end }
local em = { get_type_definition = function() return td end,
             call = function(self, m)
                 if m == "get_CurrentWeaponType" then return world.type end
                 if m == "getPlayerEquipment" then return equipment end
             end }
-- the player (PlayerManager.get_CurrentPlayer) and its HitPointController
local hit_points = { call = function(self, m)
    if m == "get_CurrentHitPoint" then return world.hp end
    if m == "get_DefaultHitPoint" then return world.max_hp end
  end }
local player = { call = function(self, m, t)
    if m == "getComponent(System.Type)" and t == NS .. ".HitPointController" then return hit_points end
  end }
-- a new player object (after a load, say), while the old one still answers at full health
function swap_player(hp)
    local points = { call = function(self, m)
        if m == "get_CurrentHitPoint" then return hp end
        if m == "get_DefaultHitPoint" then return world.max_hp end
      end }
    world.player_obj = { call = function(self, m, t)
        if m == "getComponent(System.Type)" and t == NS .. ".HitPointController" then return points end
      end }
end
local pm = { call = function(self, m)
    if m == "get_CurrentPlayer" then return world.player_obj or player end
  end }
sdk = { get_managed_singleton = function(name)
            if name == NS .. ".EquipmentManager" then return em end
            if name == NS .. ".PlayerManager" then return pm end
        end,
        get_native_singleton = function(name) if name == "via.hid.GamePad" then return "gamepad" end end,
        find_type_definition = function(name) return name end,
        typeof = function(name) return name end,
        call_native_func = function() return world.pads end }
function step() world.t = world.t + 1; hooks.frame() end
"""


def run(game, ns, names, cases):
    work = tempfile.mkdtemp()
    os.makedirs(os.path.join(work, "DualSenseCompanion"))
    cwd = os.getcwd()
    os.chdir(work)
    try:
        L = lupa.LuaRuntime()
        L.execute(f'NS = "{ns}"')
        L.execute(FAKE)
        world = L.globals().world
        for value, name in names.items():
            world.names[value] = name
        script = os.path.join(HERE, "..", "mods", game, "reframework", "autorun", f"dualsense_companion_{game}.lua")
        L.execute(open(script, encoding="utf-8").read())
        out = os.path.join(work, "DualSenseCompanion", f"{game}_triggers.json")

        def effects(value, ammo=10):
            world.type, world.ammo = value, ammo
            L.globals().step()
            text = open(out, encoding="ascii").read()
            json.loads(text)
            o = dsx.Overrides()
            o.apply(dsx.parse(text), game)
            return o, text

        for value, expect in cases:
            o, text = effects(value)
            if expect is None:
                # nothing in hand: triggers normal, the lightbar still shows health
                assert dsx.parse(text) == [(7, [0]), (2, [0, 0, 255, 40])], (game, value, text)
            else:
                assert o.r2 == dsx.encode_trigger(*expect[0]), (game, value, o.r2, expect)
                assert o.thresholds[dsx.R2] == expect[1], (game, value, o.thresholds)
        # the lightbar shows health, as on PS5: green, yellow, orange, red
        for hp, colour in ((1.0, (0, 255, 40)), (0.6, (255, 200, 0)), (0.3, (255, 90, 0)),
                           (0.1, (255, 0, 0))):
            world.hp = world.max_hp * hp
            o, _ = effects(cases[0][0])                  # a gun in hand
            assert o.rgb == colour, (game, hp, o.rgb)
        world.hp = world.max_hp
        # a new player object: its health, not the old one's (still at full)
        L.globals().swap_player(world.max_hp * 0.3)
        L.globals().step()
        o = dsx.Overrides()
        o.apply(dsx.parse(open(out, encoding="ascii").read()), game)
        assert o.rgb == (255, 90, 0), (game, "new player", o.rgb)
        world.player_obj = None
        # empty gun: the light early click and no fire point
        o, _ = effects(cases[0][0], ammo=0)
        assert o.r2 == dsx.encode_trigger(22, [2, 4, 3]) and o.thresholds[dsx.R2] == 0, game
        # no controller for 2 s: the in-game warning
        world.pads = 0
        for _ in range(4):
            L.globals().step()
        assert world.warned, f"{game}: no in-game warning"
        assert '"controllerSeen":false' in open(out).read()
    finally:
        os.chdir(cwd)


# Village: weapons are app.WeaponCore objects the game updates every frame; each kind has its
# own lateUpdate (a gun's overrides the base one, so a hook on the base never sees guns: found
# in game). The one in hand has get_isEquip and get_isPlayerEquip true.
FAKE_RE8 = r"""
world = { held = nil, empty = false, pads = 1, t = 0, warned = false, hp = 1000, max_hp = 1000 }
local hooks = {}
re = { on_frame = function(f) hooks.frame = f end,
       on_script_reset = function(f) hooks.reset = f end,
       on_draw_ui = function(f) hooks.ui = f end }
os.clock = function() return world.t end
log = { info = function() end }
json = { load_file = function() return nil end, dump_file = function() end }
imgui = { tree_node = function() return false end, get_display_size = function() return { y = 2160 } end,
          load_font = function() return "font" end, push_font = function() end, pop_font = function() end,
          begin_window = function() world.warned = true; return true end, end_window = function() end,
          text = function() end, button = function() return false end }
local function weapon(address, name, type_name)
    return { get_address = function() return address end,
             get_type_definition = function() return { get_full_name = function() return type_name end } end,
             call = function(self, m)
                 if m == "get_isEquip" or m == "get_isPlayerEquip" then return world.held == address end
                 if m == "get_weaponName" then return name end
                 if m == "get_isMagazineEmpty" then return world.empty end
                 if m == "get_loadNumRatio" then return world.empty and 0.0 or 0.5 end
             end }
end
weapons = { weapon(1, "ri3040", "app.WeaponGunCore"), weapon(2, "ri3021", "app.WeaponGunCore"),
            weapon(3, "ri3087", "app.WeaponGunCore"), weapon(4, "ri3022", "app.WeaponMeleeCore"),
            weapon(5, "ri3075", "app.WeaponThrowableCore"), weapon(6, "ri3023", "app.WeaponGunCore") }
-- one lateUpdate per weapon kind; a hook only sees the objects of its own kind
local late_updates, kind_hooks = {}, {}
for _, kind in ipairs({ "app.WeaponCore", "app.WeaponGunCore", "app.WeaponMeleeCore",
                        "app.WeaponThrowableCore" }) do
    late_updates[kind] = { kind = kind }
end
-- the player (PropsManager.<Player>k__BackingField); its app.PlayerUpdaterFPS holds the
-- app.DamageController
local damage = { call = function(self, m)
    if m == "get_health" then return world.hp end
    if m == "get_maxHealth" then return world.max_hp end
  end }
local updater = { call = function(self, m) if m == "get_damageController" then return damage end end }
local player = { call = function(self, m, t)
    if m == "getComponent(System.Type)" and t == "app.PlayerUpdaterFPS" then return updater end
  end }
props = { get_field = function(self, f) if f == "<Player>k__BackingField" then return player end end }
sdk = { find_type_definition = function(name)
            if late_updates[name] then
                return { get_method = function(self, m) if m == "lateUpdate" then return late_updates[name] end end }
            end
            return name
        end,
        hook = function(method, pre, post) kind_hooks[method.kind] = pre end,
        to_managed_object = function(p) return p end,
        get_managed_singleton = function(name) if name == "app.PropsManager" then return props end end,
        typeof = function(name) return name end,
        get_native_singleton = function(name) if name == "via.hid.GamePad" then return "gamepad" end end,
        call_native_func = function() return world.pads end }
function step()
    world.t = world.t + 1
    for _, w in ipairs(weapons) do                              -- the game updates its weapons
        local kind = w:get_type_definition():get_full_name()
        if kind_hooks[kind] then kind_hooks[kind]({ nil, w }) end
    end
    hooks.frame()
end
"""


def run_re8():
    work = tempfile.mkdtemp()
    os.makedirs(os.path.join(work, "DualSenseCompanion"))
    cwd = os.getcwd()
    os.chdir(work)
    try:
        L = lupa.LuaRuntime()
        L.execute(FAKE_RE8)
        world = L.globals().world
        L.execute(open(os.path.join(HERE, "..", "mods", "re8", "reframework", "autorun",
                                    "dualsense_companion_re8.lua"), encoding="utf-8").read())
        out = os.path.join(work, "DualSenseCompanion", "re8_triggers.json")

        def effects(held, empty=False):
            world.held, world.empty = held, empty
            L.globals().step()
            text = open(out, encoding="ascii").read()
            o = dsx.Overrides()
            o.apply(dsx.parse(text), "re8")
            return o, text

        for held, expect in [(1, ((22, [3, 6, 2]), 190)), (2, SHOTGUN), (3, RIFLE), (6, LAUNCHER),
                             (4, KNIFE), (5, ((13, [0, 3]), 0))]:
            o, text = effects(held)
            assert o.r2 == dsx.encode_trigger(*expect[0]), (held, text)
            assert o.thresholds[dsx.R2] == expect[1], (held, text)
        # the lightbar shows health, as on PS5: green, yellow, orange, red
        for hp, colour in ((1.0, (0, 255, 40)), (0.6, (255, 200, 0)), (0.3, (255, 90, 0)),
                           (0.1, (255, 0, 0))):
            world.hp = world.max_hp * hp
            o, _ = effects(1)
            assert o.rgb == colour, ("re8", hp, o.rgb)
        world.hp = world.max_hp
        o, _ = effects(1, empty=True)                    # empty magazine: the click
        assert o.r2 == dsx.encode_trigger(22, [2, 4, 3]) and o.thresholds[dsx.R2] == 0
        o, text = effects(None)                          # nothing in hand: triggers normal,
        assert dsx.parse(text) == [(7, [0]), (2, [0, 0, 255, 40])], text   # health still on the lightbar
        world.pads = 0
        for _ in range(4):
            L.globals().step()
        assert world.warned, "re8: no in-game warning"
    finally:
        os.chdir(cwd)


SHOTGUN = ((22, [3, 7, 8]), 205)
RIFLE = ((22, [2, 5, 7]), 165)
LAUNCHER = ((22, [5, 8, 8]), 230)
SMG = ((23, [3, 5, 15]), 0)
BURNER = ((23, [2, 4, 30]), 0)
KNIFE = ((0, []), 0)
# RE2 and RE3 take the RE4 remake's feel (tuned against its PS5 version): lighter walls
RE4_FEEL = {"handgun": ((22, [3, 6, 1]), 190), "shotgun": ((22, [3, 7, 5]), 205),
            "rifle": ((22, [2, 5, 5]), 165), "magnum": ((22, [3, 7, 5]), 205)}


def main():
    # RE2: classes by the weapon type's number (names don't matter)
    run("re2", "app.ropeway", {1: "wp0000", 11: "wp1000"},
        [(1, RE4_FEEL["handgun"]), (11, RE4_FEEL["shotgun"]), (21, SMG), (31, RE4_FEEL["magnum"]), (42, LAUNCHER), (43, BURNER),
         (46, KNIFE), (0, None)])
    # RE3: classes by the wp ID in the type's name, then by keywords in it
    run("re3", "offline", {1: "wp0000", 2: "wp1000", 3: "wp2000", 4: "wp3100", 5: "wp4100",
                           6: "HandGrenade", 7: "CombatKnife"},
        [(1, RE4_FEEL["handgun"]), (2, RE4_FEEL["shotgun"]), (3, RE4_FEEL["rifle"]),
         (4, RE4_FEEL["magnum"]), (5, LAUNCHER),
         (6, ((13, [0, 3]), 0)), (7, KNIFE), (0, None)])
    run_re8()
    print("OK: RE2, RE3 and Village scripts write the expected trigger payloads for each weapon class")


if __name__ == "__main__":
    main()
