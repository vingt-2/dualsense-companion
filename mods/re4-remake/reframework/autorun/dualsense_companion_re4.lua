-- DualSense Companion: adaptive triggers for Resident Evil 4 (2023)
-- https://github.com/vingt-2/dualsense-companion (mods/re4-remake)
--
-- Gives each weapon class its own trigger feel, and shows the player's health on the
-- lightbar as on PS5. Guns get a trigger wall that breaks, and the
-- game only sees R2 once the wall has broken, so the shot fires at the break like a real
-- trigger. Needs REFramework and DualSense Companion 1.7 or later, which reads the file this
-- script writes (reframework\data\DualSenseCompanion\re4_triggers.json) and applies it.
--
-- The file uses DSX's instruction format (DualSenseX's mod protocol):
--   type 1 trigger effect, 2 lightbar, 4 trigger threshold, 7 reset.
-- Trigger effects: 13 Resistance(start zone 0-9, force 1-8),
--   22 Weapon(start zone 2-7, break zone 3-8, force 1-8), 23 Vibration(start, amplitude, Hz).
-- Thresholds are trigger positions 0-255: below it the game reads the trigger as released.
--
-- MIT licence, see the repository. Idea: lunati_'s "RE4 Remake Adaptive Triggers" (Nexus).

local OUT_FILE = "DualSenseCompanion/re4_triggers.json"   -- relative to reframework/data
local CONFIG_FILE = "DualSenseCompanion/re4_config.json"
local POLL = 0.1                                       -- s between checks of the weapon

-- Trigger feel per weapon class. l2/r2 = {mode, params...}; fire = R2 threshold.
-- Tune here, or override any class in reframework/data/DualSenseCompanion/re4_config.json.
-- Tuned side by side with the PS5 version: aim (L2) is almost free except on launchers, and
-- the rocket launcher has the strongest wall.
local PROFILES = {
    none     = { l2 = {0},           r2 = {0},           fire = 0,   rgb = nil },
    handgun  = { l2 = {0},           r2 = {22, 3, 6, 1}, fire = 190, rgb = {0, 120, 255} },
    shotgun  = { l2 = {13, 0, 1},    r2 = {22, 3, 7, 5}, fire = 205, rgb = {255, 50, 30} },
    rifle    = { l2 = {13, 0, 1},    r2 = {22, 2, 5, 5}, fire = 165, rgb = {255, 220, 0} },
    magnum   = { l2 = {0},           r2 = {22, 3, 7, 5}, fire = 205, rgb = {170, 0, 255} },
    smg      = { l2 = {13, 7, 1},    r2 = {23, 3, 5, 15}, fire = 0,  rgb = {255, 130, 0} },
    bow      = { l2 = {13, 0, 1},    r2 = {22, 5, 8, 6}, fire = 230, rgb = {0, 255, 255} },
    launcher = { l2 = {13, 0, 6},    r2 = {22, 5, 8, 8}, fire = 230, rgb = {255, 0, 80} },
    knife    = { l2 = {0},           r2 = {0},           fire = 0,   rgb = {255, 255, 255} },
    throw    = { l2 = {13, 0, 1},    r2 = {13, 0, 3},    fire = 0,   rgb = {0, 255, 60} },
    other    = { l2 = {13, 0, 1},    r2 = {0},           fire = 0,   rgb = nil },
}
-- A gun with an empty magazine: a light, early click, so the dry fire registers at once.
local EMPTY_R2 = {22, 2, 4, 3}

-- The lightbar shows the player's health, as on PS5: green while fine, yellow then orange as
-- it drops (caution), red in danger. Untick it in the menu (or set "lightbar_health": false in
-- the config) for a colour per weapon class instead.
local HEALTH_COLOURS = {          -- {above this share of max health, colour}
    { 0.66, {0, 255, 40} },
    { 0.45, {255, 200, 0} },
    { 0.25, {255, 90, 0} },
    { -1,   {255, 0, 0} },
}

