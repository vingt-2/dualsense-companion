-- DualSense Bridge: adaptive triggers for Resident Evil 7 biohazard
-- https://github.com/vingt-2/dualsense-bridge (mods/re7)
--
-- Gives each weapon class its own trigger feel. Guns get a trigger wall that breaks, and the
-- game only sees R2 once the wall has broken, so the shot fires at the break like a real
-- trigger. Works in the main game and the DLC episodes. Needs REFramework and DualSense
-- Bridge 1.7 or later, which reads the file this script writes
-- (reframework\data\DualSenseBridge\re7_triggers.json) and applies it.
--
-- The file uses DSX's instruction format (DualSenseX's mod protocol):
--   type 1 trigger effect, 2 lightbar, 4 trigger threshold, 7 reset.
-- Trigger effects: 13 Resistance(start zone 0-9, force 1-8),
--   22 Weapon(start zone 2-7, break zone 3-8, force 1-8), 23 Vibration(start, amplitude, Hz).
-- Thresholds are trigger positions 0-255: below it the game reads the trigger as released.
--
-- MIT licence, see the repository.

local OUT_FILE = "DualSenseBridge/re7_triggers.json"   -- relative to reframework/data
local STATUS_FILE = "DualSenseBridge/re7_status.txt"
local CONFIG_FILE = "DualSenseBridge/re7_config.json"
local POLL = 0.1                                       -- s between checks of the weapon

-- Trigger feel per weapon class. l2/r2 = {mode, params...}; fire = R2 threshold.
-- Tune here, or override any class in reframework/data/DualSenseBridge/re7_config.json.
local PROFILES = {
    none     = { l2 = {0},            r2 = {0},            fire = 0,   rgb = nil },
    handgun  = { l2 = {13, 0, 3},     r2 = {22, 3, 6, 8},  fire = 190, rgb = {0, 120, 255} },
    shotgun  = { l2 = {13, 0, 5},     r2 = {22, 3, 7, 8},  fire = 205, rgb = {255, 50, 30} },
    magnum   = { l2 = {13, 0, 6},     r2 = {22, 4, 8, 8},  fire = 225, rgb = {170, 0, 255} },
    smg      = { l2 = {13, 0, 2},     r2 = {23, 3, 5, 15}, fire = 0,   rgb = {255, 130, 0} },
    burner   = { l2 = {13, 0, 2},     r2 = {23, 2, 4, 30}, fire = 0,   rgb = {255, 90, 0} },
    launcher = { l2 = {13, 0, 7},     r2 = {22, 5, 8, 8},  fire = 230, rgb = {255, 0, 80} },
    knife    = { l2 = {13, 0, 1},     r2 = {0},            fire = 0,   rgb = {255, 255, 255} },
    saw      = { l2 = {13, 0, 3},     r2 = {23, 1, 6, 40}, fire = 0,   rgb = {255, 255, 255} },
    throw    = { l2 = {13, 0, 4},     r2 = {13, 0, 3},     fire = 0,   rgb = {0, 255, 60} },
    other    = { l2 = {13, 0, 2},     r2 = {0},            fire = 0,   rgb = nil },
}
-- A gun with an empty magazine: a light, early click, so the dry fire registers at once.
local EMPTY_R2 = {22, 2, 4, 3}

-- Weapon classes from the equipped item's ID (e.g. "Handgun_G17", "Shotgun_M37", "CKnife"),
-- checked in order: the first match wins, so "GrenadeLauncher" comes before "Grenade".
local CLASS_RULES = {
    { "grenadelauncher", "launcher" },
    { "handgun", "handgun" },
    { "shotgun", "shotgun" },
    { "magnum", "magnum" },
    { "machinegun", "smg" },
    { "burner", "burner" },
    { "chainsaw", "saw" }, { "circularsaw", "saw" },
    { "knife", "knife" }, { "axe", "knife" },
    { "grenade", "throw" }, { "bomb", "throw" },
}
local GUNS = { handgun = true, shotgun = true, magnum = true, smg = true, burner = true,
               launcher = true }

local config = { enabled = true, lightbar = true, profiles = {} }
local state = { weapon = nil, class = "none", ammo = nil, last_text = nil,
                last_poll = 0, error = nil, wrote = 0, stage = "starting" }

-- -- config -------------------------------------------------------------------------------
local function load_config()
    local ok, saved = pcall(json.load_file, CONFIG_FILE)
    if ok and type(saved) == "table" then
        for k, v in pairs(saved) do config[k] = v end
    end
end

local function save_config()
    pcall(json.dump_file, CONFIG_FILE, config)
end

local function profile(class)
    local base = PROFILES[class] or PROFILES.other
    local over = type(config.profiles) == "table" and config.profiles[class]
    if type(over) ~= "table" then return base end
    local p = {}
    for k, v in pairs(base) do p[k] = v end
    for k, v in pairs(over) do p[k] = v end
    return p
end

