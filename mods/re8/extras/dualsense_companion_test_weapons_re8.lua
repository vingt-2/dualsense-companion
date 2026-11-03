-- DualSense Companion: test weapons for Resident Evil Village
-- A testing helper for the adaptive-trigger work: puts weapons (and some ammo) straight into
-- the inventory. It's a cheat, for testing only; remove it when you're done. Guns you already
-- carry are skipped. The inventory has limited room: if a gun doesn't fit, make space (or
-- enlarge the case at the Duke) and press the button again.
--
-- Install: copy into reframework\autorun. Use: REFramework menu (Insert) ->
-- Script Generated UI -> "DualSense-Companion: test weapons (Village)".
--
-- Game facts (an item's ID is the 32-bit murmur3 hash of its name, e.g. "ri3046", in UTF-16
-- with seed 0xFFFFFFFF; items are made with InventoryManager.createItemCore and added with
-- the active inventory's addItem; ammo with createAndAddItem) as worked out by the Visceral
-- RE8 VR project (github.com/TefMeister/visceral-re8-vr). MIT licence, like the rest of
-- DualSense Companion.

local WEAPONS = {
    { "M1911", "ri3040" }, { "LEMI", "ri3046" }, { "V61 Custom", "ri3047" },
    { "USM-AI", "ri3124" }, { "Samurai Edge", "ri3122" },
    { "M1851 Wolfsbane", "ri3008" }, { "S.T.A.K.E.", "ri3050" },
    { "W870 TAC", "ri3021" }, { "M1897", "ri3036" }, { "SYG-12", "ri3048" },
    { "F2 Rifle", "ri3042" }, { "WCX", "ri3049" }, { "Dragoon", "ri3125" },
    { "GM 79", "ri3023" }, { "Rocket Pistol", "ri3115" }, { "Handcannon PZ", "ri3116" },
}
-- Ammo item IDs seen added in game by the VR project (handgun and shotgun named there;
-- the others are its rifle, magnum and launcher rounds).
local AMMO = {
    { "Handgun ammo", 1179972000, 30 }, { "Shotgun shells", 1731811000, 20 },
    { "Ammo 3", 3919597625, 20 }, { "Ammo 4", 2182652875, 20 },
    { "Ammo 5", 2275184395, 6 }, { "Ammo 6", 3188868396, 30 },
}

local SIG_CREATE = "createItemCore(System.UInt32, System.Int32, System.UInt32, System.Int32)"
local SIG_CREATE_ADD = "createAndAddItem(System.UInt32, System.Int32, System.UInt32, System.Int32)"
local SIG_ADD = "addItem(app.ItemCore.InstanceWork, System.Boolean, System.Boolean, System.Boolean)"

local status = "Ready"

-- murmur3 (32-bit) of a name in UTF-16LE, seed 0xFFFFFFFF: the game's item ID
local function item_id(name)
    local M = 0xFFFFFFFF
    local function mul(a, b)                       -- 32-bit multiply without overflow
        return ((a & 0xFFFF) * b + (((a >> 16) * b) & 0xFFFF) * 0x10000) & M
    end
    local function rotl(x, r) return ((x << r) | (x >> (32 - r))) & M end
    local bytes = {}
    for i = 1, #name do bytes[#bytes + 1] = name:byte(i); bytes[#bytes + 1] = 0 end
    local h, n = M, #bytes
    local i = 1
    while i + 3 <= n do
        local k = bytes[i] | (bytes[i + 1] << 8) | (bytes[i + 2] << 16) | (bytes[i + 3] << 24)
        k = mul(rotl(mul(k, 0xcc9e2d51), 15), 0x1b873593)
        h = (mul(rotl(h ~ k, 13), 5) + 0xe6546b64) & M
        i = i + 4
    end
    local k, shift = 0, 0
    while i <= n do k = k | (bytes[i] << shift); shift = shift + 8; i = i + 1 end
    if shift > 0 then h = h ~ mul(rotl(mul(k, 0xcc9e2d51), 15), 0x1b873593) end
    h = h ~ n
    h = mul(h ~ (h >> 16), 0x85ebca6b)
    h = mul(h ~ (h >> 13), 0xc2b2ae35)
    return h ~ (h >> 16)
end

local function managers()
    local im = sdk.get_managed_singleton("app.InventoryManager")
    local ok, inv = pcall(function() return im and im:call("get_activeInventory") end)
    if not ok or not inv then return nil, nil, "no inventory (load a save first)" end
    return im, inv
end

local function give_weapons(list)
    local im, inv, why = managers()
    if not inv then status = "Couldn't add: " .. why return end
    local added, owned, failed = 0, 0, {}
    for _, w in ipairs(list) do
        local id = item_id(w[2])
        local ok_has, has = pcall(inv.call, inv, "hasItem", id, false, false)
        if ok_has and has then
            owned = owned + 1
        else
            local ok = pcall(function()
                local core = im:call(SIG_CREATE, id, 1, 0, 0)
                local work = core and core:call("get_work")
                assert(work, "no item")
                inv:call(SIG_ADD, work, false, false, false)
            end)
            local now_ok, now = pcall(inv.call, inv, "hasItem", id, false, false)
            if ok and (not now_ok or now) then added = added + 1 else failed[#failed + 1] = w[1] end
        end
    end
    status = string.format("Added %d, already had %d%s", added, owned,
        #failed > 0 and (", no room or failed: " .. table.concat(failed, ", ")) or "")
    log.info("[DualSense Companion test weapons] " .. status)
end

local function give_ammo()
    local im, inv, why = managers()
    if not inv then status = "Couldn't add: " .. why return end
    local added, failed = 0, {}
    for _, a in ipairs(AMMO) do
        local ok, r = pcall(im.call, im, SIG_CREATE_ADD, a[2], a[3], 0, 0)
        if ok and r then added = added + 1 else failed[#failed + 1] = a[1] end
    end
    status = string.format("Added %d kinds of ammo%s", added,
        #failed > 0 and (", no room or failed: " .. table.concat(failed, ", ")) or "")
    log.info("[DualSense Companion test weapons] " .. status)
end

re.on_draw_ui(function()
    if not imgui.tree_node("DualSense-Companion: test weapons (Village)") then return end
    imgui.text("Adds straight to the inventory. Guns you carry are skipped.")
    if imgui.button("Every weapon") then give_weapons(WEAPONS) end
    imgui.same_line()
    if imgui.button("Ammo") then give_ammo() end
    for _, w in ipairs(WEAPONS) do
        if imgui.button(w[1]) then give_weapons({ w }) end
    end
    imgui.text(status)
    imgui.tree_pop()
end)
