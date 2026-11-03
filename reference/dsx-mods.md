# DSX-mod support

Goal: DSX-based trigger mods drive adaptive triggers, lightbar and LEDs through DualSense Companion,
so users don't need DualSenseX (DSX, a paid Steam app) or any mod helper exe. The app stands
in for DSX: it speaks DSX's UDP protocol and also reads the payload files some mods write.
Nothing from any mod is redistributed or changed. Never ask the user for game install paths.

Researched 2026-11-01: read the RE4 mod's files (Nexus residentevil42023/mods/5813 v1.0 by
lunati_), plus PadForge's DSX-compatibility notes (padforge.org/docs/reference/game-mods-internals,
github.com/hifihedgehog/PadForge/issues/529), which were written from the source of several mods.

## Two ways mods talk to DSX

1. **UDP, directly** (most mods: Skyrim SE/AE and Fallout 4 SKSE/F4SE plugins, RDR2, GTA IV/V
   (DualSense4Rockstar, GTASense), Tomb Raider trilogy, BeamNG, Cyberpunk ...). The mod sends JSON
   to `127.0.0.1:<port>` and expects a reply.
2. **Payload file + helper exe** (mods whose scripting has no sockets, e.g. REFramework Lua). The
   mod writes the same JSON to a file; a helper the user starts by hand forwards it over UDP. The
   app reads the file itself, so the helper isn't needed.

## Part 1: UDP stand-in for DSX (generic)

- **Socket:** UDP bound to 127.0.0.1, port 6969. Drop non-loopback datagrams. Disable
  `SIO_UDP_CONNRESET` on Windows, or one mod closing its socket kills the receive loop. If 6969 is
  taken (real DSX running), log it once and stay out of the way.
- **Reply to every packet, before applying it.** Some mods block on `Receive` with no timeout and
  hang without a reply. Send JSON to the source address with `Status: "DSX Received UDP
  Instructions"`, `TimeReceived`, `isControllerConnected`, `BatteryLevel`, and (v3) `Devices`:
  `[{Index, MacAddress, DeviceType: 0 (DualSense), ConnectionType: 0 (USB, as games see us),
  BatteryLevel, plus the support flags for adaptive triggers, lightbar, player LED and mic LED}]`.
  Get the exact field names from the PadForge source or the Paliverse v3.1 UDP example.
- **Port files.** Some mods read the port from a file, and some v2 mods quit if it's missing:
  - `C:\Temp\DualSenseX\DualSenseX_PortNumber.txt` (v2 mods): create if missing, containing `6969`.
  - `%LOCALAPPDATA%\DSX\DSX_UDP_PortNumber.txt` (v3.1 mods): absent means 6969; only fix it if it
    names a different port.
  - Don't touch either while a real DSX process is running.
- **Process check (later, optional).** Some mods (DualSense4GTAV) shut down unless a process named
  `DSX.exe` is running. PadForge ships a tiny stand-in `DSX.exe`. Only add this if a mod we care
  about needs it.

### Parsing (be lenient, like DSX)

`{"instructions":[{"type":1,"parameters":[0,2,13,0,8]}, ...]}`. Keys case-insensitive; `type` is a
number or a name; `parameters` may be null or missing (the v2 example sends `{"type":0,
"parameters":null}` for unused slots); values may be numbers (truncate decimals), numeric strings,
booleans, or null (= 0). Skip instructions you can't read and apply the rest in order. The first
parameter is the controller index: we have one controller, so accept 0 and negative ("all").

| type | Name | Parameters after the index |
|---|---|---|
| 0 | GetDSXStatus | none (reply only) |
| 1 | TriggerUpdate | side (1 = L2, 2 = R2), mode, mode params |
| 2 | RGBUpdate | r, g, b, optional brightness 0-255 (v3; scale colours by it) |
| 3 | PlayerLED | five on/off values (bits 0-4, left to right) |
| 4 | TriggerThreshold | side, point 0-255 |
| 5 | MicLED | 0 on, 1 pulse, 2 off (report values 1, 2, 0) |
| 6 | PlayerLEDNewRevision | 0-4 = player 1-5 patterns 0x04, 0x0A, 0x15, 0x1B, 0x1F; 5 = off |
| 7 | ResetToUserSettings | none: drop all overrides, give everything back to the game |

