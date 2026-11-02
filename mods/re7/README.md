# Adaptive triggers for Resident Evil 7 biohazard

A small [REFramework](https://github.com/praydog/REFramework) script that gives every weapon in
Resident Evil 7 its own adaptive-trigger feel on a DualSense, played through
[DualSense Bridge](../../README.md). The PC version never had adaptive triggers.

- **Guns fire at the break.** R2 has a trigger wall that gives way, and the game only sees the
  trigger once it's past the wall, so the shot goes off at the break like a real trigger.
- Each class feels different: handguns, shotguns, the 44 MAG, the machine gun, the burner and
  the grenade launcher. Knives and the axe have a light L2, saws buzz, throwables have a light pull.
- An empty gun gets a light, early click.
- The lightbar takes a colour per weapon class (can be turned off).
- Works in the main game and the DLC episodes (e.g. *Not a Hero*). In menus and cutscenes the
  triggers go back to normal.

## Install

You need [DualSense Bridge](../../README.md#install) 1.7 or later.

### The quick way

Right-click DualSense Bridge's tray icon → *Game mods* → *Resident Evil 7* → **Install adaptive
triggers…**, and confirm. It finds the game through Steam, adds REFramework if the game doesn't
have it yet (the right build for your version of the game, with its own menu kept closed: press
Insert to open it), and downloads the script below. Then start (or restart) the game.
*Update the mod…* fetches the latest version, *How it works…* explains it, and *Uninstall…*
removes it again (REFramework too if DualSense Bridge installed it and no other mod uses it).

### By hand

1. In Steam, right-click **Resident Evil 7** → *Manage* → *Browse local files*: the folder with
   `re7.exe`.
2. **REFramework** (skip if you already use it): from the
   [REFramework releases](https://github.com/praydog/REFramework/releases), download **RE7.zip**,
   or **RE7_TDB49.zip** if you play the old *dx11_non-rt* beta branch. Copy only **`dinput8.dll`**
   from it next to `re7.exe`, start the game once and quit.
3. Download **[dualsense_bridge_re7.lua](https://github.com/vingt-2/dualsense-bridge/raw/main/mods/re7/reframework/autorun/dualsense_bridge_re7.lua)**
   and put it in `reframework\autorun` in the game folder.
4. Play. DualSense Bridge's tray menu shows *Game mod: re7.exe – …* with the current effects.

In game, press **Insert** for the REFramework menu and open *Script Generated UI → DualSense
Bridge: adaptive triggers*: it turns the script and its lightbar colours on or off, and shows the
current weapon, its class and its loaded ammo. `reframework\data\DualSenseBridge\re7_status.txt`
has the script's last status line; include it in any
[issue](https://github.com/vingt-2/dualsense-bridge/issues).

To remove it by hand, delete `reframework\autorun\dualsense_bridge_re7.lua` and the
`reframework\data\DualSenseBridge` folder.

## Tuning

The feel of each class is the `PROFILES` table at the top of
`reframework\autorun\dualsense_bridge_re7.lua` (the same settings as the
[RE4 mod's](../re4-remake/README.md#tuning)). Weapons are recognised by their item ID
(`Handgun_G17`, `Shotgun_M37`, …) through the `CLASS_RULES` list; the menu shows the ID of the
weapon in hand, so a new one can be added. To keep changes across updates, put them in
`reframework\data\DualSenseBridge\re7_config.json`, e.g. `{"profiles": {"handgun": {"fire": 200}}}`.

## Testing

`extras\dualsense_bridge_test_weapons_re7.lua` puts every weapon and some ammo into the item box,
for trying each weapon class. Copy it into `reframework\autorun`, use its REFramework menu, and
remove it when you're done.

## Credits

Game facts (the player's equipment manager, item IDs, the item box) come from the
[RE7 Archipelago client](https://github.com/ElGrenier/RE7_AP_Client) (MIT), and were checked in
game with a probe. MIT licence, like the rest of DualSense Bridge.
