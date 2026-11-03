"""Games with a DualSense mod of ours (adaptive triggers, and PlayStation button prompts
where the game lacks them), played through DualSense Companion.

When one of these games is running and its mod isn't installed, the tray offers the mod's
setup guide. A new game is one more entry here.
"""
import os

REPO = "https://github.com/vingt-2/dualsense-companion"
RAW = "https://raw.githubusercontent.com/vingt-2/dualsense-companion/main"

# The lightbar, the same in every game's mod (see the scripts' HEALTH_COLOURS)
LIGHTBAR = ("Your health shows on the lightbar, as on PS5: green, then yellow and orange as "
            "it drops, red in danger. The mod's REFramework menu can switch it to a colour "
            "per weapon instead.")

GAMES = [
    {
        "exe": "re4.exe",
        "name": "Resident Evil 4",
        # any of these next to the exe means the mod (or one like it) is already installed
        "installed": [r"reframework\autorun\dualsense_companion_re4.lua"],
        "data": r"reframework\data\DualSenseCompanion",      # the mod's own files (removed on uninstall)
        "guide": f"{REPO}/tree/main/mods/re4-remake#readme",
        "features": "adaptive triggers",          # what the mod adds, for the tray's messages
        # shown by the tray's "How it works…"
        "about": (
            "Resident Evil 4 on PC has no adaptive triggers. This DualSense mod adds them.\n\n"
            "•  A small script runs inside the game through REFramework, a widely used mod "
            "loader for Capcom's games. Several times a second it checks which weapon you're "
            "holding, how many rounds are loaded and how much health you have.\n\n"
            "•  Each kind of weapon gets its own trigger feel: pistols, shotguns, rifles, "
            "magnums, SMGs, the bolt thrower, launchers, knives and grenades, tuned side by "
            "side with the PS5 version.\n\n"
            "•  " + LIGHTBAR + "\n\n"
            "•  The script writes that feel to a small file in the game folder. DualSense "
            "Companion follows the file and plays it on your controller's triggers.\n\n"
            "•  Guns have a trigger wall that gives way, like a real trigger, and the app "
            "only lets the game see the trigger once it's past the wall, so the shot fires at "
            "the break. An empty gun gets a light click instead. In menus and cutscenes the "
            "triggers go back to normal.\n\n"
            "The mod only reads the game, it doesn't change it. To remove it, delete "
            "reframework\\autorun\\dualsense_companion_re4.lua in the game folder."),
        # for the automatic install (mod_installer.py)
        "steam_appid": 2050650,
        # REFramework for the installed build: {"repo": GitHub repo, "asset": zip in its
        # latest release}. Stable praydog/REFramework works with RE4's current build (checked
        # 2026-11-01: same dinput8.dll as a working install). For games whose current patch
        # needs newer builds use {"repo": "praydog/REFramework-nightly", "asset":
        # "REFramework.zip"} (one zip for every game, but no old non-RT builds); Steam
        # branches with their own zip go in "reframework_branches", e.g.
        # {"dx11_non-rt": {"repo": "praydog/REFramework", "asset": "RE7_TDB49.zip"}}.
        "reframework": {"repo": "praydog/REFramework", "asset": "RE4.zip"},
        "files": {r"reframework\autorun\dualsense_companion_re4.lua":
                  f"{RAW}/mods/re4-remake/reframework/autorun/dualsense_companion_re4.lua"},
        # other trigger mods for this game, moved aside so they don't fight over the triggers
        "conflicts": [r"reframework\autorun\DualsenseX.lua", r"reframework\autorun\DualsenseX",
                      r"reframework\data\DualSenseX"],
    },
    {
        "exe": "re7.exe",
        "name": "Resident Evil 7",
        "installed": [r"reframework\autorun\dualsense_companion_re7.lua"],
        "data": r"reframework\data\DualSenseCompanion",
        "guide": f"{REPO}/tree/main/mods/re7#readme",
        "features": "adaptive triggers and PlayStation button prompts",
        "about": (
            "Resident Evil 7 on PC has no adaptive triggers and only shows Xbox buttons. This "
            "DualSense mod adds adaptive triggers and PlayStation button prompts, in the main "
            "game and the DLC episodes.\n\n"
            "•  A small script runs inside the game through REFramework, a widely used mod "
            "loader for Capcom's games. Several times a second it checks which weapon you're "
            "holding, how many rounds are loaded and how much health you have.\n\n"
            "•  Each kind of weapon gets its own trigger feel: handguns, shotguns, the 44 MAG, "
            "the machine gun, the burner, the grenade launcher, knives, saws and throwables, "
            "with the feel of Resident Evil Village on PS5.\n\n"
            "•  " + LIGHTBAR + "\n\n"
            "•  The script writes that feel to a small file in the game folder. DualSense "
            "Companion follows the file and plays it on your controller's triggers.\n\n"
            "•  Guns have a trigger wall that gives way, like a real trigger, and the app "
            "only lets the game see the trigger once it's past the wall, so the shot fires at "
            "the break. An empty gun gets a light click instead. In menus and cutscenes the "
            "triggers go back to normal.\n\n"
            "•  The game's button prompts show PlayStation buttons (✕ ○ □ △, L1, R2, "
            "Options…) instead of Xbox ones. They're loose files that replace the game's "
            "button icons; REFramework loads them. They're only in place while DualSense "
            "Companion is running, so the game shows its own Xbox icons when you play without "
            "it (e.g. with an Xbox controller). The game picks its icons when it starts.\n\n"
            "Keep Steam Input on for the game: Resident Evil 7 only reads Xbox-style "
            "controllers, and Steam Input turns the DualSense into one for it.\n\n"
            "The mod doesn't change the game's own files. Uninstall removes it again."),
        "xinput_only": True,      # the game needs Steam Input (or another XInput emulator)
        "steam_appid": 418370,
        # stable works with RE7's current (ray-traced) build: checked 2026-11-01
        "reframework": {"repo": "praydog/REFramework", "asset": "RE7.zip"},
        "reframework_branches": {
            "dx11_non-rt": {"repo": "praydog/REFramework", "asset": "RE7_TDB49.zip"}},
        "files": {
            r"reframework\autorun\dualsense_companion_re7.lua":
                f"{RAW}/mods/re7/reframework/autorun/dualsense_companion_re7.lua",
            # PlayStation button icons (tools/ps-icons builds them)
            r"natives\stm\ui\ui0000\tex\ui0010_iam.tex.35.x64":
                f"{RAW}/mods/re7/icons/natives/stm/ui/ui0000/tex/ui0010_iam.tex.35.x64",
            r"natives\stm\ui\ui0000\tex\ui0020_iam.tex.35.x64":
                f"{RAW}/mods/re7/icons/natives/stm/ui/ui0000/tex/ui0020_iam.tex.35.x64",
        },
        "loose_files": True,      # REFramework must load files from natives\ (the icons)
        # files that are only in place while DualSense Companion runs (kept in the mod's data
        # folder otherwise): the game shows its own Xbox icons when played without the app
        "while_app_runs": [
            r"natives\stm\ui\ui0000\tex\ui0010_iam.tex.35.x64",
            r"natives\stm\ui\ui0000\tex\ui0020_iam.tex.35.x64",
        ],
        "icons_skip_branches": ["dx11_non-rt"],   # its icon textures differ
        "conflicts": [],
    },
    {
        "exe": "re2.exe",
        "name": "Resident Evil 2",
        "installed": [r"reframework\autorun\dualsense_companion_re2.lua"],
        "data": r"reframework\data\DualSenseCompanion",
        "guide": f"{REPO}/tree/main/mods/re2#readme",
        "features": "adaptive triggers and PlayStation button prompts",
        "about": (
            "Resident Evil 2 on PC has no adaptive triggers and only shows Xbox buttons. This "
            "DualSense mod adds adaptive triggers and PlayStation button prompts.\n\n"
            "•  A small script runs inside the game through REFramework, a widely used mod "
            "loader for Capcom's games. Several times a second it checks which weapon you're "
            "holding, how many rounds are loaded and how much health you have.\n\n"
            "•  Each kind of weapon gets its own trigger feel: handguns, the shotgun, SMGs, the Lightning Hawk, "
            "launchers, the flamethrower and knives, with the feel of "
            "the Resident Evil 4 remake on PS5.\n\n"
            "•  " + LIGHTBAR + "\n\n"
            "•  The script writes that feel to a small file in the game folder. DualSense "
            "Companion follows the file and plays it on your controller's triggers.\n\n"
            "•  Guns have a trigger wall that gives way, like a real trigger, and the app "
            "only lets the game see the trigger once it's past the wall, so the shot fires at "
            "the break. An empty gun gets a light click instead. In menus and cutscenes the "
            "triggers go back to normal.\n\n"
            "•  The game's button prompts show PlayStation buttons (✕ ○ □ △, L1, R2, "
            "Options…) instead of Xbox ones, while DualSense Companion is running (the game "
            "picks its icons when it starts; without the app it shows its own Xbox ones). "
            "Not on the old dx11_non-rt build, which has different icon files.\n\n"
            "Keep Steam Input on for the game: Resident Evil 2 only reads Xbox-style "
            "controllers, "
            "and Steam Input turns the DualSense into one for it.\n\n"
            "The mod doesn't change the game's own files. Uninstall removes it again."),
        "xinput_only": True,
        "steam_appid": 883710,
        "reframework": {"repo": "praydog/REFramework", "asset": "RE2.zip"},
        "reframework_branches": {
            "dx11_non-rt": {"repo": "praydog/REFramework", "asset": "RE2_TDB66.zip"}},
        "files": {
            r"reframework\autorun\dualsense_companion_re2.lua":
                f"{RAW}/mods/re2/reframework/autorun/dualsense_companion_re2.lua",
            r"natives\stm\sectionroot\ui\ui0000\tex\ui0000_iam.tex.34.x64":
                f"{RAW}/mods/re2/icons/natives/stm/sectionroot/ui/ui0000/tex/ui0000_iam.tex.34.x64",
        },
        "loose_files": True,
        "while_app_runs": [r"natives\stm\sectionroot\ui\ui0000\tex\ui0000_iam.tex.34.x64"],
        "icons_skip_branches": ["dx11_non-rt"],   # its icon textures differ
        "conflicts": [],
    },
    {
        "exe": "re3.exe",
        "name": "Resident Evil 3",
        "installed": [r"reframework\autorun\dualsense_companion_re3.lua"],
        "data": r"reframework\data\DualSenseCompanion",
        "guide": f"{REPO}/tree/main/mods/re3#readme",
        "features": "adaptive triggers and PlayStation button prompts",
        "about": (
            "Resident Evil 3 on PC has no adaptive triggers and only shows Xbox buttons. This "
            "DualSense mod adds adaptive triggers and PlayStation button prompts.\n\n"
            "•  A small script runs inside the game through REFramework, a widely used mod "
            "loader for Capcom's games. Several times a second it checks which weapon you're "
            "holding, how many rounds are loaded and how much health you have.\n\n"
            "•  Each kind of weapon gets its own trigger feel: handguns, the shotgun, the CQBR assault rifle, "
            "magnums, launchers, knives and grenades, with the feel of "
            "the Resident Evil 4 remake on PS5.\n\n"
            "•  " + LIGHTBAR + "\n\n"
            "•  The script writes that feel to a small file in the game folder. DualSense "
            "Companion follows the file and plays it on your controller's triggers.\n\n"
            "•  Guns have a trigger wall that gives way, like a real trigger, and the app "
            "only lets the game see the trigger once it's past the wall, so the shot fires at "
            "the break. An empty gun gets a light click instead. In menus and cutscenes the "
            "triggers go back to normal.\n\n"
            "•  The game's button prompts show PlayStation buttons (✕ ○ □ △, L1, R2, "
            "Options…) instead of Xbox ones, while DualSense Companion is running (the game "
            "picks its icons when it starts; without the app it shows its own Xbox ones). "
            "Not on the old dx11_non-rt build, which has different icon files.\n\n"
            "Keep Steam Input on for the game: Resident Evil 3 only reads Xbox-style "
            "controllers, "
            "and Steam Input turns the DualSense into one for it.\n\n"
            "The mod doesn't change the game's own files. Uninstall removes it again."),
        "xinput_only": True,
        "steam_appid": 952060,
        "reframework": {"repo": "praydog/REFramework", "asset": "RE3.zip"},
        "reframework_branches": {
            "dx11_non-rt": {"repo": "praydog/REFramework", "asset": "RE3_TDB67.zip"}},
        "files": {
            r"reframework\autorun\dualsense_companion_re3.lua":
                f"{RAW}/mods/re3/reframework/autorun/dualsense_companion_re3.lua",
            r"natives\stm\escape\ui\ui0000\tex\ui0000_iam.tex.34.stm":
                f"{RAW}/mods/re3/icons/natives/stm/escape/ui/ui0000/tex/ui0000_iam.tex.34.stm",
        },
        "loose_files": True,
        "while_app_runs": [r"natives\stm\escape\ui\ui0000\tex\ui0000_iam.tex.34.stm"],
        "icons_skip_branches": ["dx11_non-rt"],   # its icon textures differ
        "conflicts": [],
    },
    {
        "exe": "re8.exe",
        "name": "Resident Evil Village",
        "installed": [r"reframework\autorun\dualsense_companion_re8.lua"],
        "data": r"reframework\data\DualSenseCompanion",
        "guide": f"{REPO}/tree/main/mods/re8#readme",
        "features": "adaptive triggers and PlayStation button prompts",
        "about": (
            "Resident Evil Village on PC has no adaptive triggers and only shows Xbox buttons. "
            "This DualSense mod adds adaptive triggers and PlayStation button prompts, in the "
            "main game, Shadows of Rose and The Mercenaries.\n\n"
            "•  A small script runs inside the game through REFramework, a widely used mod "
            "loader for Capcom's games. Several times a second it checks which weapon you're "
            "holding, whether its magazine is empty and how much health you have.\n\n"
            "•  Each kind of weapon gets its own trigger feel: handguns, shotguns, rifles, "
            "magnums, the V61 Custom, the grenade launcher, the knife and throwables, tuned "
            "side by side with the PS5 version.\n\n"
            "•  " + LIGHTBAR + "\n\n"
            "•  The script writes that feel to a small file in the game folder. DualSense "
            "Companion follows the file and plays it on your controller's triggers.\n\n"
            "•  Guns have a trigger wall that gives way, like a real trigger, and the app "
            "only lets the game see the trigger once it's past the wall, so the shot fires at "
            "the break. An empty gun gets a light click instead. In menus and cutscenes the "
            "triggers go back to normal.\n\n"
            "•  The game's button prompts show PlayStation buttons (✕ ○ □ △, L1, R2, "
            "Options…) instead of Xbox ones, while DualSense Companion is running (the game "
            "picks its icons when it starts; without the app it shows its own Xbox ones).\n\n"
            "Keep Steam Input on for the game: Resident Evil Village only reads Xbox-style "
            "controllers, and Steam Input turns the DualSense into one for it.\n\n"
            "The mod doesn't change the game's own files. Uninstall removes it again."),
        "xinput_only": True,
        "steam_appid": 1196590,
        # stable works with Village's current build: checked 2026-11-02
        "reframework": {"repo": "praydog/REFramework", "asset": "RE8.zip"},
        "files": {
            r"reframework\autorun\dualsense_companion_re8.lua":
                f"{RAW}/mods/re8/reframework/autorun/dualsense_companion_re8.lua",
            r"natives\stm\gui\ui0000\tex\ui0000_iam.tex.30.x64":
                f"{RAW}/mods/re8/icons/natives/stm/gui/ui0000/tex/ui0000_iam.tex.30.x64",
        },
        "loose_files": True,
        "while_app_runs": [r"natives\stm\gui\ui0000\tex\ui0000_iam.tex.30.x64"],
        "conflicts": [],
    },
]


# Before the rename the mods were DualSense Bridge's: reframework\autorun\dualsense_bridge_<key>.lua
# and a reframework\data\DualSenseBridge folder. mod_installer.migrate moves them over.
LEGACY_DATA = r"reframework\data\DualSenseBridge"
for _game in GAMES:
    _game["legacy_files"] = {
        rel.replace("dualsense_companion_", "dualsense_bridge_"): rel
        for rel in _game["files"] if "dualsense_companion_" in rel}
    _game["legacy_data"] = LEGACY_DATA
    _game["installed"] = _game["installed"] + list(_game["legacy_files"])
del _game


def suggestion(exe_path):
    """The game entry to suggest for a running exe, or None (unknown game, or mod installed)."""
    if not exe_path:
        return None
    folder, name = os.path.split(exe_path)
    for game in GAMES:
        if name.lower() == game["exe"]:
            if any(os.path.exists(os.path.join(folder, p)) for p in game["installed"]):
                return None
            return game
    return None
