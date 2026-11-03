-- DualSense Companion: test weapons for Resident Evil 4 (2023)
-- A testing helper for the adaptive-trigger script: puts one of every weapon (and some ammo)
-- into the storage you reach from any typewriter. Weapons you already own are skipped:
-- storage merges duplicate weapons, which would undo the upgrades on the copy you carry.
--
-- Install: copy into reframework\autorun. Use: REFramework menu (Insert) →
-- "DualSense-Companion: test weapons". Remove it again when you're done testing.
--
-- Item creation via chainsaw.ChainsawGuiUtil.generateItem and storage via
-- chainsaw.ArmouryManager.addArmouryItem, as documented by the RE4R Archipelago project
-- (github.com/LiterallyMetaphorical/RE4R-AP-Wizard, MIT), which credits chenstack's item_adder.
-- MIT licence, like the rest of DualSense Companion.

-- Weapon item IDs: 274835456 + 1600 x (weapon number - 4000), e.g. wp4100 W-870.
local WEAPONS = {
    { "SG-09 R", 4000 }, { "Punisher", 4001 }, { "Red9", 4002 }, { "Blacktail", 4003 },
    { "Matilda", 4004 }, { "Sentinel Nine", 6000 }, { "XM96E1", 6300 },
    { "W-870", 4100 }, { "Riot Gun", 4101 }, { "Striker", 4102 }, { "Skull Shaker", 6001 },
    { "TMP", 4200 }, { "Chicago Sweeper", 4201 }, { "LE 5", 4202 },
    { "SR M1903", 4400 }, { "Stingray", 4401 }, { "CQBR Assault Rifle", 4402 },
    { "Broken Butterfly", 4500 }, { "Killer7", 4501 }, { "Handcannon", 4502 },
    { "Bolt Thrower", 4600 }, { "Flamethrower", 4701 }, { "Rocket Launcher", 4900 },
}
local AMMO = {
    { "Handgun Ammo", 112800000, 50 }, { "Shotgun Shells", 112803200, 20 },
    { "Rifle Ammo", 112804800, 20 }, { "Submachine Gun Ammo", 112806400, 100 },
    { "Bolts", 112808000, 10 },
}
local GRENADES = { { "Hand Grenade", 277075456 }, { "Flash Grenade", 277078656 },
                   { "Heavy Grenade", 277077056 } }

local function item_id(weapon) return 274835456 + 1600 * (weapon - 4000) end

local status = "Ready"

local function armoury()
    return sdk.get_managed_singleton("chainsaw.ArmouryManager")
end

local function owned(id)
    local a = armoury()
    local ok, n = pcall(function() return a:call("getItemCountSum", id) end)
    return ok and (tonumber(n) or 0) > 0
end

local function store(id, count)
    local a = armoury()
    if not a then return false, "no ArmouryManager (load a save first)" end
    local util = sdk.find_type_definition("chainsaw.ChainsawGuiUtil")
    local generate = util and util:get_method("generateItem")
    if not generate then return false, "generateItem not found" end
    local item = generate:call(nil, id, count, -1, -1, 100, 0)
    if not item then return false, "could not create item " .. id end
    local wrapper = sdk.create_instance("chainsaw.ArmouryItem", true)
    if not wrapper then return false, "could not create a storage entry" end
    if wrapper.add_ref then wrapper = wrapper:add_ref() end
    wrapper:set_field("_Item", item)
    wrapper:set_field("_CurrVirtualStackCount", 1)
    wrapper:set_field("_VirtualStackableCountMax", 1)
    a:call("addArmouryItem(chainsaw.ArmouryItem)", wrapper)
    return true
end

local function give(list, to_id, skip_owned, count_of)
    local added, skipped, failed = 0, 0, {}
    for _, entry in ipairs(list) do
        local id = to_id(entry)
        if skip_owned and owned(id) then
            skipped = skipped + 1
        else
            local ok, res, err = pcall(store, id, count_of and count_of(entry) or 1)
            if ok and res then
                added = added + 1
            else
                failed[#failed + 1] = entry[1] .. " (" .. tostring(ok and err or res) .. ")"
            end
        end
    end
    status = string.format("Added %d, already owned %d%s", added, skipped,
        #failed > 0 and (", failed: " .. table.concat(failed, ", ")) or "")
    log.info("[DualSense Companion test weapons] " .. status)
end

re.on_draw_ui(function()
    if not imgui.tree_node("DualSense-Companion: test weapons") then return end
    imgui.text("Adds to storage (take them out at any typewriter).")
    if imgui.button("Every weapon") then
        give(WEAPONS, function(w) return item_id(w[2]) end, true)
    end
    imgui.same_line()
    if imgui.button("Ammo") then
        give(AMMO, function(a) return a[2] end, false, function(a) return a[3] end)
    end
    imgui.same_line()
    if imgui.button("Grenades") then
        give(GRENADES, function(g) return g[2] end, false, function() return 3 end)
    end
    for _, w in ipairs(WEAPONS) do
        if imgui.button(w[1] .. " (wp" .. w[2] .. ")") then
            give({ w }, function(x) return item_id(x[2]) end, true)
        end
    end
    imgui.text(status)
    imgui.tree_pop()
end)
