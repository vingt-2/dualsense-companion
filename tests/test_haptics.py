"""Haptics conversion and rumble flags, no controller needed:
python tests\\test_haptics.py"""
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from haptics import HapticsConverter, to_int8
from dualsense_usb import normalize_rumble


def level(freq, peak):
    """Output RMS / input RMS for a 1 s tone through the converter."""
    out = []
    c = HapticsConverter(out.append)
    frames = [(int(peak * math.sin(2 * math.pi * freq * i / 48000)),) * 2 for i in range(48000)]
    c.feed(frames)
    v = [s for b in out for s in struct.unpack(f"{len(b)}b", b)][0::2]
    rin = math.sqrt(sum(f[0] ** 2 for f in frames) / len(frames)) / 256
    return math.sqrt(sum(x * x for x in v) / len(v)) / rin if v else 0.0


def test_rounding():
    assert [to_int8(v) for v in (0.4, 0.5, 1.49, -0.4, -0.5, -1.6, 127.99, -128.0, -200)] == \
        [0, 1, 1, 0, -1, -2, 127, -128, -128]
    # quiet effects keep their strength (truncating lost 10-20 % and silenced ~1.5 %)
    for peak in (2000, 1000, 500):
        assert 0.9 < level(150, peak) < 1.1, (peak, level(150, peak))
    assert level(150, 32767) > 0.97
    # the game's +-1 noise floor still counts as silence: nothing is sent after the tail
    out = []
    c = HapticsConverter(out.append)
    c.feed([((-1) ** i, (-1) ** i) for i in range(48000)])
    assert not out, len(out)


def test_rumble_flags():
    def payload(flag0, flag2=0, motors=(11, 15)):
        p = bytearray(47); p[0] = flag0; p[2], p[3] = motors; p[38] = flag2
        return bytes(p)
    # only an enable bit (Death Stranding's landings): passed through as a wired controller
    # sees it, which doesn't switch it out of audio haptics
    for v2 in (True, False):
        assert normalize_rumble(payload(0x01), v2) == payload(0x01)
        assert normalize_rumble(payload(0x00, 0x04), v2) == payload(0x00, 0x04)
    # classic rumble the game selected: rewritten for the firmware
    assert normalize_rumble(payload(0x03), True) == payload(0x02, 0x04)
    assert normalize_rumble(payload(0x02, 0x04), False) == payload(0x03, 0x00)
    assert normalize_rumble(payload(0x02, 0x04), True) == payload(0x02, 0x04)
    assert normalize_rumble(payload(0x03), False) == payload(0x03)


def main():
    test_rumble_flags()
    test_rounding()
    print("OK: rumble flags as a wired controller sees them, haptics rounding keeps quiet effects")


if __name__ == "__main__":
    main()
