# DualSense mod for Resident Evil 7 biohazard

Adaptive triggers and PlayStation button prompts for Resident Evil 7 on a DualSense, played
through [DualSense Companion](../../README.md). The PC version has neither: no adaptive triggers,
and only Xbox button prompts.

- **Guns fire at the break.** R2 has a trigger wall that gives way, and the game only sees the
  trigger once it's past the wall, so the shot goes off at the break like a real trigger.
- Each class feels different: handguns, shotguns, the 44 MAG, the machine gun, the burner and
  the grenade launcher, with the feel of Resident Evil Village on PS5: handguns and the
  machine gun aim with only a little resistance deep in the pull and have a light wall, heavier
  guns take more force to aim, the grenade launcher the most. Knives and the axe have no
  resistance, saws buzz, throwables have a light pull.
- An empty gun gets a light, early click.
- **Your health on the lightbar**, as on PS5: green, then yellow and orange as it drops,
  red in danger. The mod's menu can switch it to a colour per weapon class, or off.
- Works in the main game and the DLC episodes (e.g. *Not a Hero*). In menus and cutscenes the
  triggers go back to normal.
- **PlayStation button prompts** everywhere (✕ ○ □ △, L1/R1/L2/R2, Options, the touch pad,
  the sticks…), in the style of Capcom's own PS5 icons (taken from Resident Evil 4). With the
  quick install they're only there when DualSense Companion is running as the game starts: played
  without it (e.g. with an Xbox controller), the game shows its own Xbox icons.

## Install

You need [DualSense Companion](../../README.md#install) 1.7.2 or later (for the lightbar; the
triggers work from 1.7).

**Keep Steam Input on for Resident Evil 7.** The PC version only reads Xbox-style (XInput)
controllers: with Steam Input off it doesn't see a DualSense at all. Steam Input reads the
DualSense and hands the game an Xbox-style pad, while DualSense Companion still drives the
triggers, lightbar and button icons. It's on by default; to check, right-click the game in
Steam → *Properties* → *Controller*, and don't pick *Disable Steam Input*. If the game sees no
controller while the mod runs, DualSense Companion tells you.

### The quick way

Right-click DualSense Companion's tray icon → *Game mods* → *Resident Evil 7* → **Install the DualSense
mod…**, and confirm (close the game first). It finds the game through Steam, adds
REFramework if the game doesn't have it yet (the right build for your version of the game, with
its own menu kept closed: press Insert to open it), downloads the script and the button icons
below, and turns on REFramework's loose file loader, which loads the icons. Then start the game.
*Update the mod…* fetches the latest version, *How it works…* explains it, and *Uninstall…*
removes it again (REFramework too if DualSense Companion installed it and no other mod uses it).

### By hand

1. In Steam, right-click **Resident Evil 7** → *Manage* → *Browse local files*: the folder with
   `re7.exe`.
2. **REFramework** (skip if you already use it): from the
   [REFramework releases](https://github.com/praydog/REFramework/releases), download **RE7.zip**,
   or **RE7_TDB49.zip** if you play the old *dx11_non-rt* beta branch. Copy only **`dinput8.dll`**
   from it next to `re7.exe`, start the game once and quit.
3. Download **[dualsense_companion_re7.lua](https://github.com/vingt-2/dualsense-companion/raw/main/mods/re7/reframework/autorun/dualsense_companion_re7.lua)**
   and put it in `reframework\autorun` in the game folder.
4. **Button icons:** download the two files in [icons/natives/stm/ui/ui0000/tex](icons/natives/stm/ui/ui0000/tex)
   and put them in `natives\stm\ui\ui0000\tex` in the game folder (create the folders). Then,
   with the game closed, set `LooseFileLoader_Enabled=true` in `re2_fw_config.txt` next to
   `re7.exe` (or tick it in REFramework's menu and restart the game).
5. Play. DualSense Companion's tray menu shows *Game mod: re7.exe – …* with the current effects.

In game, press **Insert** for the REFramework menu and open *Script Generated UI → DualSense-Companion*:
it turns the script and the lightbar on or off, switches the lightbar between your health and
the weapon's colour, and shows the current weapon, its class, its loaded ammo and your health. `reframework\data\DualSenseCompanion\re7_status.txt`
has the script's last status line; include it in any
[issue](https://github.com/vingt-2/dualsense-companion/issues).

If the lightbar doesn't follow your health, the menu's *Health* line (and the `health:`
field of the status file) says what the script found; include it in any issue.

To remove it by hand, delete `reframework\autorun\dualsense_companion_re7.lua`, the
`reframework\data\DualSenseCompanion` folder and the two icon files in `natives\stm\ui\ui0000\tex`.

## Tuning

The feel of each class is the `PROFILES` table at the top of
`reframework\autorun\dualsense_companion_re7.lua` (the same settings as the
[RE4 mod's](../re4-remake/README.md#tuning)). Weapons are recognised by their item ID
(`Handgun_G17`, `Shotgun_M37`, …) through the `CLASS_RULES` list; the menu shows the ID of the
weapon in hand, so a new one can be added. To keep changes across updates, put them in
`reframework\data\DualSenseCompanion\re7_config.json`, e.g. `{"profiles": {"handgun": {"fire": 200}}}`.

## Testing

`extras\dualsense_companion_test_weapons_re7.lua` puts every weapon and some ammo into the item box,
for trying each weapon class. Copy it into `reframework\autorun`, use its REFramework menu, and
remove it when you're done.

## Credits

The button icons are Capcom's PS5 icons from Resident Evil 4 (2023), placed into Resident Evil 7's
own icon atlas ([tools/ps-icons](../../tools/ps-icons/README.md) builds it); they belong to Capcom.

Game facts (the player's equipment manager, item IDs, the item box) come from the
[RE7 Archipelago client](https://github.com/ElGrenier/RE7_AP_Client) (MIT), and were checked in
game with a probe. The player's health is read from the component on the player that has
it, found by looking through them. MIT licence, like the rest of DualSense Companion.
