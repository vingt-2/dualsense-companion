# Notes for agents working on DualSense Companion

DualSense Companion makes a Bluetooth DualSense look like a wired one to Windows (USB/IP +
usbip-win2 + HidHide), so games enable haptics, adaptive triggers, speaker and mic. Read
`README.md` first (features, file list, protocol notes). This file is about **adding game mods**
and the conventions that matter when changing the project.

## How the owner works

- They test on real hardware and in games, then say "push" (commit + push) or "push and update
  release" (also `gh release create vX.Y.Z` with the installer from `.\build.ps1 -Version X.Y.Z`
  and short user-facing notes). Don't push or release without being asked.
- **Every release attaches the installer twice**: `DualSenseCompanion-Setup-X.Y.Z.exe` and
  the identical `DualSenseBridge-Setup-X.Y.Z.exe` (`build.ps1` makes both). Copies installed
  before the rename (as DualSense Bridge) only look for the old name; GitHub redirects the old
  repo to this one. Never create a new repo called `dualsense-bridge`: it would end the redirect.
- Commit as the repo-local GitHub noreply identity (already configured in `.git/config`); never
  put a personal email in commits.
- Trust their reports of feel and sound over your own measurements.
- Installing a local build for them to try: build, then
  `Start-Process dist\DualSenseCompanion-Setup-X.Y.Z.exe -ArgumentList "/SILENT","/SUPPRESSMSGBOXES","/LAUNCH=1"`
  **without** `-Wait` (the installer relaunches the app and `-Wait` hangs). Check
  `%LOCALAPPDATA%\DualSenseCompanion\companion.log` afterwards: a crash at startup shows there.
- User-facing text calls the feature **"Game mods"**. Don't name DualSenseX/DSX in feature names
  or menus; it's fine in code, credits and one compatibility line in the README.
- **REFramework's window stays hidden by default** for anyone who installs a mod through the
  app (Insert still opens it): every install and update sets `RememberMenuState=true` and
  `MenuOpen=false` in its config, even when REFramework was already there. People install these
  for the mod, not to see REFramework. Keep it that way for every new game.

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
  script from this repo's `main`, conflicting mods moved to `DualSenseCompanion-backup`).
- `tray_app.py`: the *Game mods* submenu, the "Get the DualSense mod for …" suggestion when a
  catalogued game runs without its mod, and the install flow (confirm dialog -> install -> notify).
- `mods/<game>/`: the mods themselves, each with a README that doubles as the manual guide.

Mods made for DualSenseX (Skyrim, Fallout 4, RDR2, GTA, ...) already work over UDP with no
changes; you only write a mod for games that have none, or whose mod is broken.

## Adding a game

