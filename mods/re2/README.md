# DualSense mod for Resident Evil 2

Adaptive triggers and PlayStation button prompts for Resident Evil 2 on a DualSense, played through
[DualSense Companion](../../README.md). The PC version has neither: no adaptive triggers, and only
Xbox button prompts.

- **Guns fire at the break.** R2 has a trigger wall that gives way, and the game only sees the
  trigger once it's past the wall, so the shot goes off at the break like a real trigger.
- Each class feels different: handguns, the shotgun, SMGs, the Lightning Hawk, launchers,
  the flamethrower and knives, with the feel of the Resident Evil 4 remake on PS5: handguns
  and the magnum aim with no resistance, the rest lightly, launchers heavily; light walls,
  the launchers' the strongest; SMGs rattle.
- An empty gun gets a light, early click.
- **Your health on the lightbar**, as on PS5: green, then yellow and orange as it drops,
  red in danger. The mod's menu can switch it to a colour per weapon class, or off.
- In menus and cutscenes the triggers go back to normal.
- **PlayStation button prompts** everywhere (✕ ○ □ △, L1/R1/L2/R2, Options, the touch pad,
  the sticks…), in the style of Capcom's own PS5 icons (taken from Resident Evil 4). With the
  quick install they're only there when DualSense Companion is running as the game starts: played
  without it (e.g. with an Xbox controller), the game shows its own Xbox icons. Not on the old
  *dx11_non-rt* build, which has different icon files (its triggers work).

## Install

You need [DualSense Companion](../../README.md#install) 1.8 or later.

**Keep Steam Input on for Resident Evil 2.** The PC version only reads Xbox-style (XInput)
controllers. Steam Input reads the DualSense and hands the game an Xbox-style pad, while
DualSense Companion still drives the triggers, lightbar and button icons. It's on by default; to
check, right-click the game in Steam → *Properties* → *Controller*. If the game sees no
controller while the mod runs, the mod tells you on screen.

### The quick way

Right-click DualSense Companion's tray icon → *Game mods* → *Resident Evil 2* → **Install the DualSense
mod…**, and confirm (close the game first). It finds the game through Steam, adds REFramework
if the game doesn't have it yet (the right build for your version of the game, with its own
window kept hidden: press Insert to open it), downloads the script and the button icons below,
and turns on REFramework's loose file loader, which loads the icons. Then start the game.
*Update the mod…* fetches the latest version, *How it works…* explains it, and *Uninstall…*
removes it again (REFramework too if DualSense Companion installed it and no other mod uses it).

### By hand

1. In Steam, right-click **Resident Evil 2** → *Manage* → *Browse local files*: the folder with
   `re2.exe`.
2. **REFramework** (skip if you already use it): from the
   [REFramework releases](https://github.com/praydog/REFramework/releases), download
   **RE2.zip**, or **RE2_TDB66.zip** if you play the old *dx11_non-rt* beta branch. Copy only
   **`dinput8.dll`** from it next to `re2.exe`, start the game once and quit.
3. Download **[dualsense_companion_re2.lua](https://github.com/vingt-2/dualsense-companion/raw/main/mods/re2/reframework/autorun/dualsense_companion_re2.lua)**
   and put it in `reframework\autorun` in the game folder.
4. **Button icons** (not on *dx11_non-rt*): download the file in [icons/natives/stm/sectionroot/ui/ui0000/tex](icons/natives/stm/sectionroot/ui/ui0000/tex)
   and put it in `natives\stm\sectionroot\ui\ui0000\tex` in the game folder (create the folders). Then, with the game
   closed, set `LooseFileLoader_Enabled=true` in `re2_fw_config.txt` next to `re2.exe`.
5. Play.

In game, press **Insert** for the REFramework menu and open *Script Generated UI → DualSense-Companion*:
it turns the script and the lightbar on or off, switches the lightbar between your health and
the weapon's colour, and shows the current weapon, its class, its loaded ammo and your health. `reframework\data\DualSenseCompanion\re2_status.txt`
has the script's last status line; include it in any
[issue](https://github.com/vingt-2/dualsense-companion/issues).

If the lightbar doesn't follow your health, the menu's *Health* line (and the `health:`
field of the status file) says what the script found; include it in any issue.

To remove it by hand, delete `reframework\autorun\dualsense_companion_re2.lua`, the
`reframework\data\DualSenseCompanion` folder and the icon file.

## Tuning

The script is generated from the [RE7 one](../re7/README.md) by
`tools/make_remake_scripts.py`; the feel of each class is its `PROFILES` table (the same
settings as the [RE4 mod's](../re4-remake/README.md#tuning)). Weapons are recognised by their
weapon type (by its number, from Advanced Weapon Framework's RE2 data); the menu shows the type of the weapon in hand. To keep changes across
updates, put them in `reframework\data\DualSenseCompanion\re2_config.json`, e.g.
`{"profiles": {"handgun": {"fire": 200}}}`.

## Credits

Game facts: the equipment calls as used by public REFramework scripts (e.g. GreenComfyTea's
Resident Evil 2 Health Bars, MIT), the weapon types from SilverEzredes' Advanced Weapon Framework, and
the player's health from its hit-point controller (the same kind those health bars read for
enemies), checked in game. The
button icons are Capcom's PS5 icons from Resident Evil 4 (2023), placed into Resident Evil 2's own icon
atlas ([tools/ps-icons](../../tools/ps-icons/README.md) builds it); they belong to Capcom.
MIT licence, like the rest of DualSense Companion.
