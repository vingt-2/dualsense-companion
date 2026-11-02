# Notes for agents working on DualSense Bridge

DualSense Bridge makes a Bluetooth DualSense look like a wired one to Windows (USB/IP +
usbip-win2 + HidHide), so games enable haptics, adaptive triggers, speaker and mic. Read
`README.md` first (features, file list, protocol notes). This file is about **adding game mods**
and the conventions that matter when changing the project.

## How the owner works

- They test on real hardware and in games, then say "push" (commit + push) or "push and update
  release" (also `gh release create vX.Y.Z` with the installer from `.\build.ps1 -Version X.Y.Z`
  and short user-facing notes). Don't push or release without being asked.
- Commit as the repo-local GitHub noreply identity (already configured in `.git/config`); never
  put a personal email in commits.
- Trust their reports of feel and sound over your own measurements.
- Installing a local build for them to try: build, then
  `Start-Process dist\DualSenseBridge-Setup-X.Y.Z.exe -ArgumentList "/SILENT","/SUPPRESSMSGBOXES","/LAUNCH=1"`
  **without** `-Wait` (the installer relaunches the app and `-Wait` hangs). Check
  `%LOCALAPPDATA%\DualSenseBridge\bridge.log` afterwards: a crash at startup shows there.
- User-facing text calls the feature **"Game mods"**. Don't name DualSenseX/DSX in feature names
  or menus; it's fine in code, credits and one compatibility line in the README.

## Game mods: how it fits together

```
game + mod ──(UDP JSON to 127.0.0.1:6969)──┐
                                           ├─> dsx.Overrides ──> WiredDualSense._output patches
game + mod ──(writes a payload JSON file)──┘     (triggers,        every output report 0x02 the game
                 dsx.PayloadWatcher reads it      lights, mic LED,  sends; thresholds are applied to
                                                  thresholds)       the input report in _on_bt_input
```

- `dsx.py`: the protocol. `parse()` (lenient JSON), `encode_trigger()` (all 27 trigger modes ->
  11 bytes), `Overrides` (the state and the report patching), `DsxServer` (UDP, replies to every
  packet), `PayloadWatcher` (finds running games with a known payload file and follows it; also
  reports every new process to `on_process`), port files.
