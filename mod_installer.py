"""Installs a game's adaptive-trigger mod (see game_mods.py): REFramework from its GitHub
releases if the game doesn't have it yet, then our script from this repository.

Nothing is deleted: a conflicting mod is moved into DualSenseBridge-backup in the game folder.
"""
import io
import json
import os
import re
import shutil
import time
import urllib.request
import winreg
import zipfile

UA = {"User-Agent": "DualSenseBridge"}
TIMEOUT = 30


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=TIMEOUT) as r:
        return r.read()


# -- finding the game ---------------------------------------------------------------------
def steam_libraries():
    """Steam library folders, from the registry and libraryfolders.vdf."""
    roots = []
    for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
        try:
            with winreg.OpenKey(hive, key) as k:
                for name in ("SteamPath", "InstallPath"):
                    try:
                        roots.append(os.path.normpath(winreg.QueryValueEx(k, name)[0]))
                    except OSError:
                        pass
        except OSError:
            pass
    libraries = []
    for root in dict.fromkeys(roots):
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
        try:
            text = open(vdf, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        libraries.append(root)
        libraries += [os.path.normpath(p.replace("\\\\", "\\"))
                      for p in re.findall(r'"path"\s+"([^"]+)"', text)]
    return list({os.path.normcase(p): p for p in reversed(libraries)}.values())[::-1]


def steam_game_folder(appid, libraries=None):
    """The install folder of a Steam app, or None."""
    for lib in libraries if libraries is not None else steam_libraries():
        manifest = os.path.join(lib, "steamapps", f"appmanifest_{appid}.acf")
        try:
            text = open(manifest, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        m = re.search(r'"installdir"\s+"([^"]+)"', text)
        if m:
            folder = os.path.join(lib, "steamapps", "common", m.group(1))
            if os.path.isdir(folder):
                return folder
    return None


def steam_branch(folder, appid):
    """The Steam branch (beta) installed in a Steam game folder, or None for the default one.
    Steam keeps it in the app manifest next to steamapps\\common: "BetaKey" under
    MountedConfig (what's on disk) or UserConfig (what's selected)."""
    steamapps = os.path.dirname(os.path.dirname(os.path.normpath(folder)))
    try:
        text = open(os.path.join(steamapps, f"appmanifest_{appid}.acf"), encoding="utf-8",
                    errors="replace").read()
    except OSError:
        return None
    for section in ("MountedConfig", "UserConfig"):
        m = re.search(r'"%s"\s*\{([^}]*)\}' % section, text)
        key = m and re.search(r'"BetaKey"\s+"([^"]*)"', m.group(1))
        if key and key.group(1) and key.group(1).lower() != "public":
            return key.group(1)
    return None


def reframework_source(game, folder):
    """(repo, zip) of the REFramework build for the installed version of the game: the
    game's "reframework" entry, or the one for its Steam branch (e.g. the old non-RT builds
    of RE2/3/7 need their own zips)."""
    branch = steam_branch(folder, game.get("steam_appid")) if game.get("steam_appid") else None
    source = game.get("reframework_branches", {}).get(branch) if branch else None
    source = source or game["reframework"]
    return source["repo"], source["asset"], branch


def is_installed(game, folder):
    return any(os.path.exists(os.path.join(folder, p)) for p in game["installed"])


# -- installing ---------------------------------------------------------------------------
def latest_reframework(asset, repo="praydog/REFramework"):
    """(tag, download URL) of the game's zip in REFramework's latest release."""
    release = json.loads(_get(f"https://api.github.com/repos/{repo}/releases/latest"))
    for a in release.get("assets", []):
        if a["name"].lower() == asset.lower():
            return release["tag_name"], a["browser_download_url"]
    raise RuntimeError(f"REFramework's latest release has no {asset}")


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


# REFramework opens its menu at every start unless told to remember it closed. People who get
# REFramework from us just want the mod, so a fresh install starts with the menu closed
# (Insert still opens it). Existing REFramework setups keep their own settings.
REFRAMEWORK_CONFIG = "re2_fw_config.txt"     # its name in every RE Engine game
QUIET_MENU = {"REFrameworkConfig_RememberMenuState": "true", "REFrameworkConfig_MenuOpen": "false"}


def set_config(path, values):
    """Set key=value lines in an REFramework config file, keeping every other line."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []
    todo = dict(values)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in todo:
            lines[i] = f"{key}={todo.pop(key)}"
    lines += [f"{k}={v}" for k, v in todo.items()]
    _write(path, ("\n".join(lines) + "\n").encode("utf-8"))


LOOSE_FILES = {"LooseFileLoader_Enabled": "true"}
REFRAMEWORK_MARKER = "installed-reframework.txt"   # in the mod's data folder
# what REFramework itself leaves next to the exe (removed only if we installed it)
REFRAMEWORK_FILES = ["dinput8.dll", REFRAMEWORK_CONFIG, "re2_framework_log.txt",
                     "reframework_revision.txt", "reframework_accessed_files.txt",
                     "reframework_loose_files.txt"]


def install(game, folder, get=_get, reframework=latest_reframework, log=print):
    """Install the game's mod into folder. Returns a list of what was done."""
    done = []
    loader = os.path.join(folder, "dinput8.dll")
    if not os.path.exists(loader):
        repo, asset, branch = reframework_source(game, folder)
        tag, url = reframework(asset, repo)
        log(f"[mods] downloading REFramework {tag} ({repo} {asset}"
            f"{', for the ' + branch + ' build' if branch else ''})")
        with zipfile.ZipFile(io.BytesIO(get(url))) as z:
            name = next((n for n in z.namelist() if n.lower().endswith("dinput8.dll")), None)
            if not name:
                raise RuntimeError(f"{asset} has no dinput8.dll")
            _write(loader, z.read(name))
        # remember that REFramework came from us, so uninstalling may take it away again
        _write(os.path.join(folder, game["data"], REFRAMEWORK_MARKER), f"{tag}\n".encode())
        done.append(f"installed REFramework {tag}")
    else:
        done.append("REFramework already installed")

    moved = []
    backup = os.path.join(folder, "DualSenseBridge-backup", time.strftime("%Y%m%d-%H%M%S"))
    for rel in game.get("conflicts", []):
        src = os.path.join(folder, rel)
        if os.path.exists(src):
            dst = os.path.join(backup, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            moved.append(rel)
    if moved:
        log(f"[mods] moved {', '.join(moved)} to {backup}")
        done.append(f"moved the other trigger mod to {os.path.relpath(backup, folder)}")

    # REFramework's window stays hidden by default (Insert opens it), on every install and
    # update, whether we installed REFramework or it was there already: people install this
    # for the mod, not to look at REFramework. Mods with loose files (button icons under
    # natives\) also need its loose file loader.
    settings = dict(QUIET_MENU)
    if game.get("loose_files"):
        settings.update(LOOSE_FILES)
    set_config(os.path.join(folder, REFRAMEWORK_CONFIG), settings)
    for rel, url in game["files"].items():
        data = get(url)
        if not data.strip():
            raise RuntimeError(f"empty download: {url}")
        _write(os.path.join(folder, rel), data)
    done.append("installed the mod")
    log(f"[mods] {game['name']}: " + "; ".join(done))
    return done




def _remove_empty_parents(path, stop):
    """Remove the folders above path that are now empty, up to (not including) stop."""
    stop = os.path.abspath(stop)
    parent = os.path.dirname(os.path.abspath(path))
    while (os.path.normcase(parent) != os.path.normcase(stop)
           and os.path.normcase(os.path.commonpath([parent, stop])) == os.path.normcase(stop)):
        try:
            os.rmdir(parent)              # only succeeds on an empty folder
        except OSError:
            return
        parent = os.path.dirname(parent)


def _files_under(path):
    return [os.path.join(root, f) for root, _, files in os.walk(path) for f in files]


def other_reframework_mods(game, folder):
    """Files of other REFramework scripts or plugins in the game (they need REFramework)."""
    ours = {os.path.normcase(os.path.join(folder, rel)) for rel in game["files"]}
    found = []
    for sub in ("autorun", "plugins"):
        for f in _files_under(os.path.join(folder, "reframework", sub)):
            if os.path.normcase(f) not in ours:
                found.append(os.path.relpath(f, folder))
    return found


def reframework_is_ours(game, folder):
    return os.path.exists(os.path.join(folder, game["data"], REFRAMEWORK_MARKER))


def uninstall(game, folder, log=print):
    """Remove the game's mod; REFramework too if we installed it and nothing else uses it.
    Backups of other mods (DualSenseBridge-backup) are kept. Returns what was done."""
    done = []
    ours = reframework_is_ours(game, folder)        # read before the data folder goes
    remove_loader = ours and not other_reframework_mods(game, folder)
    if remove_loader and os.path.exists(os.path.join(folder, "dinput8.dll")):
        try:                                  # first: it's locked while the game runs
            os.remove(os.path.join(folder, "dinput8.dll"))
        except PermissionError:
            raise RuntimeError("the game is running: close it and try again") from None
    for rel in game["files"]:
        path = os.path.join(folder, rel)
        if os.path.exists(path):
            os.remove(path)
        _remove_empty_parents(path, folder)
    shutil.rmtree(os.path.join(folder, game["data"]), ignore_errors=True)
    done.append("removed the mod")
    if remove_loader:
        for name in REFRAMEWORK_FILES[1:]:
            try:
                os.remove(os.path.join(folder, name))
            except FileNotFoundError:
                pass
        root = os.path.join(folder, "reframework")
        if os.path.isdir(root) and not _files_under(root):    # only empty folders left
            shutil.rmtree(root, ignore_errors=True)
        done.append("removed REFramework (DualSense Bridge had installed it)")
    elif ours:
        done.append("kept REFramework: other mods use it")
    log(f"[mods] {game['name']}: " + "; ".join(done))
    return done
