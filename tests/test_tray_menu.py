"""Builds the tray app and walks its whole menu (texts, states, submenus) with stand-in parts,
without showing an icon:  python tests\\test_tray_menu.py"""
import os
import sys
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
    assert "Adaptive triggers not installed visible=True" in menu, menu
    assert "Install adaptive triggers… visible=True" in menu, menu
    assert "Update the mod… visible=False" in menu, menu
    assert "Uninstall… visible=False" in menu, menu
    os.makedirs(os.path.join(folder, "reframework", "autorun"))
    open(os.path.join(folder, "reframework", "autorun", "dualsense_bridge_re4.lua"), "w").close()
    menu = "\n".join(walk(app.icon.menu, app.icon))
    assert "Adaptive triggers installed visible=True" in menu, menu
    assert "Install adaptive triggers… visible=False" in menu, menu
    assert "Update the mod… visible=True" in menu, menu
    assert "Uninstall… visible=True" in menu, menu
    # every game in the catalogue has an explanation
    import game_mods
    assert all(len(g.get("about", "")) > 200 for g in game_mods.GAMES)
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
    print("OK: tray menu builds, the Game mods submenu follows the game's state, reminders until dismissed")


if __name__ == "__main__":
    main()
