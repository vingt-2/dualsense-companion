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
    backups = os.listdir(os.path.join(folder, "DualSenseBridge-backup"))
    assert os.path.exists(os.path.join(folder, "DualSenseBridge-backup", backups[0], "reframework",
                                       "autorun", "DualsenseX", "core.lua"))
    script = os.path.join(folder, "reframework", "autorun", "dualsense_bridge_re4.lua")
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
    data = os.path.join(fresh, "reframework", "data", "DualSenseBridge")
    open(os.path.join(data, "re4_triggers.json"), "w").close()        # what the script writes
    os.makedirs(os.path.join(fresh, "DualSenseBridge-backup", "x"))
    open(os.path.join(fresh, "DualSenseBridge-backup", "x", "old.lua"), "w").close()
    done = mod_installer.uninstall(GAME, fresh, log=lambda s: None)
    assert done == ["removed the mod",
                    "removed REFramework (DualSense Bridge had installed it)"], done
    assert sorted(os.listdir(fresh)) == ["DualSenseBridge-backup"], os.listdir(fresh)

    # ...but REFramework stays when other scripts use it
    fresh = tempfile.mkdtemp()
    mod_installer.install(GAME, fresh, get=get, reframework=reframework, log=lambda s: None)
    open(os.path.join(fresh, "reframework", "autorun", "someone_elses.lua"), "w").close()
    done = mod_installer.uninstall(GAME, fresh, log=lambda s: None)
    assert done[1] == "kept REFramework: other mods use it", done
    assert os.path.exists(os.path.join(fresh, "dinput8.dll"))
    assert not mod_installer.is_installed(GAME, fresh)

    # ...and it's never removed when DualSense Bridge didn't install it
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

    # Steam: the app manifest says where the game is
    lib = tempfile.mkdtemp()
    os.makedirs(os.path.join(lib, "steamapps", "common", "RE4 Folder"))
    with open(os.path.join(lib, "steamapps", "appmanifest_2050650.acf"), "w") as f:
        f.write('"AppState"\n{\n\t"appid"\t\t"2050650"\n\t"installdir"\t\t"RE4 Folder"\n}\n')
    assert mod_installer.steam_game_folder(2050650, [tempfile.mkdtemp(), lib]) == \
        os.path.join(lib, "steamapps", "common", "RE4 Folder")
    assert mod_installer.steam_game_folder(1, [lib]) is None
    print("OK: game-mod installer: install, update, uninstall, conflicting mod, Steam lookup all pass")


if __name__ == "__main__":
    main()
