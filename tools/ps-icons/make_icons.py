"""Build a game's button-icon atlas with PlayStation icons.

Takes the game's own Xbox icon atlas (extracted from its .pak, see README.md) and copies each
PS5 icon from ps5_icons.png into the cell of its Xbox counterpart. Only those cells are
re-encoded (BC7); every other pixel and the texture header stay the game's own.

    pip install pillow texture2ddecoder etcpak
    python tools/ps-icons/make_icons.py re7 <ui0010_iam.tex.35.x64 from the game> <out.tex>
"""
import os
import struct
import sys

import etcpak
import texture2ddecoder
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(HERE, "ps5_icons.png")   # RE4's PS5 atlas: 6 columns of 80 px cells
CELL = 80

# Per game: {game atlas cell (column, row): ps5_icons.png cell (column, row)}, 80 px cells.
# "half" entries take a stick with arrows on both sides and keep only one arrow.
GAMES = {
    "re7": {
        "cells": {
            (0, 0): (0, 0), (1, 0): (1, 0), (2, 0): (2, 0), (3, 0): (3, 0),   # A B X Y
            (4, 0): (4, 0),                                                   # d-pad
            (0, 1): (0, 1), (1, 1): (1, 1), (2, 1): (2, 1), (3, 1): (3, 1),   # d-pad directions
            (4, 1): (4, 1), (5, 1): (5, 1),
            (0, 2): (0, 2), (1, 2): (1, 2), (2, 2): (2, 2), (3, 2): (3, 2),   # LS RS LB RB
            (4, 2): (4, 2), (5, 2): (5, 2),                                   # Menu, View
            (0, 3): (0, 3), (1, 3): (1, 3), (2, 3): (2, 3), (3, 3): (3, 3),   # LS/RS press, LT RT
            (0, 4): (0, 4), (1, 4): (1, 4), (2, 4): (3, 4), (3, 4): (3, 5),   # stick directions
            (4, 4): (2, 4), (5, 4): (2, 5),
            (0, 5): (0, 5), (1, 5): (1, 5),
            (4, 5): (0, 6), (5, 5): (1, 6),                                   # white A B
            (0, 12): (4, 4), (1, 12): (5, 4),                                 # LS, one arrow
        },
        "half": {(2, 12): ("left", (0, 5)), (3, 12): ("right", (0, 5))},     # RS, one arrow
    },
    # RE2 (ray-traced build): natives/stm/sectionroot/ui/ui0000/tex/ui0000_iam.tex.34.x64
    "re2": {
        "cells": {
            (0, 0): (0, 0), (1, 0): (1, 0), (2, 0): (2, 0), (3, 0): (3, 0),   # A B X Y
            (4, 0): (4, 0), (5, 0): (5, 0),                                   # d-pad, all directions
            (0, 1): (0, 1), (1, 1): (1, 1), (2, 1): (2, 1), (3, 1): (3, 1),   # d-pad directions
            (4, 1): (4, 1), (5, 1): (5, 1),
            (0, 2): (0, 2), (1, 2): (1, 2), (2, 2): (2, 2), (3, 2): (3, 2),   # LS RS LB RB
            (4, 2): (4, 2), (5, 2): (5, 2),                                   # Menu, View
            (0, 3): (0, 3), (1, 3): (1, 3), (2, 3): (2, 3), (3, 3): (3, 3),   # LS/RS press, LT RT
            (0, 4): (0, 4), (1, 4): (1, 4), (2, 4): (2, 4), (3, 4): (3, 4),   # LS directions
            (4, 4): (4, 4), (5, 4): (5, 4),
            (0, 5): (0, 5), (1, 5): (1, 5), (2, 5): (2, 5), (3, 5): (3, 5),   # RS directions
            (0, 6): (0, 6), (1, 6): (1, 6), (2, 6): (2, 6), (3, 6): (3, 6),   # white A B X Y
        },
    },
    # RE3 (ray-traced build): natives/stm/escape/ui/ui0000/tex/ui0000_iam.tex.34.stm. Same
    # layout as RE2, but row 6 is dark (not white) A B X Y, plus dark LT RT.
    "re3": {
        "cells": {
            (0, 0): (0, 0), (1, 0): (1, 0), (2, 0): (2, 0), (3, 0): (3, 0),   # A B X Y
            (4, 0): (4, 0), (5, 0): (5, 0),                                   # d-pad, all directions
            (0, 1): (0, 1), (1, 1): (1, 1), (2, 1): (2, 1), (3, 1): (3, 1),   # d-pad directions
            (4, 1): (4, 1), (5, 1): (5, 1),
            (0, 2): (0, 2), (1, 2): (1, 2), (2, 2): (2, 2), (3, 2): (3, 2),   # LS RS LB RB
            (4, 2): (4, 2), (5, 2): (5, 2),                                   # Menu, View
            (0, 3): (0, 3), (1, 3): (1, 3), (2, 3): (2, 3), (3, 3): (3, 3),   # LS/RS press, LT RT
            (0, 4): (0, 4), (1, 4): (1, 4), (2, 4): (2, 4), (3, 4): (3, 4),   # LS directions
            (4, 4): (4, 4), (5, 4): (5, 4),
            (0, 5): (0, 5), (1, 5): (1, 5), (2, 5): (2, 5), (3, 5): (3, 5),   # RS directions
            (0, 6): (0, 0), (1, 6): (1, 0), (2, 6): (2, 0), (3, 6): (3, 0),   # dark A B X Y
            (4, 6): (2, 3), (5, 6): (3, 3),                                   # dark LT RT
        },
    },
    # Village: natives/stm/gui/ui0000/tex/ui0000_iam.tex.30.x64 (the copy in patch_006)
    "re8": {
        "cells": {
            (0, 0): (0, 0), (1, 0): (1, 0), (2, 0): (2, 0), (3, 0): (3, 0),   # A B X Y
            (4, 0): (4, 0), (5, 0): (5, 0),                                   # d-pad, all directions
            (6, 0): (0, 1), (7, 0): (1, 1), (8, 0): (2, 1), (9, 0): (3, 1),   # d-pad up down left right
            (10, 0): (4, 1), (11, 0): (5, 1),                                 # left+right, up+down
            (0, 1): (0, 2), (1, 1): (0, 4), (2, 1): (1, 4), (3, 1): (2, 4),   # LS and its directions
            (4, 1): (3, 4), (5, 1): (4, 4), (6, 1): (5, 4), (7, 1): (0, 3),   # ..., LS press
            (8, 1): (2, 2), (9, 1): (3, 2), (10, 1): (5, 2), (11, 1): (4, 2), # LB RB View Menu
            (0, 2): (1, 2), (1, 2): (0, 5), (2, 2): (1, 5), (3, 2): (2, 5),   # RS and its directions
            (4, 2): (3, 5), (7, 2): (1, 3),                                   # ..., RS press
            (8, 2): (2, 3), (9, 2): (3, 3),                                   # LT RT
            (0, 3): (0, 6), (1, 3): (1, 6),                                   # white A B
            (7, 3): (4, 5), (8, 3): (4, 6),                                   # white LB RB
        },
        "half": {(5, 2): ("left", (0, 5)), (6, 2): ("right", (0, 5))},       # RS, one arrow
    },
}