-- -- the payload --------------------------------------------------------------------------
local function instruction(kind, params)
    local parts = {}
    for i, v in ipairs(params) do parts[i] = tostring(math.floor(v)) end
    return string.format('{"type":%d,"parameters":[%s]}', kind, table.concat(parts, ","))
end

local function payload(class, empty)
    if class == nil then
        return '{"instructions":[' .. instruction(7, {0}) .. ']}'
    end
    local p = profile(class)
    local r2 = (empty and GUNS[class]) and EMPTY_R2 or p.r2
    local list = {
        instruction(7, {0}),                                  -- start clean every time
        instruction(1, {0, 1, table.unpack(p.l2)}),
        instruction(1, {0, 2, table.unpack(r2)}),
        instruction(4, {0, 2, empty and 0 or (p.fire or 0)}),
    }
    if config.lightbar and p.rgb then
        list[#list + 1] = instruction(2, {0, p.rgb[1], p.rgb[2], p.rgb[3]})
    end
    return '{"instructions":[' .. table.concat(list, ",") .. ']}'
end

local function write(text)
    if text == state.last_text then return end
    local f = io.open(OUT_FILE, "wb")
    if not f then
        state.error = "can't write reframework/data/" .. OUT_FILE
        return
    end
    f:write(text)
    f:close()
    state.last_text, state.error, state.wrote = text, nil, state.wrote + 1
end

-- -- the game -----------------------------------------------------------------------------
local function try_call(obj, method)
    local ok, v = pcall(obj.call, obj, method)
    return ok and v or nil
end

local function try_field(obj, name)
    local ok, v = pcall(obj.get_field, obj, name)
    return ok and v or nil
end

-- The player's equipment manager: InteractManager -> _PlayerStatus -> EquipManager.
local function equip_manager()
    local interact = sdk.get_managed_singleton("app.InteractManager")
    if not interact then return nil, "no InteractManager" end
    local status = try_field(interact, "_PlayerStatus")
    if not status then return nil, "no player (menu or cutscene)" end
    local equip = try_field(status, "EquipManager")
    if not equip then return nil, "no EquipManager" end
    return equip
end

local function class_of(item_id)
    if type(item_id) ~= "string" or item_id == "" or item_id == "None" then return "none" end
    local id = item_id:lower()
    for _, rule in ipairs(CLASS_RULES) do
        if id:find(rule[1], 1, true) then return rule[2] end
    end
    return "other"
end

local function poll()
    local equip, why = equip_manager()
    state.stage = why or "ok"
    if not equip then
        state.weapon, state.class, state.ammo = nil, "none", nil
        write(payload(nil))                 -- menus, cutscenes: triggers back to normal
        return
    end
    local item = try_call(equip, "get_equipWeaponItemIDRight")
    item = item ~= nil and tostring(item) or nil
    local class = class_of(item)
    local ammo
    if GUNS[class] then
        local weapon = try_call(equip, "get_equipWeaponRight")
        ammo = weapon and tonumber(try_call(weapon, "get_loadNum")) or nil
    end
    state.weapon, state.class, state.ammo = item, class, ammo
    write(payload(class, ammo == 0))
end

-- What the script sees, written to reframework/data/DualSenseBridge/re7_status.txt when
-- it changes (and shown in the menu), for troubleshooting from outside the game.
local last_report
local function report()
    local line = string.format("player: %s | weapon: %s (%s) | ammo: %s | error: %s",
        tostring(state.stage), tostring(state.weapon), state.class, tostring(state.ammo),
        tostring(state.error))
    if line == last_report then return end
    last_report = line
    local f = io.open(STATUS_FILE, "wb")
    if f then
        f:write(os.date("%H:%M:%S ") .. line .. "\n")
        f:close()
    end
    if state.error then log.info("[DualSense Bridge] " .. line) end
end

-- -- REFramework hooks --------------------------------------------------------------------
load_config()

re.on_frame(function()
    local now = os.clock()
    if now - state.last_poll < POLL then return end
    state.last_poll = now
    if not config.enabled then
        write(payload(nil))
        return
    end
    local ok, err = pcall(poll)
    state.error = not ok and tostring(err) or nil
    report()
end)

re.on_script_reset(function()
    state.last_text = nil
    write(payload(nil))
end)

re.on_draw_ui(function()
    if not imgui.tree_node("DualSense Bridge: adaptive triggers") then return end
    local changed
    changed, config.enabled = imgui.checkbox("Enabled", config.enabled)
    if changed then save_config() end
    changed, config.lightbar = imgui.checkbox("Lightbar colour per weapon", config.lightbar)
    if changed then
        state.last_text = nil
        save_config()
    end
    imgui.text(string.format("Weapon: %s (%s)", tostring(state.weapon or "none"), state.class))
    if GUNS[state.class] then
        imgui.text("Loaded ammo: " .. tostring(state.ammo))
    end
    imgui.text("Updates written: " .. state.wrote)
    imgui.text("Player: " .. tostring(state.stage))
    if state.error then imgui.text("Problem: " .. state.error) end
    imgui.tree_pop()
end)
