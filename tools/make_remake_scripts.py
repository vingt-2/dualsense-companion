"""Generate the RE2, RE3 (remakes) and Village trigger scripts from the RE7 one.

They share everything (profiles, payload, empty-gun click, fire at the break, the in-game
controller warning, status file) and differ only in how the equipped weapon and its ammo are
read. Edit mods/re7/.../dualsense_companion_re7.lua or the pieces below, then run:

    python tools/make_remake_scripts.py
"""
import re
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "mods", "re7", "reframework", "autorun", "dualsense_companion_re7.lua")

# RE2 and RE3: the current player from PlayerManager; its health in a HitPointController.
REMAKE_HEALTH = '''local HEALTH_COMPONENTS = { NS .. ".HitPointController" }
local function player_object()
    local pm = sdk.get_managed_singleton(NS .. ".PlayerManager")
    return pm and try_call(pm, "get_CurrentPlayer")
end'''

# Village: the player from PropsManager (as the Visceral RE8 VR project found); its health
# in the app.DamageController its app.PlayerUpdaterFPS holds (get_damageController; read in game).
RE8_HEALTH = '''local HEALTH_COMPONENTS = { "app.PlayerUpdaterFPS" }
local function player_object()
    local props = sdk.get_managed_singleton("app.PropsManager")
    return props and try_field(props, "<Player>k__BackingField")
end'''


# RE4's trigger feel (tuned side by side with the PS5 version), for RE2 and RE3: pistols and
# magnums aim with no resistance, the rest lightly; light walls; SMGs rattle.
RE4_L2 = {"handgun": "{0}", "shotgun": "{13, 0, 1}", "rifle": "{13, 0, 1}", "magnum": "{0}",
          "smg": "{13, 7, 1}", "launcher": "{13, 0, 6}"}
RE4_R2 = {"handgun": "{22, 3, 6, 1}", "shotgun": "{22, 3, 7, 5}", "rifle": "{22, 2, 5, 5}",
          "magnum": "{22, 3, 7, 5}", "smg": "{23, 3, 5, 15}", "launcher": "{22, 5, 8, 8}"}
FEEL_RE4 = '''-- The feel of the Resident Evil 4 remake on PS5 (tuned side by side with it): pistols and
-- magnums aim with no resistance, the rest lightly, launchers heavily; light walls, the
-- launcher's the strongest; SMGs rattle.
'''
FEEL_RE8 = '''-- Tuned side by side with the PS5 version: big guns take a lot of force to aim, pistols and
-- the V61 Custom very little (and only deep in the pull); a pistol's wall is light.
'''
RE4_FIRE = {"handgun": 190, "shotgun": 205, "rifle": 165, "magnum": 205, "smg": 0,
            "launcher": 230}