local function health_colour(ratio)
    if not ratio then return nil end
    for _, c in ipairs(HEALTH_COLOURS) do
        if ratio > c[1] then return c[2] end
    end
end

-- Every weapon's class by its ID (main game, Separate Ways and Mercenaries). Classes as
-- listed in Advanced Weapon Framework's RE4 weapon data (SilverEzredes).
local WEAPON_CLASS = {}
for class, ids in pairs({
    handgun  = { 4000, 4001, 4002, 4003, 4004, 6000, 6103, 6112, 6113, 6300 },
    shotgun  = { 4100, 4101, 4102, 6001, 6100 },
    smg      = { 4200, 4201, 4202, 6101, 6104, 4701 },   -- 4701 flamethrower: a steady buzz
    rifle    = { 4400, 4401, 4402, 6105, 6114 },
    magnum   = { 4500, 4501, 4502 },
    bow      = { 4600, 6102, 6304 },
    launcher = { 4900, 4901, 4902, 6106, 6111 },
    knife    = { 5000, 5001, 5002, 5003, 5006, 6107, 6108 },
    throw    = { 5400, 5401, 5402, 5403, 5404, 5405 },
}) do
    for _, id in ipairs(ids) do WEAPON_CLASS[id] = class end
end
-- Unlisted weapons (e.g. from a future update) by their ID family: wp40xx pistols, ...
local FAMILIES = { [40] = "handgun", [41] = "shotgun", [42] = "smg", [44] = "rifle",
                   [45] = "magnum", [46] = "bow", [49] = "launcher", [50] = "knife",
                   [54] = "throw" }
local GUNS = { handgun = true, shotgun = true, rifle = true, magnum = true, smg = true,
               bow = true, launcher = true }
-- Player characters' head objects, which carry their equipment (Leon; add others here).
local PLAYER_OBJECTS = { "ch0a0z0_head" }

local config = { enabled = true, lightbar = true, lightbar_health = true, profiles = {} }
local state = { weapon = nil, class = "none", ammo = nil, last_text = nil,
                last_poll = 0, error = nil, wrote = 0 }

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

-- Everything back to normal: the script is off or being reloaded.
local function release()
    return '{"instructions":[' .. instruction(7, {0}) .. ']}'
end

local function health_rgb()
    if config.lightbar and config.lightbar_health ~= false then return health_colour(state.health) end
    return nil
end