1. **Write the mod** in `mods/<game>/`, laid out as it goes into the game folder (e.g.
   `mods/re4-remake/reframework/autorun/dualsense_companion_re4.lua`). If the mod can't open
   sockets (REFramework Lua can't), have it write a payload file inside the game folder. Use our
   own path, e.g. `reframework\data\DualSenseCompanion\<game>_triggers.json`.
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
     app reports the trigger as released (analog 0, digital bit cleared).
   - Back to a plain reset in menus/cutscenes (our RE scripts keep the health colour there, see
     below), and a plain reset when disabled and on script reload.
   - **The lightbar shows the player's health, as on PS5** in all our RE mods: green above 66 %,
     yellow above 45 %, orange above 25 %, red below (`HEALTH_COLOURS` in each script). The menu
     (or `"lightbar_health": false` in the config) switches it to the class's `rgb` instead.
     With nothing in hand the payload is a reset plus the health colour. Read health from the
     *current* player object every poll: games swap it (loads, cutscenes, another character)
     and the old one keeps answering with stale health (RE3 did); cache the component found
     only for as long as the player object's address is the same.
   - Write a one-line status file next to the payload (what was detected, any error) so problems
     can be diagnosed from outside the game without asking the user to read menus.
2. **Register the payload path** in `dsx.PAYLOAD_PATHS` (relative to the game exe's folder).
3. **Add the game to `game_mods.GAMES`**: `exe`, `name`, `features` (what the mod adds, e.g.
   "adaptive triggers and PlayStation button prompts", used in the tray's messages), `installed` (files that mean the mod is
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
   `dinput8.dll` only when missing and then leaves a marker; every install and update sets
   REFramework to keep its window hidden, see above; uninstall removes REFramework only with that marker and no other REFramework mods); a
   game with another loader needs a new branch there.
4. **Write the mod's README** (`mods/<game>/README.md`): what it does, "The quick way" (tray ->
   *Game mods* -> *<game>* -> *Install the DualSense mod…*), "By hand" steps a non-modder can follow,
   troubleshooting, tuning, credits.
5. **Tests**, and add each new test script to `build.ps1` (the build runs them all):
   - extend `tests/test_dsx.py` / `tests/test_mod_installer.py` / `tests/test_tray_menu.py`;
   - for a Lua mod, a test like `tests/test_re4_mod.py`: run the real script in `lupa` against a
     stand-in of exactly the engine API the script uses, and check the payloads it writes by
     feeding them to `dsx.parse` + `dsx.Overrides`. Keep the stand-in faithful: it must not
     provide functions the real engine lacks (see pitfalls).
6. **Try it in the game** with the owner before pushing. Ship a temporary probe script when you
   need to learn something about the game (see below); remove it afterwards.

### RE2, RE3 and Village are generated

`tools/make_remake_scripts.py` builds `mods/re2`, `mods/re3` and `mods/re8` from the RE7 script:
edit RE7's (or the generator's per-game `GAMES` entry: weapon IDs, `l2`/`r2`/`fire` per class,
`feel` comment, `health` block), then run it and the tests. Trigger feel, tuned against the PS5
versions with the owner: RE4 (its own), Village (in the generator), RE7 (Village's values),
RE2/RE3 (RE4's values, `RE4_L2`/`RE4_R2`/`RE4_FIRE`). The REFramework menu entry is called
**DualSense-Companion** in every game.

## Learning a game's API (REFramework / RE Engine)

- Prefer facts from MIT/permissive projects (e.g. RE4R Archipelago, REE Content Editor). Method
  and type names, IDs and data layouts are facts; code is not: write your own.
- When the sources run out, write a small probe script that logs what you need to a file under
  `reframework/data/DualSenseCompanion/` (enumerate a type's methods via `get_type_definition()`,
  `get_methods()`, `get_parent_type()`; call candidate getters; log values per state change),
  have the owner play for a minute, read the file. This found RE4's weapon objects quickly.
- RE4 (2023) facts we rely on: `chainsaw.CharacterManager:getPlayerContextRef()` ->
  `get_HeadGameObject()` (works for Leon and Ada) -> component `chainsaw.PlayerEquipment` ->
  `get_EquipWeaponID()`. Loaded ammo: `chainsaw.InventoryManager._ControllerTable` values ->
  the `chainsaw.CsInventoryController` -> `getEquippedWeapon()` -> `get_CurrentAmmoCount()`.
  Weapon IDs -> classes: the table in the script (from Advanced Weapon Framework's data).
  Health: the player context's `get_HitPoint()` -> `get_CurrentHitPoint()` / `get_DefaultHitPoint()`.
- RE7 facts (probe, 2026-11-01; same in the main game and *Not a Hero*):
  `app.InteractManager._PlayerStatus` (a field) -> `EquipManager` -> `get_equipWeaponItemIDRight()`
  (the item ID as a string: `Handgun_G17`, `Shotgun_Albert`, `CKnife`, ...) and
  `get_equipWeaponRight():get_loadNum()` (loaded rounds). Classes come from the item ID's name.
  Not a Hero has its own inventory (`app.CH8Inventory`) and item IDs; main-game items can't be
  equipped there. The probe used is kept outside git (`build/probes/`); its approach (read fields
  as well as getters, start from known objects, log scan errors) is what worked.
  Health: `app.ObjectManager.PlayerObj`, then whichever of its components has health getters
  (the script looks through `get_Components()`; not yet pinned down by a probe).
- RE2 / RE3 facts: the player is `<ns>.PlayerManager:get_CurrentPlayer()` (`app.ropeway` /
  `offline`); health is its `<ns>.HitPointController`'s `get_CurrentHitPoint()` /
  `get_DefaultHitPoint()` (checked in game).
- Village facts (probes, 2026-11-02): the player is `app.PropsManager`'s
  `<Player>k__BackingField` (a GameObject). Its health is **not** a component: its
  `app.PlayerUpdaterFPS` component's `get_damageController()` -> `app.DamageController`
  `get_health()` / `get_maxHealth()` (1000 max; the game's own thresholds are caution 500 and
  danger 300). An item's ID is the murmur3 (32-bit) of its name (`"ri3046"`) in UTF-16LE with
  seed `0xFFFFFFFF` (facts from the Visceral RE8 VR project, which has no licence: facts only).

## PlayStation button prompts

RE7, Village, RE2 and RE3 show only Xbox prompts on PC and only read XInput (with Steam Input
off, RE7 sees no controller at all), so the game can't be made to pick its own PlayStation icons.
Instead each game's mod ships its icon atlas with the Xbox cells replaced by PS5 icons, loaded as
a loose file (`"loose_files": True` in `game_mods.py` turns on REFramework's loose file loader on
install; the tray asks for the game to be closed, because the game rewrites REFramework's config
on exit). The owner chose to ship them as part of each game's mod (no separate option: nobody
playing on a DualSense wants Xbox prompts) and to keep the icons in the repo. They're only in
place while the app runs (`"while_app_runs"` in `game_mods.py`): installed into the mod's
data folder, copied into `natives\` when the app starts (`mod_installer.activate`) and
removed when it quits (`deactivate`), so a game started without the app shows its own icons.
Only files with a stashed copy are ever removed (an install by hand keeps its icons).
These games need **Steam Input on** (`"xinput_only": True`): they only read XInput, and Steam
Input turns the DualSense into an XInput pad inside the game. A game script should report
whether the game sees any controller as `"controllerSeen": true/false` in its payload (RE7:
`app.PadManager.ManagedDeviceList` count); the tray notifies once per launch when it stays
false for 2 s (and the script shows the same in game: Windows holds back tray
notifications during fullscreen games). The app can't check this itself: Steam Input's pad only exists in the game. How to find a
game's atlas, map its cells and build it: `tools/ps-icons/README.md`. RE7's atlas:
`natives/stm/ui/ui0000/tex/ui0010_iam.tex.35.x64` (and an identical `ui0020`), checked in game.

## The rename (DualSense Bridge -> DualSense Companion, 1.8.0)

The project was DualSense Bridge until 1.7.1. What carries existing installs over:
- **Installer** (same `AppId`, so it upgrades): installs into `DualSense Companion`, not the old
  folder (`UsePreviousAppDir=no`); quits and kills `DualSenseBridge.exe` too; deletes the old
  program folder, Start menu folder and desktop shortcut (`RemoveOldApp`).
- **App, at start** (`tray_app.migrate_data_dir`, `migrate_startup_task`): moves
  `%LOCALAPPDATA%\DualSenseBridge` to `DualSenseCompanion` (or copies `settings.json` if it's in
  use), replaces the `DualSenseBridge` startup task with ours, and drops the old exe from
  HidHide's allowed apps.
- **Game mods** (`mod_installer.migrate`, run for every game found at start and before every
  install or uninstall): renames `dualsense_bridge_<key>.lua` to `dualsense_companion_<key>.lua`
  (pointing its data path at the new folder) and moves `reframework\data\DualSenseBridge` to
  `DualSenseCompanion`. `game_mods` lists the old names per game (`legacy_files`,
  `legacy_data`, and the old script counts as `installed`), and `dsx.PAYLOAD_PATHS` still follows
  the old payload files, so a game that was running during the move keeps its triggers.
- Kept on purpose: the `while-bridge-runs` stash folder name (existing stashes), and
  `bridge.py` (the module that does the Bluetooth <-> USB bridging).
- Not covered: an old copy that never updates the app and uses *Update the mod…* gets a
  404 (the old script paths are gone). The tray offers the app update first.

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
- **Over Bluetooth the lightbar ignores colours until it's handed over**: the controller keeps
  the blue it lights at connect until an output report sets valid flag 2 bit 1 (byte 39 of the
  USB report) with lightbar setup = 2 ("light out", byte 42). Games that drive the DualSense
  themselves (RE4) send it; games behind Steam Input never do, so the app sends it once per
  connection before the first colour (`WiredDualSense._send`, 1.8.0). The fact is from the
  Linux hid-playstation driver (GPL: fact only).
- A DSX UDP sender that exits gets its effects released at once (it's treated as the mod's
  process): a test script that sends one packet and quits shows nothing. Keep it running.
- A game exe name can match more than one game (e.g. remakes); check `installed` paths and the
  Steam app id rather than the exe name alone when that matters.

## Licensing

The project is MIT. Before reusing anything, check its licence: copy code only from permissive
sources (with credit); from everything else (no licence, CC BY-NC, other mods) take facts only.
Other mods are never redistributed or modified by the app; the installer only moves known
conflicting files into a backup folder. Credit inspirations in the mod's README.