- `game_mods.py`: the catalogue of games **we** ship a mod for (detection + install data).
- `mod_installer.py`: one-click install (Steam lookup, REFramework from GitHub releases, our
  script from this repo's `main`, conflicting mods moved to `DualSenseBridge-backup`).
- `tray_app.py`: the *Game mods* submenu, the "Get adaptive triggers for …" suggestion when a
  catalogued game runs without its mod, and the install flow (confirm dialog -> install -> notify).
- `mods/<game>/`: the mods themselves, each with a README that doubles as the manual guide.

Mods made for DualSenseX (Skyrim, Fallout 4, RDR2, GTA, ...) already work over UDP with no
changes; you only write a mod for games that have none, or whose mod is broken.

## Adding a game

1. **Write the mod** in `mods/<game>/`, laid out as it goes into the game folder (e.g.
   `mods/re4-remake/reframework/autorun/dualsense_bridge_re4.lua`). If the mod can't open
   sockets (REFramework Lua can't), have it write a payload file inside the game folder. Use our
   own path, e.g. `reframework\data\DualSenseBridge\<game>_triggers.json`.
   - Payload format: `{"instructions":[{"type":T,"parameters":[0, ...]}, ...]}` (the first
     parameter is the controller index, always 0). Types: 1 trigger effect
     `[0, side (1 L2, 2 R2), mode, params...]`, 2 lightbar `[0, r, g, b]`, 3 player LEDs,
     4 trigger threshold `[0, side, 0-255]`, 5 mic LED, 7 reset. Modes worth using:
     13 Resistance `(start zone 0-9, force 1-8)`, 22 Weapon `(start 2-7, break 3-8, force 1-8)`,
     23 Vibration `(start, amplitude 1-8, frequency)`, 14 Bow, 15 Galloping, 18 Machine, 0 off.
   - **Start every payload with a reset (type 7)** and write the whole state each time, so nothing
     (a threshold, a lightbar colour) leaks from one weapon to the next. Write only on change.
   - Guns: a Weapon wall plus an R2 **threshold** just past the break makes the game see the
     trigger only once the wall gives way, so the shot fires at the break. Below the threshold the
     bridge reports the trigger as released (analog 0, digital bit cleared).
   - Back to a plain reset in menus/cutscenes, when disabled, and on script reload.
   - Write a one-line status file next to the payload (what was detected, any error) so problems
     can be diagnosed from outside the game without asking the user to read menus.
2. **Register the payload path** in `dsx.PAYLOAD_PATHS` (relative to the game exe's folder).
3. **Add the game to `game_mods.GAMES`**: `exe`, `name`, `installed` (files that mean the mod is
   there), `data` (the mod's own data folder, removed on uninstall; the installer also keeps its
   "we installed REFramework" marker there), `guide` (URL of the mod's README), `about` (a plain-language "how it works" for the
   tray's per-game submenu; no jargon), and for the one-click install `steam_appid`,
   `reframework` (`{"repo", "asset"}`: the REFramework zip for the game's current build; see the
   comment in `game_mods.py` for stable vs nightly) and, if Steam branches need other builds,
   `reframework_branches` (`{branch: {"repo", "asset"}}`, e.g. RE2/3/7's `dx11_non-rt` ->
   `RE2_TDB66.zip`/`RE3_TDB67.zip`/`RE7_TDB49.zip` from stable; the installer reads the installed
   branch from the Steam app manifest's `BetaKey`), `files`
   (`{path in game folder: raw.githubusercontent URL on main}`) and `conflicts` (other mods'
   files to move aside). `mod_installer.install` assumes an REFramework game (it installs
   `dinput8.dll` only when missing, then sets REFramework to keep its menu closed and leaves a
   marker; uninstall removes REFramework only with that marker and no other REFramework mods); a
   game with another loader needs a new branch there.
4. **Write the mod's README** (`mods/<game>/README.md`): what it does, "The quick way" (tray ->
   *Game mods* -> *<game>* -> *Install adaptive triggers…*), "By hand" steps a non-modder can follow,
   troubleshooting, tuning, credits.
5. **Tests**, and add each new test script to `build.ps1` (the build runs them all):
   - extend `tests/test_dsx.py` / `tests/test_mod_installer.py` / `tests/test_tray_menu.py`;
   - for a Lua mod, a test like `tests/test_re4_mod.py`: run the real script in `lupa` against a
     stand-in of exactly the engine API the script uses, and check the payloads it writes by
     feeding them to `dsx.parse` + `dsx.Overrides`. Keep the stand-in faithful: it must not
     provide functions the real engine lacks (see pitfalls).
6. **Try it in the game** with the owner before pushing. Ship a temporary probe script when you
   need to learn something about the game (see below); remove it afterwards.

## Learning a game's API (REFramework / RE Engine)

- Prefer facts from MIT/permissive projects (e.g. RE4R Archipelago, REE Content Editor). Method
  and type names, IDs and data layouts are facts; code is not: write your own.
- When the sources run out, write a small probe script that logs what you need to a file under
  `reframework/data/DualSenseBridge/` (enumerate a type's methods via `get_type_definition()`,
  `get_methods()`, `get_parent_type()`; call candidate getters; log values per state change),
  have the owner play for a minute, read the file. This found RE4's weapon objects quickly.
- RE4 (2023) facts we rely on: `chainsaw.CharacterManager:getPlayerContextRef()` ->
  `get_HeadGameObject()` (works for Leon and Ada) -> component `chainsaw.PlayerEquipment` ->
  `get_EquipWeaponID()`. Loaded ammo: `chainsaw.InventoryManager._ControllerTable` values ->
  the `chainsaw.CsInventoryController` -> `getEquippedWeapon()` -> `get_CurrentAmmoCount()`.
  Weapon IDs -> classes: the table in the script (from Advanced Weapon Framework's data).
- RE7 facts (probe, 2026-11-01; same in the main game and *Not a Hero*):
  `app.InteractManager._PlayerStatus` (a field) -> `EquipManager` -> `get_equipWeaponItemIDRight()`
  (the item ID as a string: `Handgun_G17`, `Shotgun_Albert`, `CKnife`, ...) and
  `get_equipWeaponRight():get_loadNum()` (loaded rounds). Classes come from the item ID's name.
  Not a Hero has its own inventory (`app.CH8Inventory`) and item IDs; main-game items can't be
  equipped there. The probe used is kept outside git (`build/probes/`); its approach (read fields
  as well as getters, start from known objects, log scan errors) is what worked.

## Hidden options

- **Haptics delay** (the controller's haptics buffer depth) has a tray submenu that is hidden
  since 1.7.0, because the default held up in every game the owner played. It's still in
  `tray_app.py`: set `SHOW_HAPTICS_DELAY = True` to show it again. A `haptics_depth` in
  `settings.json` is applied either way. Bring it back if users report stuttering haptics.

## Pitfalls we hit (don't repeat them)

- **REFramework has no `sdk.get_current_scene()`.** Get the scene with
  `sdk.call_native_func(sdk.get_native_singleton("via.SceneManager"),
  sdk.find_type_definition("via.SceneManager"), "get_CurrentScene")`. Wrap engine calls in
  `pcall`; a script that errors every frame writes nothing and looks "dead".
- REFramework Lua `io.open` paths are relative to `reframework/data` and it creates folders.
- **pystray menu actions must take 0-2 positional parameters**; a lambda with a default argument
  (`lambda _, __, g=game:`) counts as 3 and crashes the app at startup. Build per-item closures
  instead (see `TrayApp._game_items`). `tests/test_tray_menu.py` builds the whole menu: run it.
- **In this Windows Git Bash, heredocs collapse backslashes** (`\\` -> `\`), so `\r`, `\a`, `\t`
  in Windows paths silently become control characters. Write edit scripts to a file with your
  file-writing tool and run them by path; never pipe code containing backslashes through `<<EOF`.
  A file watcher may also convert files to CRLF; normalise when matching text.
- **DSX trigger mode numbers**: 1-7 and 9-11 are named presets that take **no** parameters
  (2 is VerySoft, 3 Soft, not "Weapon"/"Bow"). Mods that pass parameters to them get nothing.
  Weapon is 22, Bow 14. The preset bytes are DualSenseY's (DSX never published them).
- Trigger thresholds persist until changed: every payload must set them (or reset first).
- A game exe name can match more than one game (e.g. remakes); check `installed` paths and the
  Steam app id rather than the exe name alone when that matters.

## Licensing

The project is MIT. Before reusing anything, check its licence: copy code only from permissive
sources (with credit); from everything else (no licence, CC BY-NC, other mods) take facts only.
Other mods are never redistributed or modified by the bridge; the installer only moves known
conflicting files into a backup folder. Credit inspirations in the mod's README.