local function payload(class, empty)
    if class == nil then                    -- nothing in hand: normal triggers, health still shown
        local rgb = health_rgb()
        if not rgb then return release() end
        return '{"instructions":[' .. instruction(7, {0}) .. "," ..
            instruction(2, {0, rgb[1], rgb[2], rgb[3]}) .. ']}'
    end
    local p = profile(class)
    local r2 = (empty and GUNS[class]) and EMPTY_R2 or p.r2
    local list = {
        instruction(7, {0}),                                  -- start clean every time
        instruction(1, {0, 1, table.unpack(p.l2)}),
        instruction(1, {0, 2, table.unpack(r2)}),
        instruction(4, {0, 2, empty and 0 or (p.fire or 0)}),
    }
    local rgb = p.rgb
    if config.lightbar_health ~= false then rgb = health_colour(state.health) end
    if config.lightbar and rgb then
        list[#list + 1] = instruction(2, {0, rgb[1], rgb[2], rgb[3]})
    end
    return '{"instructions":[' .. table.concat(list, ",") .. ']}'
end

local function write(text)
    if text == state.last_text then return end
    local f = io.open(OUT_FILE, "wb")
    if not f then
        state.error = "can't write reframework/data/" .. OUT_FILE .. " (is its folder there?)"
        return
    end
    f:write(text)
    f:close()
    state.last_text, state.error, state.wrote = text, nil, state.wrote + 1
end

-- -- the game -----------------------------------------------------------------------------
local function current_scene()
    local manager = sdk.get_native_singleton("via.SceneManager")
    if not manager then return nil end
    return sdk.call_native_func(manager, sdk.find_type_definition("via.SceneManager"),
        "get_CurrentScene")
end

-- Returns the equipment component, or nil and the step that failed (shown in the menu).
local function try_call(obj, method)
    local ok, v = pcall(obj.call, obj, method)
    return ok and v or nil
end

local function equipment_on(game_object)
    if not game_object then return nil end
    local ok, c = pcall(game_object.call, game_object, "getComponent(System.Type)",
        sdk.typeof("chainsaw.PlayerEquipment"))
    return ok and c or nil
end

-- The player's equipment: from the player context's body (or head) object, else by name.
local function player_equipment()
    local manager = sdk.get_managed_singleton("chainsaw.CharacterManager")
    if not manager then return nil, "no CharacterManager" end
    local context = try_call(manager, "getPlayerContextRef")
    if not context then return nil, "no player (menu or cutscene)" end
    for _, getter in ipairs({ "get_BodyGameObject", "get_HeadGameObject" }) do
        local equipment = equipment_on(try_call(context, getter))
        if equipment then return equipment, nil, getter end
    end
    local scene = current_scene()
    for _, name in ipairs(PLAYER_OBJECTS) do
        local equipment = scene and equipment_on(scene:call("findGameObject(System.String)", name))
        if equipment then return equipment, nil, name end
    end
    local body = try_call(context, "get_BodyGameObject")
    return nil, body and ("no PlayerEquipment on body " .. tostring(try_call(body, "get_Name")))
        or "no player object"
end

-- Loaded rounds: the inventory's equipped weapon knows them (get_CurrentAmmoCount). The
-- inventory controller is reached from the player, or failing that from InventoryManager.
local function inventory_controller()
    local pm = sdk.get_managed_singleton("chainsaw.PlayerManager")
    local player = pm and try_call(pm, "get_CurrentPlayer")
    local c = player and try_call(player, "get_InventoryController")
    if c then return c, "PlayerManager" end
    local cm = sdk.get_managed_singleton("chainsaw.CharacterManager")
    player = cm and try_call(cm, "get_ManualPlayer")
    c = player and try_call(player, "get_InventoryController")
    if c then return c, "ManualPlayer" end
    local manager = sdk.get_managed_singleton("chainsaw.InventoryManager")
    local table_ = manager and manager:get_field("_ControllerTable")
    local values = table_ and try_call(table_, "get_Values")
    local it = values and try_call(values, "GetEnumerator")
    for _ = 1, 64 do                         -- bounded: never spin on a bad enumerator
        if not (it and try_call(it, "MoveNext")) then break end
        local controller = try_call(it, "get_Current")
        local td = controller and controller:get_type_definition()
        if td and td:get_full_name() == "chainsaw.CsInventoryController" then
            return controller, "InventoryManager"
        end
    end
    return nil, "no inventory controller"
end

local function loaded_ammo()
    local controller, via = inventory_controller()
    if not controller then
        state.ammo_via = via
        return nil
    end
    local weapon = try_call(controller, "getEquippedWeapon")
    if not weapon then
        local ok, w = pcall(controller.call, controller, "getEquippedWeapon", 0)
        weapon = ok and w or nil
    end
    if not weapon then
        state.ammo_via = via .. ": no equipped weapon"
        return nil
    end
    local ammo = tonumber(try_call(weapon, "get_CurrentAmmoCount"))
    state.ammo_via = via .. (ammo and "" or ": no ammo count")
    return ammo
end

local function class_of(weapon)
    if not weapon or weapon < 0 then return "none" end
    return WEAPON_CLASS[weapon] or FAMILIES[math.floor(weapon / 100)] or "other"
end

-- -- health -------------------------------------------------------------------------------
local function component(game_object, type_name)
    local ok, t = pcall(sdk.typeof, type_name)
    if not ok or not t then return nil end
    local ok2, c = pcall(game_object.call, game_object, "getComponent(System.Type)", t)
    return ok2 and c or nil
end

-- Share of max health (0-1) from a health object: hit points (current / default) or a damage
-- controller (health / maxHealth), whichever it has.
local function health_ratio(obj)
    if not obj then return nil end
    for _, pair in ipairs({ { "get_CurrentHitPoint", "get_DefaultHitPoint" },
                            { "get_health", "get_maxHealth" } }) do
        local hp, max = tonumber(try_call(obj, pair[1])), tonumber(try_call(obj, pair[2]))
        if hp and max and max > 0 then return math.max(0, math.min(1, hp / max)) end
    end
    return nil
end

-- The player's hit points: the player context's HitPoint (current / default).
local function player_health()
    local manager = sdk.get_managed_singleton("chainsaw.CharacterManager")
    local context = manager and try_call(manager, "getPlayerContextRef")
    if not context then return nil, "no player" end
    local r = health_ratio(try_call(context, "get_HitPoint"))
    return r, r and "HitPoint" or "no HitPoint"
end

local function poll()
    state.health, state.health_via = player_health()
    local equipment, why, via = player_equipment()
    state.stage = why or ("ok via " .. tostring(via))
    if not equipment then
        state.weapon, state.class, state.ammo = nil, "none", nil
        write(payload(nil))                 -- menus, cutscenes: triggers back to normal
        return
    end
    local weapon = tonumber(equipment:call("get_EquipWeaponID()"))
    local class = class_of(weapon)
    local ammo = GUNS[class] and loaded_ammo() or nil
    state.weapon, state.class, state.ammo = weapon, class, ammo
    write(payload(class, ammo == 0))
end

-- What the script sees, written to reframework/data/DualSenseCompanion/re4_status.txt when
-- it changes (and shown in the menu), for troubleshooting from outside the game.
local last_report
local function report()
    local line = string.format("player: %s | weapon: %s (%s) | ammo: %s (%s) | health: %s (%s) | error: %s",
        tostring(state.stage), tostring(state.weapon), state.class, tostring(state.ammo),
        tostring(state.ammo_via), tostring(state.health), tostring(state.health_via),
        tostring(state.error))
    if line == last_report then return end
    last_report = line
    local f = io.open("DualSenseCompanion/re4_status.txt", "wb")
    if f then
        f:write(os.date("%H:%M:%S ") .. line .. "\n")
        f:close()
    end
    if state.error then log.info("[DualSense Companion] " .. line) end
end

-- -- REFramework hooks --------------------------------------------------------------------
load_config()

re.on_frame(function()
    local now = os.clock()
    if now - state.last_poll < POLL then return end
    state.last_poll = now
    if not config.enabled then
        write(release())
        return
    end
    local ok, err = pcall(poll)
    state.error = not ok and tostring(err) or nil
    report()
end)

re.on_script_reset(function()
    state.last_text = nil
    write(release())
end)

re.on_draw_ui(function()
    if not imgui.tree_node("DualSense-Companion") then return end
    local changed
    changed, config.enabled = imgui.checkbox("Enabled", config.enabled)
    if changed then save_config() end
    changed, config.lightbar = imgui.checkbox("Lightbar", config.lightbar)
    if changed then
        state.last_text = nil
        save_config()
    end
    local health_on = config.lightbar_health ~= false
    changed, health_on = imgui.checkbox("Lightbar shows health, as on PS5 (off: colour per weapon)",
        health_on)
    if changed then
        config.lightbar_health = health_on
        state.last_text = nil
        save_config()
    end
    imgui.text("Health: " .. (state.health and string.format("%d%%", math.floor(state.health * 100 + 0.5))
        or tostring(state.health_via)))
    imgui.text(string.format("Weapon: %s (%s)", state.weapon and ("wp" .. state.weapon) or "none",
        state.class))
    if GUNS[state.class] then
        imgui.text("Loaded ammo: " .. tostring(state.ammo))
    end
    imgui.text("Updates written: " .. state.wrote)
    imgui.text("Player: " .. tostring(state.stage))
    if state.error then imgui.text("Problem: " .. state.error) end
    imgui.tree_pop()
end)