def read_tex(path):
    data = open(path, "rb").read()
    if data[:4] != b"TEX\0":
        raise SystemExit(f"{path}: not an RE Engine texture")
    width, height = struct.unpack_from("<HH", data, 8)
    fmt = struct.unpack_from("<I", data, 0x10)[0]
    if fmt not in (98, 99):
        raise SystemExit(f"{path}: format {fmt}, expected BC7 (98/99)")
    offset, pitch, size = struct.unpack_from("<QII", data, 0x28)
    return data, width, height, offset, pitch, size


def decode(path):
    data, width, height, offset, pitch, size = read_tex(path)
    w, h = pitch // 16 * 4, size // pitch * 4           # rows may be padded past the width
    raw = data[offset:offset + size]
    img = Image.frombytes("RGBA", (w, h), texture2ddecoder.decode_bc7(raw, w, h), "raw", "BGRA")
    return img.crop((0, 0, width, height))


def build(game, atlas_path, out_path):
    spec = GAMES[game]
    data, width, height, offset, pitch, size = read_tex(atlas_path)
    sheet = Image.open(SHEET).convert("RGBA")
    blocks = bytearray(data[offset:offset + size])
    per_row = pitch // 16
    cells = dict(spec["cells"])
    cells.update({k: v[1] for k, v in spec.get("half", {}).items()})
    for (cx, cy), (sx, sy) in cells.items():
        icon = sheet.crop((sx * CELL, sy * CELL, (sx + 1) * CELL, (sy + 1) * CELL))
        keep = spec.get("half", {}).get((cx, cy), (None,))[0]
        if keep:                                       # erase the other side's arrow
            px = icon.load()
            for x in range(CELL):
                if (keep == "left" and x >= 64) or (keep == "right" and x < 16):
                    for y in range(CELL):
                        px[x, y] = (0, 0, 0, 0)
        encoded = etcpak.compress_bc7(icon.tobytes("raw", "RGBA"), CELL, CELL)
        n = CELL // 4
        for by in range(n):
            dst = ((cy * n + by) * per_row + cx * n) * 16
            blocks[dst:dst + n * 16] = encoded[by * n * 16:(by + 1) * n * 16]
    with open(out_path, "wb") as f:
        f.write(data[:offset] + bytes(blocks) + data[offset + size:])
    return len(cells)


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in GAMES:
        raise SystemExit(__doc__)
    n = build(*sys.argv[1:])
    print(f"wrote {sys.argv[3]}: {n} icons replaced")