### Trigger modes

0 Normal, 1 GameCube, 2 VerySoft, 3 Soft, 4 Hard, 5 VeryHard, 6 Hardest, 7 Rigid,
8 VibrateTrigger(freq 0-255, default 10), 9 Choppy, 10 Medium, 11 VibrateTriggerPulse,
12 CustomTriggerValue, 13 Resistance(start 0-9, force 0-8), 14 Bow, 15 Galloping,
16 SemiAutomaticGun, 17 AutomaticGun, 18 Machine, 19 VIBRATE_TRIGGER_10Hz, 20 OFF, 21 FEEDBACK,
22 WEAPON, 23 VIBRATION, 24 SLOPE_FEEDBACK, 25 MULTIPLE_POSITION_FEEDBACK,
26 MULTIPLE_POSITION_VIBRATION.

- Each trigger effect is 11 bytes (mode byte + 10 params). Off = `0x05` + zeros.
- 13/21, 14, 15, 16/22, 17/23, 18, 24-26: standard Nielk1 encodings (raw 0x21 feedback, 0x22 bow,
  0x23 galloping, 0x25 weapon, 0x26 vibration, 0x27 machine; Nielk1's TriggerEffectGenerator is MIT).
- 1-7, 9-11 (the named presets): DSX never published their bytes. Use DualSenseY's values, as
  PadForge does. They're unconfirmed against real DSX, so tune by feel if one feels wrong.
- 12 CustomTriggerValue: a custom mode byte (Off 0x00, Rigid 0x01, RigidA 0x21, RigidB 0x05,
  RigidAB 0x25, Pulse 0x02, PulseA 0x22, PulseB 0x06, PulseAB 0x26, plus the VibrateResistance
  and VibratePulse variants) and forces 1-7: values 1-6 go to bytes 1-6, value 7 to byte 9. The
  v3.1 helper library writes values one place early with a trailing null; parse it the way DSX does.
- Unknown mode or bad params: ignore that instruction and keep the previous state.
- Check the licences of DualSenseY and PadForge before copying code; copying the facts (byte
  tables) is fine.

### Trigger threshold (type 4)

The app owns the input path (`WiredDualSense._on_bt_input`), so it can do this: while a
threshold is set, the analog value of that trigger reports 0 below the point and passes
unchanged at or above it. Also clear the matching digital L2/R2 button bit below the point.
Point 0 = no threshold.

## Part 2: payload files (no helper exe)

While a process is running, look in its folder (from its exe path; cache the ones already
checked) for a known payload file. If it's there, watch that file while the process runs, parse
each change as a DSX payload (same parser as UDP, no reply), and clear the overrides when the
process exits. Retry on an empty or partial read: writers truncate and then rewrite. If the
user runs the helper anyway, the same payload also arrives over UDP, which is harmless. Reading
another process's exe path needs `PROCESS_QUERY_LIMITED_INFORMATION`; the app runs as admin.

Known payload locations (relative to the game exe's folder). Keep this a data table so new
mods are a one-line addition:

| Payload path | Mods | Status |
|---|---|---|
| `reframework\data\DualSenseX\payload.json` | lunati_'s REFramework mods: RE4 Remake (nexus 5813), RE Requiem (residentevilrequiem/mods/42); the disputed Requiem copy (mods/24) reportedly reuses the same client | RE4 verified from files; Requiem by the author's description |
| Cyberpunk 2077 "Enhanced DualSense Support" (nexus cyberpunk2077/mods/4156) | uses a CET Lua script plus a UDP client with a JSON file in between | **unverified:** need the mod's files to learn the path and which direction the file goes |

Also worth checking: the mod's helper finds the file from its own location ("GameDir", then
`reframework\data\DualSenseX\payload.json`), which confirms the path is relative to the game folder.

### RE4 mod details (for testing)

The Lua checks the equipped weapon every 6 frames and rewrites payload.json on change and as a
heartbeat. What it sends:

| Weapon class (mapping key) | L2 | R2 | RGB |
|---|---|---|---|
| default | 13 Resistance (0,3) | 0 Normal | 0,0,0 |
| `type:hg` pistols | 13 (0,3) | **2** + (0,9,8) | 0,120,255 |
| `type:xbow` / `type:bowgun` | 13 (0,5) | **2** + (5,9,6) | 0,255,255 |
| `type:sg` shotguns | 13 (0,6) | **3** + (0,6,8,8) | 255,40,40 |
| `type:mag` / `type:magnum` | 13 (0,6) | **3** + (0,8,8,8) | 180,0,255 |
| `type:smg`, `cqbr` | 13 (0,2) | 8 VibrateTrigger (20) | 255,140,0 |
| `type:sr` / `type:rf` rifles | 13 (0,6) | **3** + (0,8,8,8) | 255,255,0 |
| `type:grenade` / `type:thrw` | 13 (0,8) | 13 (0,4) | 0,255,0 |
| `type:knf` / `type:knife` | 13 (0,1) | 0 Normal | 255,255,255 |
| any gun at 0 ammo | (unchanged) | **1** GameCube + (0,8) | (unchanged) |
| mod disabled in its menu | 0 Normal | 0 Normal | 0,0,0 |

The mod's comments call R2 mode 2 "Weapon" and 3 "Bow", but in DSX's numbering 2 is VerySoft and
3 is Soft (presets with no parameters; DSX ignores the extras). The author tuned the feel on
real DSX, so do what DSX does. Don't special-case the mod.

## Output to the controller

Override state: {L2 effect, R2 effect, RGB, player LEDs, mic LED, L2/R2 thresholds}. In USB
output report 0x02 (offsets include the report ID byte):

- `[1]` valid_flag0: 0x04 = R2 effect valid, 0x08 = L2 effect valid
- `[2]` valid_flag1: 0x01 = mic LED valid, 0x04 = lightbar colour valid, 0x10 = player LEDs valid
- `[9]` mic LED, `[11..21]` R2 effect, `[22..32]` L2 effect, `[44]` player LEDs, `[45..47]` R,G,B
- `[39]` valid_flag2: 0x02 = lightbar setup valid, with `[42]` lightbar setup (2 = light out).
  Over Bluetooth the controller ignores colours until this has been sent once on the
  connection; the app sends it before the first colour (`WiredDualSense._send`).

In `WiredDualSense._output` (dualsense_usb.py): while an override is active, patch these bytes
and flags into every 0x02 report the game sends before `bt.write_usb_output`. The game also writes
this report for rumble and the lightbar and would otherwise reset the triggers. When the override
changes, also send one report of our own (zeros except the patched fields and flags).

Holds: DSX keeps effects until a reset. Clear an override when its source goes away: for a
payload file, when the process exits; for UDP, when the sender's process exits (find it from the
UDP port's owner with `GetExtendedUdpTable`), or after 15 s with no packets if it can't be found.
(PadForge instead lets a game's own trigger write win for ~1.5 s; we don't need that, since mods
are mostly for games without trigger support.)

Tray: a "DSX mods" toggle, and the active source plus current effects in the status line.

## Tests (no game needed)

- Replay sample payloads (the RE4 table above, plus the examples in PadForge's GameModTests) as
  UDP datagrams; check the report bytes and that every packet gets a reply.
- Write the same payloads into a temp `reframework\data\DualSenseX\payload.json` (point the
  detector at that folder directly); include an empty write followed by the full one.
- Port-file creation and leaving them alone when a fake `DSX.exe` is "running".
- Threshold: input reports with the trigger below and above the point.
