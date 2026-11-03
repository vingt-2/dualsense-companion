"""Self-test of the game-mod installer, offline (no downloads):  python tests\\test_mod_installer.py"""
import io
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import game_mods
import mod_installer

GAME = game_mods.GAMES[0]


def fake_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("dinput8.dll", b"MZ fake loader")
        z.writestr("openvr_api.dll", b"not wanted")
    return buf.getvalue()


def main():
    downloads = []

    def get(url):
        downloads.append(url)
        return fake_zip() if url.endswith(".zip") else b"-- the trigger script"

    def reframework(asset, repo="praydog/REFramework"):
        assert asset == "RE4.zip" and repo == "praydog/REFramework", (asset, repo)
        return "v9", "https://example.invalid/RE4.zip"

    # a fresh game with another trigger mod: loader added, old mod set aside, script added
    folder = tempfile.mkdtemp()
    old = os.path.join(folder, "reframework", "autorun", "DualsenseX")
    os.makedirs(old)
    open(os.path.join(old, "core.lua"), "w").close()
    done = mod_installer.install(GAME, folder, get=get, reframework=reframework, log=lambda s: None)
    assert done[0] == "installed REFramework v9", done
    assert open(os.path.join(folder, "dinput8.dll"), "rb").read() == b"MZ fake loader"
    assert not os.path.exists(os.path.join(folder, "openvr_api.dll"))
    config = open(os.path.join(folder, "re2_fw_config.txt")).read()      # menu starts closed
    assert "REFrameworkConfig_RememberMenuState=true" in config
    assert "REFrameworkConfig_MenuOpen=false" in config
    assert not os.path.exists(old)
    backups = os.listdir(os.path.join(folder, "DualSenseCompanion-backup"))
    assert os.path.exists(os.path.join(folder, "DualSenseCompanion-backup", backups[0], "reframework",
                                       "autorun", "DualsenseX", "core.lua"))
    script = os.path.join(folder, "reframework", "autorun", "dualsense_companion_re4.lua")
    assert open(script, "rb").read() == b"-- the trigger script"
    assert mod_installer.is_installed(GAME, folder)

    # REFramework already there (maybe another mod's dinput8.dll): left alone
    downloads.clear()
    open(os.path.join(folder, "dinput8.dll"), "wb").write(b"someone else's")
    done = mod_installer.install(GAME, folder, get=get, reframework=reframework, log=lambda s: None)
    assert done[0] == "REFramework already installed" and not any(u.endswith(".zip") for u in downloads)
    assert open(os.path.join(folder, "dinput8.dll"), "rb").read() == b"someone else's"

    # an existing REFramework setup gets its window hidden too, and keeps its other settings
    with open(os.path.join(folder, "re2_fw_config.txt"), "w") as f:
        f.write("REFrameworkConfig_RememberMenuState=false\nREFrameworkConfig_MenuOpen=true\nOther=1\n")
    mod_installer.install(GAME, folder, get=get, reframework=reframework, log=lambda s: None)
    assert open(os.path.join(folder, "re2_fw_config.txt")).read().splitlines() == [
        "REFrameworkConfig_RememberMenuState=true", "REFrameworkConfig_MenuOpen=false", "Other=1"]
    # set_config keeps other lines, replaces the keys it sets and appends missing ones
    with open(os.path.join(folder, "re2_fw_config.txt"), "w") as f:
        f.write("REFrameworkConfig_RememberMenuState=false\nOther=1\n")
    mod_installer.set_config(os.path.join(folder, "re2_fw_config.txt"), mod_installer.QUIET_MENU)
    lines = open(os.path.join(folder, "re2_fw_config.txt")).read().splitlines()
    assert lines == ["REFrameworkConfig_RememberMenuState=true", "Other=1",
                     "REFrameworkConfig_MenuOpen=false"], lines

    # an empty download is an error, not an empty script
    try:
        mod_installer.install(GAME, folder, get=lambda url: b"", reframework=reframework,
                              log=lambda s: None)
        raise AssertionError("empty download accepted")
    except RuntimeError:
        pass

    # uninstall after we installed REFramework: the mod and REFramework go, backups stay
    fresh = tempfile.mkdtemp()
    mod_installer.install(GAME, fresh, get=get, reframework=reframework, log=lambda s: None)
    data = os.path.join(fresh, "reframework", "data", "DualSenseCompanion")
    open(os.path.join(data, "re4_triggers.json"), "w").close()        # what the script writes
    os.makedirs(os.path.join(fresh, "DualSenseCompanion-backup", "x"))
    open(os.path.join(fresh, "DualSenseCompanion-backup", "x", "old.lua"), "w").close()
    done = mod_installer.uninstall(GAME, fresh, log=lambda s: None)
    assert done == ["removed the mod",
                    "removed REFramework (DualSense Companion had installed it)"], done
    assert sorted(os.listdir(fresh)) == ["DualSenseCompanion-backup"], os.listdir(fresh)

    # ...but REFramework stays when other scripts use it
    fresh = tempfile.mkdtemp()
    mod_installer.install(GAME, fresh, get=get, reframework=reframework, log=lambda s: None)
    open(os.path.join(fresh, "reframework", "autorun", "someone_elses.lua"), "w").close()
    done = mod_installer.uninstall(GAME, fresh, log=lambda s: None)
    assert done[1] == "kept REFramework: other mods use it", done
    assert os.path.exists(os.path.join(fresh, "dinput8.dll"))
    assert not mod_installer.is_installed(GAME, fresh)

    # ...and it's never removed when DualSense Companion didn't install it
    fresh = tempfile.mkdtemp()
    open(os.path.join(fresh, "dinput8.dll"), "wb").write(b"theirs")
    mod_installer.install(GAME, fresh, get=get, reframework=reframework, log=lambda s: None)
    done = mod_installer.uninstall(GAME, fresh, log=lambda s: None)
    assert done == ["removed the mod"], done
    assert open(os.path.join(fresh, "dinput8.dll"), "rb").read() == b"theirs"

    # the REFramework build follows the installed Steam branch
    lib = tempfile.mkdtemp()
    game_dir = os.path.join(lib, "steamapps", "common", "Game")
    os.makedirs(game_dir)
    entry = {"steam_appid": 418370,
             "reframework": {"repo": "praydog/REFramework-nightly", "asset": "REFramework.zip"},
             "reframework_branches": {"dx11_non-rt": {"repo": "praydog/REFramework",
                                                      "asset": "RE7_TDB49.zip"}}}
    manifest = os.path.join(lib, "steamapps", "appmanifest_418370.acf")
    def write_manifest(beta):
        config = f'\t\t"BetaKey"\t\t"{beta}"\n' if beta else ""
        with open(manifest, "w") as f:
            f.write('"AppState"\n{\n\t"appid"\t\t"418370"\n\t"UserConfig"\n\t{\n'
                    '\t\t"language"\t\t"english"\n' + config + '\t}\n\t"MountedConfig"\n\t{\n'
                    '\t\t"language"\t\t"english"\n' + config + '\t}\n}\n')
    write_manifest(None)
    assert mod_installer.reframework_source(entry, game_dir) == \
        ("praydog/REFramework-nightly", "REFramework.zip", None)
    write_manifest("dx11_non-rt")
    assert mod_installer.reframework_source(entry, game_dir) == \
        ("praydog/REFramework", "RE7_TDB49.zip", "dx11_non-rt")
    write_manifest("some_other_beta")             # unknown branch: the game's default
    assert mod_installer.reframework_source(entry, game_dir)[1] == "REFramework.zip"
    # the real RE7 on this kind of PC (no BetaKey) and a folder outside Steam
    assert mod_installer.steam_branch(tempfile.mkdtemp(), 418370) is None

    # a mod with loose files (RE7's PlayStation icons): the loader is turned on, and uninstall
    # removes the files and the folders they leave empty, nothing else
    re7 = next(g for g in game_mods.GAMES if g["exe"] == "re7.exe")
    def reframework7(asset, repo="praydog/REFramework"):
        return "v9", "https://example.invalid/RE7.zip"
    def get7(url):
        return fake_zip() if url.endswith(".zip") else b"file:" + url.encode()
    fresh = tempfile.mkdtemp()
    os.makedirs(os.path.join(fresh, "natives", "stm", "other"))
    open(os.path.join(fresh, "natives", "stm", "other", "keep.tex"), "w").close()
    mod_installer.install(re7, fresh, get=get7, reframework=reframework7, log=lambda s: None)
    icon = os.path.join(fresh, "natives", "stm", "ui", "ui0000", "tex", "ui0010_iam.tex.35.x64")
    assert open(icon, "rb").read().endswith(b"/mods/re7/icons/natives/stm/ui/ui0000/tex/ui0010_iam.tex.35.x64")
    config = open(os.path.join(fresh, "re2_fw_config.txt")).read()
    assert "LooseFileLoader_Enabled=true" in config, config
    # the icons are only in place while the app runs: out at quit, back at the next start
    assert mod_installer.deactivate(re7, fresh) == 2 and not os.path.exists(icon)
    assert not os.path.exists(os.path.join(fresh, "natives", "stm", "ui"))   # no empty folders
    assert mod_installer.activate(re7, fresh) == 2 and os.path.exists(icon)
    # files the mod didn't stash (e.g. icons copied by hand) are never removed
    hand = tempfile.mkdtemp()
    hand_icon = os.path.join(hand, *re7["while_app_runs"][0].split("\\"))
    os.makedirs(os.path.dirname(hand_icon))
    open(hand_icon, "wb").write(b"by hand")
    assert mod_installer.deactivate(re7, hand) == 0 and os.path.exists(hand_icon)
    # an install from 1.7.1 (icons in place, nothing stashed) is taken over at the next start
    old = tempfile.mkdtemp()
    for rel in list(re7["files"]):
        p = os.path.join(old, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(b"1.7.1 copy")
    assert mod_installer.activate(re7, old) == 2
    assert mod_installer.deactivate(re7, old) == 2
    assert not os.path.exists(os.path.join(old, re7["while_app_runs"][0]))
    mod_installer.uninstall(re7, fresh, log=lambda s: None)
    assert not os.path.exists(os.path.join(fresh, "natives", "stm", "ui"))
    assert os.path.exists(os.path.join(fresh, "natives", "stm", "other", "keep.tex"))

    # a failed download (e.g. a 404 on the second file) leaves the game folder untouched
    fresh = tempfile.mkdtemp()
    def get_failing(url):
        if "ui0010" in url:
            raise OSError("HTTP Error 404: Not Found")
        return get7(url)
    try:
        mod_installer.install(re7, fresh, get=get_failing, reframework=reframework7, log=lambda s: None)
        raise AssertionError("failed download accepted")
    except OSError:
        pass
    assert os.listdir(fresh) == [], os.listdir(fresh)

    # the old dx11_non-rt build has other icon textures: triggers only, no icons, no loader
    lib = tempfile.mkdtemp()
    old_build = os.path.join(lib, "steamapps", "common", "RE7 Folder")
    os.makedirs(old_build)
    with open(os.path.join(lib, "steamapps", "appmanifest_418370.acf"), "w") as f:
        f.write('"AppState"\n{\n\t"appid"\t\t"418370"\n\t"MountedConfig"\n\t{\n'
                '\t\t"BetaKey"\t\t"dx11_non-rt"\n\t}\n}\n')
    def reframework_old(asset, repo="praydog/REFramework"):
        assert asset == "RE7_TDB49.zip", asset
        return "v9", "https://example.invalid/RE7_TDB49.zip"
    mod_installer.install(re7, old_build, get=get7, reframework=reframework_old, log=lambda s: None)
    assert mod_installer.is_installed(re7, old_build)
    assert not os.path.exists(os.path.join(old_build, "natives"))
    assert mod_installer.activate(re7, old_build) == 0
    assert "LooseFileLoader" not in open(os.path.join(old_build, "re2_fw_config.txt")).read()

    rename_from_bridge(get, reframework)

    # Steam: the app manifest says where the game is
    lib = tempfile.mkdtemp()
    os.makedirs(os.path.join(lib, "steamapps", "common", "RE4 Folder"))
    with open(os.path.join(lib, "steamapps", "appmanifest_2050650.acf"), "w") as f:
        f.write('"AppState"\n{\n\t"appid"\t\t"2050650"\n\t"installdir"\t\t"RE4 Folder"\n}\n')
    assert mod_installer.steam_game_folder(2050650, [tempfile.mkdtemp(), lib]) == \
        os.path.join(lib, "steamapps", "common", "RE4 Folder")
    assert mod_installer.steam_game_folder(1, [lib]) is None
    print("OK: game-mod installer: install, update, uninstall, conflicting mod, Steam lookup, "
          "moving DualSense Bridge installs over all pass")


def rename_from_bridge(get, reframework):
    """A mod installed by DualSense Bridge (before the rename) moves over to the new names."""
    re7 = next(g for g in game_mods.GAMES if g["exe"] == "re7.exe")
    folder = tempfile.mkdtemp()
    old_script = os.path.join(folder, "reframework", "autorun", "dualsense_bridge_re7.lua")
    old_data = os.path.join(folder, "reframework", "data", "DualSenseBridge")
    os.makedirs(os.path.dirname(old_script))
    os.makedirs(os.path.join(old_data, "while-bridge-runs"))
    open(old_script, "wb").write(b'local OUT_FILE = "DualSenseBridge/re7_triggers.json"\n')
    open(os.path.join(old_data, "re7_config.json"), "w").write('{"lightbar": false}')
    open(os.path.join(old_data, "installed-reframework.txt"), "w").write("v8\n")
    open(os.path.join(old_data, "while-bridge-runs", "icon.tex"), "w").write("icons")
    assert mod_installer.is_installed(re7, folder)          # not offered again meanwhile
    assert not mod_installer.other_reframework_mods(re7, folder)   # it's ours, not another mod
    done = mod_installer.migrate(re7, folder, log=lambda s: None)
    assert done == ["moved its data folder", "renamed dualsense_bridge_re7.lua"], done
    new_script = os.path.join(folder, "reframework", "autorun", "dualsense_companion_re7.lua")
    new_data = os.path.join(folder, "reframework", "data", "DualSenseCompanion")
    assert not os.path.exists(old_script) and not os.path.exists(old_data)
    # the old script keeps working as it was, writing where the app now looks
    assert open(new_script, "rb").read() == b'local OUT_FILE = "DualSenseCompanion/re7_triggers.json"\n'
    assert open(os.path.join(new_data, "re7_config.json")).read() == '{"lightbar": false}'
    assert mod_installer.reframework_is_ours(re7, folder)          # the marker came along
    assert os.path.exists(os.path.join(new_data, "while-bridge-runs", "icon.tex"))
    assert mod_installer.migrate(re7, folder, log=lambda s: None) == []   # once
    # a game still writing to the old folder (it was running): merged in, new files kept
    os.makedirs(old_data)
    open(os.path.join(old_data, "re7_config.json"), "w").write("stale")
    open(os.path.join(old_data, "re7_status.txt"), "w").write("status")
    assert mod_installer.migrate(re7, folder, log=lambda s: None) == ["moved its data folder"]
    assert open(os.path.join(new_data, "re7_config.json")).read() == '{"lightbar": false}'
    assert os.path.exists(os.path.join(new_data, "re7_status.txt"))
    assert not os.path.exists(old_data)
    # updating over an old install leaves one script, not two
    open(os.path.join(folder, "dinput8.dll"), "wb").write(b"MZ")   # REFramework is there
    open(old_script, "wb").write(b"-- old")
    mod_installer.install(re7, folder, get=get, reframework=reframework, log=lambda s: None)
    assert not os.path.exists(old_script) and open(new_script, "rb").read() == b"-- the trigger script"
    # and uninstalling one never updated takes the old names too
    other = tempfile.mkdtemp()
    os.makedirs(os.path.join(other, "reframework", "autorun"))
    open(os.path.join(other, "reframework", "autorun", "dualsense_bridge_re7.lua"), "w").close()
    os.makedirs(os.path.join(other, "reframework", "data", "DualSenseBridge"))
    mod_installer.uninstall(re7, other, log=lambda s: None)
    assert not mod_installer.is_installed(re7, other)
    assert not os.path.exists(os.path.join(other, "reframework", "data", "DualSenseBridge"))
    assert not os.path.exists(os.path.join(other, "reframework", "data", "DualSenseCompanion"))


if __name__ == "__main__":
    main()
