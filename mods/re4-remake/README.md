# DualSense mod for Resident Evil 4 (2023)

A small [REFramework](https://github.com/praydog/REFramework) script that gives every weapon in
Resident Evil 4 (2023) its own adaptive-trigger feel on a DualSense, played through
[DualSense Bridge](../../README.md). Capcom never shipped adaptive triggers in the PC version.

- **Guns fire at the break.** R2 has a trigger wall that gives way, and the game only sees the
  trigger once it's past the wall, so the shot goes off at the break like a real trigger instead
  of before you reach the resistance.
- Each class feels different: pistols, shotguns, rifles, magnums, SMGs, the bolt thrower and
  launchers. Knives have a light L2 and no R2 resistance.
- An empty gun gets a light, early click.
- The lightbar takes a colour per weapon class (can be turned off).
- In menus and cutscenes the triggers go back to normal.

## Install

You need [DualSense Bridge](../../README.md#install) 1.7 or later.

### The quick way

Right-click DualSense Bridge's tray icon → *Game mods* → *Resident Evil 4* → **Install the DualSense
mod…**, and confirm. It finds the game through Steam, adds REFramework if the game doesn't
have it yet (set to keep its own menu closed; press Insert to open it), downloads the script
below, and moves any other trigger mod into `DualSenseBridge-backup` in the game folder (nothing
is deleted). Then start (or restart) the game. *Update the mod…* in the same submenu fetches the
latest version of the script, *How it works…* explains what it does, and *Uninstall…* removes it
again. If DualSense Bridge installed REFramework and no other mod uses it, Uninstall removes it
too; otherwise REFramework stays.

To remove it by hand, delete `reframework\autorun\dualsense_bridge_re4.lua` and the
`reframework\data\DualSenseBridge` folder.

### By hand

About five minutes:

#### 1. Find the game folder

In Steam, right-click **Resident Evil 4** → *Manage* → *Browse local files*. That opens the folder
with `re4.exe` in it; the steps below all happen there.

#### 2. Install REFramework (skip if you already use it)

REFramework is the mod loader that runs the script.

1. Open the [REFramework releases](https://github.com/praydog/REFramework/releases) page and
   download **RE4.zip** from the latest release.
2. Open the zip and copy **`dinput8.dll`** into the game folder, next to `re4.exe`.
3. Start the game once and quit. REFramework creates a `reframework` folder next to `re4.exe`.

#### 3. Add the trigger script

1. Download **[dualsense_bridge_re4.lua](https://github.com/vingt-2/dualsense-bridge/raw/main/mods/re4-remake/reframework/autorun/dualsense_bridge_re4.lua)** (if your browser shows the
   text instead, right-click the link → *Save link as…*).
2. Put it in `reframework\autorun` in the game folder.

#### 4. Remove any other trigger mod

If you installed another adaptive-trigger mod for RE4 (for example one that needs DualSenseX and a
"UDP client"), remove it, or the two will fight over the triggers. For lunati_'s mod, delete
`reframework\autorun\DualsenseX.lua` and the `reframework\autorun\DualsenseX` folder. You don't
need DualSenseX or any helper app.

#### 5. Play

Start the game and draw a weapon: the triggers change with it. DualSense Bridge's tray menu
shows *Game mod: re4.exe – …* with the current effects.

To check on the script in game, press **Insert** for the REFramework menu and open *Script
Generated UI → DualSense Bridge: adaptive triggers*. It turns the script and its lightbar colours
on or off, and shows the current weapon, its class and its loaded ammo.

### If the triggers don't change

- **The REFramework menu has no *DualSense Bridge* entry**: the script isn't in
  `reframework\autorun`, or REFramework isn't loading (step 2).
- **The entry says "Player: no player…" in the middle of gameplay**: open an
  [issue](https://github.com/vingt-2/dualsense-bridge/issues) with what it shows.
- **The entry looks fine but the tray never shows *Game mod***: make sure *Game mods* is ticked in
  DualSense Bridge's tray menu and that it's version 1.7 or later.
- `reframework\data\DualSenseBridge\re4_status.txt` has the script's last status line; include
  it in any issue.

## Tuning

The feel of each class is the `PROFILES` table at the top of
`reframework\autorun\dualsense_bridge_re4.lua`:

- `r2 = {22, start, break, force}`: a wall from zone *start* (2-7) that breaks at zone *break*
  (3-8, out of 10 along the trigger's travel), with force 1-8.
- `fire`: where the game starts to see R2 (0-255). Put it just past the break: if the shot
  goes off while you're still pushing the wall, raise it; if you have to squeeze well past the
  break, lower it.
- `l2 = {13, start, force}`: steady resistance from zone *start* with force 1-8.

To keep your changes across updates, put them in `reframework\data\DualSenseBridge\re4_config.json`
instead, e.g. `{"profiles": {"handgun": {"fire": 200}}}`.

Every weapon of the main game, Separate Ways and Mercenaries is listed in `WEAPON_CLASS`. A
weapon that isn't (e.g. from a later update) is classed by its ID family (wp40xx pistols,
wp41xx shotguns, ...), or gets a light L2 only; the menu shows its ID, so it can be added.

## Testing

`extras\dualsense_bridge_test_weapons.lua` is a helper for trying every weapon class: copy it
into `reframework\autorun`, and its REFramework menu puts one of each weapon you don't own yet
(plus ammo and grenades) into storage, to take out at a typewriter. Remove it when you're done.

## Credits

The idea comes from **lunati_**'s
[Resident Evil 4 Remake Adaptive Triggers](https://www.nexusmods.com/residentevil42023/mods/5813)
(Nexus Mods), which was the first to bring DSX trigger effects to this game through REFramework.
We tested that mod with DualSense Bridge and then wrote this one independently, from scratch,
with its own design: every update replaces the whole trigger state, and guns use a trigger
threshold so the shot fires at the wall's break. No code from that mod is included; we learned
from it where the game keeps the equipped weapon's loaded ammo.

Game facts come from public RE Engine modding resources: the weapon classes from
SilverEzredes' [Advanced Weapon Framework](https://github.com/SilverEzredes/Advanced-Weapon-Framework)
RE4 weapon data, the weapon list from [REE Content Editor](https://github.com/kagenocookie/REE-Content-Editor)
(MIT), and the inventory and item calls from the
[RE4R Archipelago](https://github.com/LiterallyMetaphorical/RE4R-AP-Wizard) project (MIT).

MIT licence, like the rest of DualSense Bridge.