GAMES = {
    "re2": {"name": "Resident Evil 2", "dir": "re2", "ns": "app.ropeway",
            "health": REMAKE_HEALTH,
            # RE2 and RE3 feel like the RE4 remake, tuned against its PS5 version
            "l2": RE4_L2, "r2": RE4_R2, "fire": RE4_FIRE, "feel": FEEL_RE4,
            # RE2's weapon types (EquipmentDefine.WeaponType values), from Advanced Weapon
            # Framework's RE2 weapon data
            "numbers": {
                "handgun": [1, 2, 3, 4, 7, 8, 9, 82, 83, 84, 85],
                "shotgun": [11], "smg": [21, 23, 50, 252], "magnum": [31],
                "launcher": [42, 44, 45, 49, 222], "burner": [43], "knife": [46, 47],
            },
            "ids": {
                "handgun": ["wp0000", "wp0100", "wp0200", "wp0300", "wp0600", "wp0700", "wp0800",
                            "wp7000", "wp7010", "wp7020", "wp7030"],
                "shotgun": ["wp1000"], "smg": ["wp2000", "wp2200", "wp4700", "wp8700"],
                "magnum": ["wp3000"], "launcher": ["wp4100", "wp4300", "wp4400", "wp4600", "wp8400"],
                "burner": ["wp4200"], "knife": ["wp4500", "wp4510"],
            }},
    "re3": {"name": "Resident Evil 3", "dir": "re3", "ns": "offline",
            "health": REMAKE_HEALTH,
            "l2": RE4_L2, "r2": RE4_R2, "fire": RE4_FIRE, "feel": FEEL_RE4,
            "numbers": {},
            # RE3's weapons, from Advanced Weapon Framework's RE3 weapon data
            "ids": {
                "handgun": ["wp0000", "wp0100", "wp0200", "wp0300", "wp0600"],
                "shotgun": ["wp1000"], "rifle": ["wp2000", "wp2100"],
                "magnum": ["wp3000", "wp3100"], "launcher": ["wp4100", "wp4400"],
            }},
    # Village: no equipment manager to ask; the script catches the weapon objects the game
    # updates every frame and takes the one the player holds (see RE8_GAME below)
    "re8": {"name": "Resident Evil Village", "dir": "re8", "ns": "app", "hooks": True,
            "health": RE8_HEALTH,
            # tuned against the PS5 version: big guns take a lot of force to aim, pistols
            # almost none, and a pistol's trigger wall is light
            "l2": {"handgun": "{13, 6, 1}", "smg": "{13, 6, 1}", "shotgun": "{13, 0, 4}",
                   "rifle": "{13, 0, 7}", "magnum": "{13, 0, 5}", "launcher": "{13, 0, 8}",
                   "knife": "{0}", "throw": "{13, 0, 1}", "other": "{13, 0, 1}"},
            "r2": {"handgun": "{22, 3, 6, 2}", "smg": "{22, 3, 6, 3}"},
            "fire": {"smg": 190}, "feel": FEEL_RE8,
            "numbers": {},
            # Village's weapons, from Advanced Weapon Framework's RE8 weapon data
            "ids": {
                "handgun": ["ri3040", "ri3046", "ri3081", "ri3082", "ri3115",
                            "ri3122", "ri3124", "ri3130", "ri3135"],
                # the V61 Custom, a full-auto machine pistol: Village's SMG
                "smg": ["ri3047", "ri3083"],
                "shotgun": ["ri3021", "ri3036", "ri3048", "ri3084", "ri3085", "ri3086", "ri3147"],
                "magnum": ["ri3008", "ri3050", "ri3116"],
                "rifle": ["ri3049", "ri3125", "ri3129", "ri3042", "ri3087"],
                "launcher": ["ri3023"],
            }},
}

# Village (probe, 2026-11-02): every weapon is an app.WeaponCore (guns app.WeaponGunCore,
# knives app.WeaponMeleeCore, throwables app.WeaponThrowableCore) updated every frame; the
# one in the player's hands has get_isEquip and get_isPlayerEquip true; get_weaponName is
# its ID (ri3087...); a gun's get_isMagazineEmpty / get_loadNumRatio give its rounds.
RE8_GAME = """-- the weapons the game updates (their lateUpdate), by address, with when. Each kind has its
-- own lateUpdate (a gun's overrides the base one), so each is hooked.
local recent = {}
local function remember(args)
    local this = sdk.to_managed_object(args[2])
    if this then recent[this:get_address()] = { this, os.clock() } end
end
local hooked = 0
for _, type_name in ipairs({ "app.WeaponGunCore", "app.WeaponMeleeCore",
                             "app.WeaponThrowableCore", "app.WeaponCore" }) do
    local td = sdk.find_type_definition(type_name)
    local late_update = td and td:get_method("lateUpdate")
    if late_update and pcall(sdk.hook, late_update, remember, function(retval) return retval end) then
        hooked = hooked + 1
    end
end

-- the weapon in the player's hands, among those updated in the last second
local function equip_manager()
    if hooked == 0 then return nil, "no weapon updates to watch" end
    local now, held = os.clock(), nil
    for key, seen in pairs(recent) do
        if now - seen[2] > 1.0 then
            recent[key] = nil
        elseif try_call(seen[1], "get_isEquip") and try_call(seen[1], "get_isPlayerEquip") then
            held = seen[1]
        end
    end
    if not held then return nil, "no weapon in hand" end
    return held
end

local function class_of(name, type_name)
    if BY_ID[name] then return BY_ID[name] end
    if type_name:find("Melee", 1, true) then return "knife" end
    if type_name:find("Throwable", 1, true) then return "throw" end
    return "other"
end

"""

