"""Games with a mod that adds adaptive triggers through DualSense Bridge.

When one of these games is running and its mod isn't installed, the tray offers the mod's
setup guide. A new game is one more entry here.
"""
import os

REPO = "https://github.com/vingt-2/dualsense-bridge"

GAMES = [
    {
        "exe": "re4.exe",
        "name": "Resident Evil 4",
        # any of these next to the exe means the mod (or one like it) is already installed
        "installed": [r"reframework\autorun\dualsense_bridge_re4.lua"],
        "guide": f"{REPO}/tree/main/mods/re4-remake#readme",
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
