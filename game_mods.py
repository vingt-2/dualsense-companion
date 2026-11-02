"""Games with a mod that adds adaptive triggers through DualSense Bridge.

When one of these games is running and its mod isn't installed, the tray offers the mod's
setup guide. A new game is one more entry here.
"""
import os

REPO = "https://github.com/vingt-2/dualsense-bridge"
RAW = "https://raw.githubusercontent.com/vingt-2/dualsense-bridge/main"

GAMES = [
    {
        "exe": "re4.exe",
        "name": "Resident Evil 4",
        # any of these next to the exe means the mod (or one like it) is already installed
        "installed": [r"reframework\autorun\dualsense_bridge_re4.lua"],
        "data": r"reframework\data\DualSenseBridge",      # the mod's own files (removed on uninstall)
        "guide": f"{REPO}/tree/main/mods/re4-remake#readme",
        # shown by the tray's "How it works…"
        "about": (
            "Resident Evil 4 on PC has no adaptive triggers. This mod adds them.\n\n"
            "•  A small script runs inside the game through REFramework, a widely used mod "
            "loader for Capcom's games. Several times a second it checks which weapon you're "
            "holding and how many rounds are loaded.\n\n"
            "•  Each kind of weapon gets its own trigger feel: pistols, shotguns, rifles, "
            "magnums, SMGs, the bolt thrower, launchers, knives and grenades. The lightbar "
            "takes the weapon's colour.\n\n"
            "•  The script writes that feel to a small file in the game folder. DualSense "
            "Bridge follows the file and plays it on your controller's triggers.\n\n"
            "•  Guns have a trigger wall that gives way, like a real trigger, and the bridge "
            "only lets the game see the trigger once it's past the wall, so the shot fires at "
            "the break. An empty gun gets a light click instead. In menus and cutscenes the "
            "triggers go back to normal.\n\n"
            "The mod only reads the game, it doesn't change it. To remove it, delete "
            "reframework\\autorun\\dualsense_bridge_re4.lua in the game folder."),
        # for the automatic install (mod_installer.py)
        "steam_appid": 2050650,
        "reframework_asset": "RE4.zip",
        "files": {r"reframework\autorun\dualsense_bridge_re4.lua":
                  f"{RAW}/mods/re4-remake/reframework/autorun/dualsense_bridge_re4.lua"},
        # other trigger mods for this game, moved aside so they don't fight over the triggers
        "conflicts": [r"reframework\autorun\DualsenseX.lua", r"reframework\autorun\DualsenseX",
                      r"reframework\data\DualSenseX"],
    },
]


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