RE8_POLL = """    local name = tostring(try_call(equip, "get_weaponName") or "?")
    local td = equip:get_type_definition()
    local type_name = td and td:get_full_name() or "?"
    local item = name .. " (" .. type_name .. ")"
    local class = class_of(name, type_name)
    local ammo
    if GUNS[class] then
        local empty = try_call(equip, "get_isMagazineEmpty") == true
        ammo = empty and 0 or (tonumber(try_call(equip, "get_loadNumRatio")) or 1)
    end
"""


def lua_list(values):
    return ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in values)


def build(key, g):
    s = open(SRC, encoding="utf-8").read().replace("\r\n", "\n")

    def rep(old, new):
        nonlocal s
        assert s.count(old) == 1, (key, old[:60], s.count(old))
        s = s.replace(old, new)

    rep("-- DualSense Companion: adaptive triggers for Resident Evil 7 biohazard\n"
        "-- https://github.com/vingt-2/dualsense-companion (mods/re7)",
        f"-- DualSense Companion: adaptive triggers for {g['name']} (generated by\n"
        f"-- tools/make_remake_scripts.py from the RE7 script: edit that, then regenerate)\n"
        f"-- https://github.com/vingt-2/dualsense-companion (mods/{g['dir']})")
    rep("trigger. Works in the main game and the DLC episodes. Needs REFramework and DualSense",
        "trigger. Needs REFramework and DualSense")
    rep("(reframework\\data\\DualSenseCompanion\\re7_triggers.json) and applies it.",
        f"(reframework\\data\\DualSenseCompanion\\{key}_triggers.json) and applies it.")
    for name in ("triggers.json", "status.txt", "config.json"):
        s = s.replace(f"DualSenseCompanion/re7_{name}", f"DualSenseCompanion/{key}_{name}")
    rep('''    magnum   = { l2 = {13, 0, 5},     r2 = {22, 4, 8, 8},  fire = 225, rgb = {170, 0, 255} },''',
        '''    rifle    = { l2 = {13, 0, 4},     r2 = {22, 2, 5, 7},  fire = 165, rgb = {255, 220, 0} },
    magnum   = { l2 = {13, 0, 5},     r2 = {22, 4, 8, 8},  fire = 225, rgb = {170, 0, 255} },''')

    # the player's object and the component with its health
    rep('''local HEALTH_COMPONENTS = { "app.DamageController" }
local function player_object()
    local objects = sdk.get_managed_singleton("app.ObjectManager")
    return objects and try_field(objects, "PlayerObj")
end''', g["health"])

    rep('''-- The feel of Resident Evil Village on PS5 (tuned side by side with it): pistols and SMGs aim
-- with only a little resistance deep in the pull and have a light wall; heavy guns take more
-- force to aim, the grenade launcher the most.
''', g["feel"])

    # per-game trigger feel (Village aims heavier than the others on PS5)
    for cls, l2 in g.get("l2", {}).items():
        s, n = re.subn(r"(\n    %s +=? *\{ l2 = )\{[^}]*\}(,)" % cls,
                       lambda m: m.group(1) + l2 + m.group(2), s)
        assert n == 1, (key, cls)
    for cls, fire in g.get("fire", {}).items():
        s, n = re.subn(r"(\n    %s +=? *\{ l2 = \{[^}]*\}, +r2 = \{[^}]*\}, +fire = )\d+" % cls,
                       lambda m: m.group(1) + str(fire), s)
        assert n == 1, (key, cls)
    for cls, r2 in g.get("r2", {}).items():
        s, n = re.subn(r"(\n    %s +=? *\{ l2 = \{[^}]*\}, +r2 = )\{[^}]*\}(,)" % cls,
                       lambda m: m.group(1) + r2 + m.group(2), s)
        assert n == 1, (key, cls)

    # weapon classes: by number, by wp ID, then by name
    start = s.index("-- Weapon classes from the equipped item's ID")
    end = s.index("local GUNS = {")
    numbers = "\n".join(f"    {cls} = {{ {lua_list(v)} }}," for cls, v in g["numbers"].items())
    ids = "\n".join(f"    {cls} = {{ {lua_list(v)} }}," for cls, v in g["ids"].items())
    s = s[:start] + f'''-- Weapon classes: by the weapon type's number, by its wp ID (e.g. wp0000) when the type's
-- name holds one, then by keywords in the name. From Advanced Weapon Framework's weapon data.
local BY_NUMBER, BY_ID = {{}}, {{}}
for class, list in pairs({{
{numbers}
}}) do for _, n in ipairs(list) do BY_NUMBER[n] = class end end
for class, list in pairs({{
{ids}
}}) do for _, id in ipairs(list) do BY_ID[id] = class end end
local CLASS_RULES = {{
    {{ "grenadelauncher", "launcher" }}, {{ "launcher", "launcher" }}, {{ "rocket", "launcher" }},
    {{ "handgun", "handgun" }}, {{ "shotgun", "shotgun" }}, {{ "magnum", "magnum" }},
    {{ "rifle", "rifle" }}, {{ "submachine", "smg" }}, {{ "machinegun", "smg" }},
    {{ "minigun", "smg" }}, {{ "flame", "burner" }}, {{ "knife", "knife" }},
    {{ "grenade", "throw" }}, {{ "bomb", "throw" }},
}}
''' + s[end:]
    rep('''local GUNS = { handgun = true, shotgun = true, magnum = true, smg = true, burner = true,
               launcher = true }''',
        '''local GUNS = { handgun = true, shotgun = true, rifle = true, magnum = true, smg = true,
               burner = true, launcher = true }''')

    # the game: EquipmentManager -> current weapon type and the equipped gun's rounds
    start = s.index("-- The player's equipment manager: InteractManager")
    end = s.index("-- Whether the game sees a gamepad")
    if g.get("hooks"):
        s = s[:start] + RE8_GAME + s[end:]
    else:
        s = s[:start] + f'''local NS = "{g['ns']}"

local function equip_manager()
    local em = sdk.get_managed_singleton(NS .. ".EquipmentManager")
    if not em then return nil, "no EquipmentManager" end
    return em
end

-- the weapon type's name, from the enum get_CurrentWeaponType returns (read once)
local weapon_names
local function weapon_name(em, value)
    if weapon_names == nil then
        weapon_names = {{}}
        local td = em:get_type_definition()
        local m = td and td:get_method("get_CurrentWeaponType")
        local enum = m and m:get_return_type()
        for _, f in ipairs(enum and enum:get_fields() or {{}}) do
            if f:is_static() then
                local ok, v = pcall(f.get_data, f, nil)
                if ok and tonumber(v) then weapon_names[tonumber(v)] = f:get_name() end
            end
        end
    end
    return weapon_names[value]
end

local function class_of(value, name)
    if BY_NUMBER[value] then return BY_NUMBER[value] end
    local lower = (name or ""):lower()
    local id = lower:match("wp%d%d%d%d")
    if id and BY_ID[id] then return BY_ID[id] end
    for _, rule in ipairs(CLASS_RULES) do
        if lower:find(rule[1], 1, true) then return rule[2] end
    end
    return "other"
end

''' + s[end:]
    rep('''    local pads = sdk.get_managed_singleton("app.PadManager")
    if pads and try_call(pads, "get_lastInputDevice") then return true end
''', "")
    start = s.index("    local item = try_call(equip, \"get_equipWeaponItemIDRight\")")
    end = s.index("    state.weapon, state.class, state.ammo = item, class, ammo")
    if g.get("hooks"):
        s = s[:start] + RE8_POLL + s[end:]
    else:
        s = s[:start] + '''    local value = tonumber(try_call(equip, "get_CurrentWeaponType"))
    if not value or value <= 0 then                       -- nothing in hand (or no player)
        state.weapon, state.class, state.ammo = nil, "none", nil
        write(payload(nil))
        return
    end
    local name = weapon_name(equip, value)
    local item = (name or "?") .. " (" .. value .. ")"
    local class = class_of(value, name)
    local ammo
    if GUNS[class] then
        local equipment = try_call(equip, "getPlayerEquipment")
        local gun = equipment and try_field(equipment, "<EquipWeapon>k__BackingField")
        ammo = gun and tonumber(try_call(gun, "getBulletNumber")) or nil
    end
''' + s[end:]
    s = s.replace('"Resident Evil 7 doesn\'t see your controller."',
                  f'"{g["name"]} doesn\'t see your controller."')
    assert "re7" not in s.replace("RE7 script", ""), [l for l in s.splitlines() if "re7" in l]
    out = os.path.join(ROOT, "mods", g["dir"], "reframework", "autorun", f"dualsense_companion_{key}.lua")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(s)
    return out


if __name__ == "__main__":
    for key, g in GAMES.items():
        print("wrote", os.path.relpath(build(key, g), ROOT))
