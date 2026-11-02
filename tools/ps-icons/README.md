# PlayStation button icons for RE Engine games

Capcom's PC releases of Resident Evil 7 (and Village, RE2 and RE3) only show Xbox button
prompts, and they only read XInput controllers, so no setting brings the PlayStation icons
back. Their prompts come from one texture atlas per game; replacing its Xbox cells with
PlayStation icons and loading it with REFramework's loose file loader fixes every prompt at once.

- `ps5_icons.png`: the PS5 icon atlas from Resident Evil 4 (2023) (`natives/stm/_chainsaw/ui/
  ui0000/tex/cs_ui0010_ps5_iam.tex`), decoded: 6 columns of 80-pixel cells. It's Capcom's art,
  from the same studio as the games it goes into, so the icons match their style.
- `make_icons.py`: builds a game's atlas from its own Xbox atlas and `ps5_icons.png`, with a
  cell map per game (`GAMES`). Only the replaced cells are re-encoded (BC7); everything else,
  including the header and the keyboard/mouse icons, stays the game's own.

The built textures for each game live with its mod (`mods/<game>/icons/natives/...`), and the
tray's *Install adaptive triggers…* installs them with the trigger script.

## Rebuilding (e.g. after a game update changes its atlas)

```
pip install pillow texture2ddecoder etcpak
python tools/ps-icons/make_icons.py re7 <the game's ui0010_iam.tex.35.x64> mods/re7/icons/natives/stm/ui/ui0000/tex/ui0010_iam.tex.35.x64
```

## Adding a game

1. **Extract the game's UI files.** Use [ree-pak-rs](https://github.com/eigeen/ree-pak-rs)
   (MIT) with the game's file list from [REE.PAK.Tool's Projects](https://github.com/Ekey/REE.PAK.Tool/tree/main/Projects)
   (e.g. `RE7_RT_STM_Release.list`): `ree-pak-cli unpack -p <list> -i re_chunk_000.pak -o out
   -f "ui/ui0000/"`. Unpack patch paks too, newest wins (RE7's are empty placeholders).
2. **Find the button atlas.** In RE7 it's `natives/stm/ui/ui0000/tex/ui0010_iam.tex.35.x64`:
   the UI textures with a platform suffix (`.x64`) are the platform-specific ones, and the PS4
   build's list has the same name with `.ps4`. The cells are listed in `ui0010.uvs`
   (`.SVU` header; UV rectangles at 0x70, 32 bytes apart).
3. **Map its cells.** Decode it (BC7, `make_icons.decode`), lay its Xbox cells next to
   `ps5_icons.png`'s, and add a `GAMES` entry: `{game cell: sheet cell}`, by meaning (A -> ✕,
   B -> ○, X -> □, Y -> △, LB/RB/LT/RT -> L1/R1/L2/R2, Menu -> Options, View -> touch pad, …).
4. **Build it, put it in `mods/<game>/icons/natives/…`**, list it in the game's `files` in
   `game_mods.py` with `"loose_files": True`, and try it in the game.
