"""Builds the tray app and walks its whole menu (texts, states, submenus) with stand-in parts,
without showing an icon:  python tests\\test_tray_menu.py"""
import os
import sys
import time
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()   # settings of its own
import tray_app
from dualsense_usb import WiredDualSense
from link_stats import LinkStats


class FakeBluetooth:
    on_input = on_mic = on_buttons = on_state = before_open = None
    headset = False
    speaker_format = 0x39
    link = LinkStats()
    dev = path = None
    haptics_depth = 0x28

    def write_usb_output(self, report): pass
    def write_media(self, block, frame=None): pass
    def set_mic(self, on): pass
    def get_feature(self, rid, size): return None


def walk(menu, item_arg, depth=0, out=None):
    out = [] if out is None else out
    for item in menu.items:
        if item is tray_app.pystray.Menu.SEPARATOR:
            continue
        text = item.text
        out.append(("  " * depth) + f"{text} visible={item.visible} enabled={item.enabled} "
                   f"checked={item.checked}")
        if item.submenu:
            walk(item.submenu, item_arg, depth + 1, out)
    return out


def main():
    os.makedirs(tray_app.DATA_DIR, exist_ok=True)       # as main() does
    bt = FakeBluetooth()
    server = SimpleNamespace(device=WiredDualSense(bt))
    app = tray_app.TrayApp(server, bt)
    lines = walk(app.icon.menu, app.icon)
    menu = "\n".join(lines)
    assert "Game mods" in menu and "Adaptive triggers and lights from game mods" in menu, menu
    # layout: Game mods leads the actions, audio options are grouped, Quit is last
    top = [line for line in lines if not line.startswith(" ")]
    names = [line.split(" visible=")[0] for line in top]
    assert names.index("Game mods") < names.index("Shortcuts…") < names.index("Audio"), names
    assert names[-1] == "Quit", names
    # the Haptics delay option is kept in code but hidden (tray_app.SHOW_HAPTICS_DELAY)
    assert "Haptics delay visible=False" in menu, menu
    assert any("Keep my default speaker and mic" in l and l.startswith("  ") for l in lines), lines
    # each game has its own submenu: state, install or update, how it works, guide
    assert "Resident Evil 4 visible=True" in menu, menu
    assert "Not found on this PC visible=True" in menu, menu
    assert "How it works… visible=True" in menu and "Setup guide… visible=True" in menu, menu
    folder = tempfile.mkdtemp()
    app.game_folders["re4.exe"] = folder
    menu = "\n".join(walk(app.icon.menu, app.icon))
    assert "DualSense mod not installed visible=True" in menu, menu
    assert "Install the DualSense mod… visible=True" in menu, menu
    assert "Update the mod… visible=False" in menu, menu
    assert "Uninstall… visible=False" in menu, menu
    os.makedirs(os.path.join(folder, "reframework", "autorun"))
    open(os.path.join(folder, "reframework", "autorun", "dualsense_companion_re4.lua"), "w").close()
    menu = "\n".join(walk(app.icon.menu, app.icon))
    assert "DualSense mod installed visible=True" in menu, menu
    assert "Install the DualSense mod… visible=False" in menu, menu
    assert "Update the mod… visible=True" in menu, menu
    assert "Uninstall… visible=True" in menu, menu
    # every game in the catalogue has an explanation
    import game_mods
    assert all(len(g.get("about", "")) > 200 and g.get("features") for g in game_mods.GAMES)
    # reminders: each launch of the game without its mod notifies, until "Don't remind me"
    notes = []
    app.icon.notify = lambda text, title=None: notes.append(text)
    bare = tempfile.mkdtemp()
    exe = os.path.join(bare, "re4.exe")
    app._check_game(1, exe)
    app._check_game(2, exe)
    assert len(notes) == 2 and app.mod_tip["exe"] == "re4.exe", notes
    menu = "\n".join(walk(app.icon.menu, app.icon))
    assert "Don't remind me about Resident Evil 4 visible=True" in menu, menu
    app._dismiss_mod_tip()
    app._check_game(3, exe)
    assert len(notes) == 2 and app.mod_tip is None
    assert tray_app._load_settings()["mod_tips_dismissed"] == ["re4.exe"]
    # a game that sees no controller for a while gets one notification per launch
    notes.clear()
    app.NO_CONTROLLER_GRACE = 0.1
    app._controller_seen("re7.exe (payload file)", "re7.exe", False)
    app._controller_seen("re7.exe (payload file)", "re7.exe", False)
    time.sleep(0.3)
    assert len(notes) == 1 and "Steam Input" in notes[0], notes
    app._controller_seen("re7.exe (payload file)", "re7.exe", True)    # seen: all clear
    app._controller_seen("re7.exe (payload file)", "re7.exe", False)
    app._controller_seen("re7.exe (payload file)", "re7.exe", True)    # in time: no notice
    time.sleep(0.3)
    assert len(notes) == 1, notes

    # quitting takes the icons out; starting (finding games) puts them back
    import mod_installer
    re7 = next(g for g in game_mods.GAMES if g["exe"] == "re7.exe")
    game = tempfile.mkdtemp()
    stash = os.path.join(game, re7["data"], mod_installer.STASH)
    for rel in re7["while_app_runs"]:
        p = os.path.join(stash, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(b"icons")
    app.game_folders = {"re7.exe": game}
    app._set_mod_files(active=True)
    placed = os.path.join(game, re7["while_app_runs"][0])
    assert os.path.exists(placed)
    app._set_mod_files(active=False)
    assert not os.path.exists(placed)
    rename_from_bridge()
    print("OK: tray menu builds, the Game mods submenu follows the game's state, reminders until dismissed, icons only while running, settings moved over from DualSense Bridge")


def rename_from_bridge():
    """DualSense Bridge's settings folder moves over to DualSense Companion's, once."""
    base = tempfile.mkdtemp()
    old, new = os.path.join(base, "DualSenseBridge"), os.path.join(base, "DualSenseCompanion")
    os.makedirs(old)
    open(os.path.join(old, "settings.json"), "w").write('{"controller_ids": ["x"]}')
    open(os.path.join(old, "bridge.log"), "w").write("old log")
    assert tray_app.migrate_data_dir(old, new)
    assert open(os.path.join(new, "settings.json")).read() == '{"controller_ids": ["x"]}'
    assert not os.path.exists(old)
    assert not tray_app.migrate_data_dir(old, new)            # nothing left to move
    # new settings already there (e.g. a second start): the old ones never overwrite them
    os.makedirs(old)
    open(os.path.join(old, "settings.json"), "w").write("old")
    assert not tray_app.migrate_data_dir(old, new)
    assert open(os.path.join(new, "settings.json")).read() == '{"controller_ids": ["x"]}'


if __name__ == "__main__":
    main()
