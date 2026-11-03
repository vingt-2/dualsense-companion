-- DualSense Companion: test weapons for Resident Evil 7 biohazard
-- A testing helper for the adaptive-trigger work: puts every weapon (and some ammo) into the
-- item box, which you open at any save-room box. It's a cheat, for testing only; remove it
-- when you're done.
--
-- Install: copy into reframework\autorun. Use: REFramework menu (Insert) ->
-- Script Generated UI -> "DualSense-Companion: test weapons (RE7)".
--
-- Game facts (item IDs; the player via app.ObjectManager.PlayerObj, its app.Inventory and the
-- item box's addItem) as documented by the RE7 Archipelago client
-- (github.com/ElGrenier/RE7_AP_Client, MIT). MIT licence, like the rest of DualSense Companion.

local WEAPONS = {
    { "G17 Handgun", "Handgun_G17" }, { "M19 Handgun", "Handgun_M19" },
    { "MPM Handgun", "Handgun_MPM" }, { "Albert-01", "Handgun_Albert" },
    { "M37 Shotgun", "Shotgun_M37" }, { "Db Shotgun", "Shotgun_DB" },
    { "44 MAG", "Magnum" }, { "P19 Machine Gun", "MachineGun" },
    { "Burner", "Burner" }, { "Grenade Launcher", "GrenadeLauncher" },
    { "Survival Knife", "MiaKnife" }, { "Knife", "Knife" },
    { "Axe", "HandAxe" }, { "Chain Saw", "ChainSaw" }, { "Circular Saw", "CircularSaw" },
    { "Remote Bomb", "LiquidBomb" },
}
local AMMO = {
    { "Handgun Ammo", "HandgunBullet", 60 }, { "Enhanced Handgun Ammo", "HandgunBulletL", 30 },
    { "Shotgun Ammo", "ShotgunBullet", 20 }, { "44 Mag Ammo", "MagnumBullet", 12 },
    { "Machine Gun Ammo", "MachineGunBullet", 120 }, { "Burner Fuel", "BurnerBullet", 200 },
    { "Flame Rounds", "FlameBulletS", 10 }, { "Neuro Rounds", "AcidBulletS", 10 },
}

-- Not a Hero (Chris) has its own inventory and weapons: Ethan's can't be equipped there.
-- IDs seen in game with the probe (2026-11-01).
local DLC_WEAPONS = {
    { "Albert-01R Handgun", "Handgun_Albert_C" }, { "Shotgun", "Shotgun_Albert" },
    { "Grenade", "Grenadebomb" }, { "Knife", "CKnife" },
}
local DLC_AMMO = {
    { "Handgun Ammo", "AlbertHandgunBullet", 60 }, { "Shotgun Ammo", "AlbertShotgunBullet", 20 },
}

local status = "Ready"

local function inventory()
    local objects = sdk.get_managed_singleton("app.ObjectManager")
    local player = objects and objects:get_field("PlayerObj")
    if not player then return nil end
    return player:call("getComponent(System.Type)", sdk.typeof("app.Inventory"))
end

-- Not a Hero's inventory is an app.CH8Inventory
local function in_dlc()
    local inv = inventory()
    local td = inv and inv:get_type_definition()
    local name = td and td:get_full_name() or ""
    return name:find("CH8", 1, true) ~= nil
end

local function item_box()
    local inv = inventory()
    if not inv then return nil, "no player (load a save first)" end
    local box = inv:get_field("<ItemBoxData>k__BackingField")
    if not box then return nil, "no item box data" end
    return box
end

local function give(list, default_count)
    local box, why = item_box()
    if not box then
        status = "Couldn't add: " .. why
        return
    end
    local added, failed = 0, {}
    for _, entry in ipairs(list) do
        local ok, err = pcall(box.call, box,
            "addItem(System.String, System.Int32, app.WeaponGun.WeaponGunSaveData)",
            entry[2], entry[3] or default_count, nil)
        if ok then
            added = added + 1
        else
            failed[#failed + 1] = entry[1] .. " (" .. tostring(err) .. ")"
        end
    end
    status = string.format("Added %d to the item box%s", added,
        #failed > 0 and (", failed: " .. table.concat(failed, ", ")) or "")
    log.info("[DualSense Companion test weapons] " .. status)
end

re.on_draw_ui(function()
    if not imgui.tree_node("DualSense-Companion: test weapons (RE7)") then return end
    local dlc = in_dlc()
    local weapons, ammo = dlc and DLC_WEAPONS or WEAPONS, dlc and DLC_AMMO or AMMO
    imgui.text((dlc and "Not a Hero: Chris's weapons. " or "Main game: Ethan's weapons. ")
        .. "Adds to the item box (open it at any save-room box).")
    if imgui.button("Every weapon") then give(weapons, 1) end
    imgui.same_line()
    if imgui.button("Ammo") then give(ammo, 1) end
    for _, w in ipairs(weapons) do
        if imgui.button(w[1]) then give({ w }, 1) end
    end
    imgui.text(status)
    imgui.tree_pop()
end)
