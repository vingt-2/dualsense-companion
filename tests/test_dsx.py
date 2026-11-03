"""Self-test of DSX-mod support (dsx.py) without a game or a controller:
python tests\\test_dsx.py"""
import json
import os
import socket
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()   # don't touch the user's files
import dsx
from dsx import OFF, encode_trigger, parse
from dualsense_usb import WiredDualSense
from link_stats import LinkStats

PORT = 16969
H = bytes.fromhex


class FakeBluetooth:
    on_input = on_mic = None
    headset = False
    speaker_format = 0x39
    link = LinkStats()
    dev = path = "fake"

    def __init__(self):
        self.outputs = []

    def write_usb_output(self, report):
        self.outputs.append(bytes(report))

    def write_media(self, block, frame=None):
        pass

    def set_mic(self, on):
        pass

    def get_feature(self, rid, size):
        return bytes([rid, 0x66, 0x55, 0x44, 0x33, 0x22, 0x11]) + bytes(size - 7)


def packet(*instructions):
    return json.dumps({"instructions": [{"type": t, "parameters": list(p)}
                                        for t, *p in instructions]})


def trigger(side, mode, *params):
    return (1, 0, side, mode, *params)


# The RE4 Remake mod (nexus 5813): weapon class -> L2, R2, RGB, as its Lua sends them.
RE4 = {
    "default": (trigger(1, 13, 0, 3), trigger(2, 0), (2, 0, 0, 0, 0)),
    "hg": (trigger(1, 13, 0, 3), trigger(2, 2, 0, 9, 8), (2, 0, 0, 120, 255)),
    "xbow": (trigger(1, 13, 0, 5), trigger(2, 2, 5, 9, 6), (2, 0, 0, 255, 255)),
    "sg": (trigger(1, 13, 0, 6), trigger(2, 3, 0, 6, 8, 8), (2, 0, 255, 40, 40)),
    "mag": (trigger(1, 13, 0, 6), trigger(2, 3, 0, 8, 8, 8), (2, 0, 180, 0, 255)),
    "smg": (trigger(1, 13, 0, 2), trigger(2, 8, 20), (2, 0, 255, 140, 0)),
    "sr": (trigger(1, 13, 0, 6), trigger(2, 3, 0, 8, 8, 8), (2, 0, 255, 255, 0)),
    "grenade": (trigger(1, 13, 0, 8), trigger(2, 13, 0, 4), (2, 0, 0, 255, 0)),
    "knf": (trigger(1, 13, 0, 1), trigger(2, 0), (2, 0, 255, 255, 255)),
    "empty": (trigger(2, 1, 0, 8),),
    "disabled": (trigger(1, 0), trigger(2, 0), (2, 0, 0, 0, 0)),
}

# Resistance(start 0, force f): mode 0x21, all ten zones, force-1 in each 3-bit zone
def resistance(force):
    zones = sum((force - 1) << (3 * i) for i in range(10))
    return bytes([0x21, 0xFF, 0x03]) + zones.to_bytes(4, "little") + bytes(4)


VERY_SOFT = H("0280a0ff00000000000000")
SOFT = H("2145a0ff00000000000000")
GAMECUBE = H("0290a0ff00000000000000")
RE4_EXPECT = {     # L2, R2, RGB after each payload (empty-ammo keeps L2 and RGB)
    "default": (resistance(3), OFF, (0, 0, 0)),
    "hg": (resistance(3), VERY_SOFT, (0, 120, 255)),
    "xbow": (resistance(5), VERY_SOFT, (0, 255, 255)),
    "sg": (resistance(6), SOFT, (255, 40, 40)),
    "mag": (resistance(6), SOFT, (180, 0, 255)),
    "smg": (resistance(2), H("26ff03ffffff3f00001400"), (255, 140, 0)),
    "sr": (resistance(6), SOFT, (255, 255, 0)),
    "grenade": (resistance(8), resistance(4), (0, 255, 0)),
    "knf": (resistance(1), OFF, (255, 255, 255)),
    "empty": (resistance(1), GAMECUBE, (255, 255, 255)),
    "disabled": (OFF, OFF, (0, 0, 0)),
}


def check_report(report, l2, r2, rgb):
    assert report[0] == 0x02 and len(report) == 48, report.hex()
    assert report[dsx.L2_EFFECT:dsx.L2_EFFECT + 11] == l2, report[22:33].hex()
    assert report[dsx.R2_EFFECT:dsx.R2_EFFECT + 11] == r2, report[11:22].hex()
    assert tuple(report[45:48]) == rgb, tuple(report[45:48])
    assert report[1] & 0x0C == 0x0C and report[2] & 0x04, report[:3].hex()


def test_encoding():
    assert resistance(8) == H("21ff03ffffff3f00000000")
    assert encode_trigger(13, [0, 8]) == resistance(8)
    assert encode_trigger(21, [0, 8]) == resistance(8)
    assert encode_trigger(13, [3, 6]) == H("21f80300dab62d00000000")
    assert encode_trigger(17, [0, 6, 12]) == H("26ff036ddbb62d00000c00")
    assert encode_trigger(17, [0, 5, 30]) == encode_trigger(23, [0, 5, 30]) == H("26ff0324499224 00001e00".replace(" ", ""))
    assert encode_trigger(8, [10]) == H("26ff03ffffff3f00000a00") == encode_trigger(19, [])
    assert encode_trigger(8, []) == encode_trigger(8, [10])
    assert encode_trigger(14, [0, 8, 2, 5]) == H("22010121000000000000 00".replace(" ", ""))
    assert encode_trigger(15, [0, 9, 2, 4, 10]) == H("2301021 40a000000000000".replace(" ", ""))
    assert encode_trigger(16, [2, 7, 8]) == encode_trigger(22, [2, 7, 8]) == H("25840007000000000000 00".replace(" ", ""))
    assert encode_trigger(18, [0, 9, 7, 7, 10, 0]) == H("2701023f0a000000000000")
    assert encode_trigger(24, [1, 9, 8, 1]) == H("21fe03b8cb4d0100000000")
    assert encode_trigger(25, [8, 8, 8, 0, 0, 0, 8, 8, 0, 0]) == H("21c700ff01fc0000000000")
    assert encode_trigger(26, [10, 8, 8, 8, 8, 8, 0, 0, 0, 8, 8]) == H("261f03ff7f003f00000a00")
    # presets (DualSenseY-v2's bytes); extra parameters are ignored
    assert encode_trigger(1, []) == GAMECUBE and encode_trigger(2, [0, 9, 8]) == VERY_SOFT
    assert encode_trigger(3, []) == SOFT
    assert encode_trigger(4, []) == H("2120a0ffffffffff000000")
    assert encode_trigger(5, []) == H("2110a0ffffffffff000000")
    assert encode_trigger(6, []) == H("0200ffffffffffff000000")
    assert encode_trigger(7, []) == H("0100ff00000000000000 00".replace(" ", ""))
    assert encode_trigger(9, []) == H("21022721272602000000 00".replace(" ", ""))
    assert encode_trigger(10, []) == H("22022301060601210000 00".replace(" ", ""))
    assert encode_trigger(11, []) == H("27252306272123220000 00".replace(" ", ""))
    assert encode_trigger(0, []) == encode_trigger(20, []) == OFF
    # CustomTriggerValue: values 1-6 to bytes 1-6, the seventh to byte 9
    modes = [0x00, 0x01, 0x21, 0x05, 0x25, 0x02, 0x22, 0x06, 0x26,
             0x06, 0x26, 0x06, 0x26, 0x27, 0x27, 0x27, 0x27]
    for n, mode in enumerate(modes):
        assert encode_trigger(12, [n, 1, 2, 3, 4, 5, 6, 7]) == bytes([mode, 1, 2, 3, 4, 5, 6, 0, 0, 7, 0])
    assert encode_trigger(12, [9, 40, 200]) == H("0628c800000000000000 00".replace(" ", ""))
    # zero strength / frequency: off; out of range or unknown: None (keep what was there)
    for mode, p in [(13, [4, 0]), (16, [2, 7, 0]), (17, [0, 0, 30]), (8, [0]), (14, [0, 8, 0, 5]),
                    (15, [0, 9, 2, 4, 0]), (18, [0, 9, 7, 7, 0, 0])]:
        assert encode_trigger(mode, p) == OFF, (mode, p)
    for mode, p in [(13, [10, 8]), (13, [0, 9]), (13, [0]), (16, [1, 7, 8]), (14, [5, 2, 3, 3]),
                    (27, []), (99, [1])]:
        assert encode_trigger(mode, p) is None, (mode, p)


def test_parsing():
    assert parse(b'{"instructions":[{"type":1,"parameters":[0,2,13,0,8]}]}') == [(1, [0, 2, 13, 0, 8])]
    assert parse('{"Instructions":[{"Type":"TriggerUpdate","Parameters":["0","2","13","0","8"]}]}') \
        == [(1, [0, 2, 13, 0, 8])]
    assert parse(b'{"instructions":[{"type":"Invalid"},{"type":0,"parameters":null},{"type":7.0}]}') \
        == [(0, []), (0, []), (7, [])]
    assert parse('\ufeff{"instructions":[{"type":2,"parameters":[0,1,2,3]},]}\0\0') == [(2, [0, 1, 2, 3])]
    assert parse(b'{"instructions":[{"type":3,"parameters":[0,true,false,"1","true",12.9,-3,null,{},[1],"Left"]}]}') \
        == [(3, [0, 1, 0, 1, 1, 12, -3, 0, 0, 0, 0])]
    assert parse(b'{"instructions":[{"type":"Bogus"},5,{"parameters":[0]},{"type":5,"parameters":[0,0]}]}') \
        == [(5, [0, 0])]
    for bad in (b"", b"   ", b'{"instructions":{}}', b"[1]", b"not json", b'{"instructions":[{"type":1'):
        assert parse(bad) is None, bad


def test_overrides():
    o = dsx.Overrides()
    o.apply(parse(packet((6, 0, 2), (5, 0, 1), (3, 0, 1, 0, 1, 0, 1))), "t")
    assert o.player == 0b10101 and o.mic == 2
    o.apply(parse(packet((6, 0, 5), (5, 0, 2), (2, 0, 255, 128, 0, 128))), "t")
    assert o.player == 0 and o.mic == 0 and o.rgb == (128, 64, 0)
    assert not o.apply(parse(packet((2, 1, 9, 9, 9))), "t")          # controller 1: not ours
    assert o.apply(parse(packet((2, -1, 9, 9, 9))), "t")             # -1: all controllers
    before = o.r2
    o.apply(parse(packet(trigger(2, 13, 0, 8))), "t")
    effect = o.r2
    o.apply(parse(packet(trigger(2, 13, 12, 8), trigger(3, 13, 0, 8))), "t")   # bad: kept
    assert o.r2 == effect != before
    o.apply(parse(packet((7, 0))), "t")
    assert not o.active and o.source is None


def test_threshold():
    o = dsx.Overrides()
    report = bytearray(64)
    report[0], report[5], report[6], report[9] = 0x01, 100, 100, 0x0C   # L2, R2 half pressed
    assert o.filter_input(bytes(report)) == bytes(report)               # no threshold
    o.apply(parse(packet((4, 0, 2, 120))), "t")
    out = o.filter_input(bytes(report))
    assert out[5] == 100 and out[6] == 0 and out[9] == 0x04, out[:10].hex()   # R2 below 120
    report[6] = 120
    out = o.filter_input(bytes(report))
    assert out[6] == 120 and out[9] == 0x0C                                   # at the point
    o.apply(parse(packet((4, 0, 2, 0))), "t")
    report[6] = 5
    assert o.filter_input(bytes(report)) == bytes(report)                     # 0 = none

    # through the emulated controller's input path
    dev = WiredDualSense(FakeBluetooth())
    dev.dsx.apply(parse(packet((4, 0, 1, 200))), "t")
    report[5] = 150
    dev._on_bt_input(bytes(report))
    assert dev._latest[5] == 0 and not dev._latest[9] & 0x04


def test_udp():
    bt = FakeBluetooth()
    dev = WiredDualSense(bt)
    latest = bytearray(dev._latest)
    latest[53] = 0x07                         # battery 70 %
    dev._latest = bytes(latest)
    server = dsx.DsxServer(dev.dsx, dev.dsx_status, port=PORT, owners=lambda: {},
                           port_files=False)
    server.start()
    deadline = time.monotonic() + 5
    while not server.listening:
        assert time.monotonic() < deadline, "server did not start"
        time.sleep(0.02)
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(2)
    try:
        def send(text):
            client.sendto(text.encode() if isinstance(text, str) else text, ("127.0.0.1", PORT))
            reply = json.loads(client.recv(65535))
            assert reply["Status"] == "DSX Received UDP Instructions", reply
            return reply

        reply = send(packet((0, 0)))
        assert reply["isControllerConnected"] is True and reply["BatteryLevel"] == 70, reply
        d = reply["Devices"][0]
        assert d["Index"] == 0 and d["DeviceType"] == 0 and d["ConnectionType"] == 0, d
        assert d["MacAddress"] == "11:22:33:44:55:66" and d["IsSupportAT"] is True, d
        assert {"TimeReceived", "IsSupportLightBar", "IsSupportPlayerLED", "IsSupportMicLED"} <= \
            set(reply) | set(d)
        send(b"garbage")                      # still answered
        # Bluetooth: before the first colour on a connection, the lightbar is handed over
        bt.outputs.clear()
        send(packet((2, 0, 0, 255, 40)))
        setup, colour = bt.outputs[-2], bt.outputs[-1]
        assert setup[0] == 0x02 and setup[39] == 0x02 and setup[42] == 0x02, setup.hex()
        assert not any(setup[1:39]) and setup[45:48] == bytes(3), setup.hex()
        assert colour[2] & 0x04 and colour[45:48] == bytes([0, 255, 40]), colour.hex()
        bt.outputs.clear()
        send(packet((2, 0, 255, 0, 0)))       # only once per connection
        assert len(bt.outputs) == 1 and bt.outputs[0][45:48] == bytes([255, 0, 0])
        send(packet((7, 0)))
        for weapon, instructions in RE4.items():
            bt.outputs.clear()
            send(packet(*instructions))
            assert bt.outputs, f"{weapon}: no report sent on change"
            check_report(bt.outputs[-1], *RE4_EXPECT[weapon])
            # the game's own reports (rumble here) get the same overrides patched in
            game = bytearray(48)
            game[0], game[1], game[3], game[4] = 0x02, 0x03, 0x40, 0x80
            dev._output(bytes(game))
            out = bt.outputs[-1]
            check_report(out, *RE4_EXPECT[weapon])
            assert out[1] & 0x03 == 0x03 and out[3:5] == bytes([0x40, 0x80]), out[:5].hex()
        bt.outputs.clear()
        send(packet(*RE4["disabled"]))        # heartbeat with nothing new: no extra report
        assert not bt.outputs
        assert dev.dsx.source == "UDP port %d" % client.getsockname()[1]
        send(packet((7, 0)))                  # reset: triggers off, then the game's state back
        assert not dev.dsx.active
        assert bt.outputs[-2][11:22] == OFF and bt.outputs[-2][22:33] == OFF
        assert bt.outputs[-1] == bytes(game)
    finally:
        client.close()
        server.stop()


def test_udp_sender_gone():
    o = dsx.Overrides()
    alive = {"v": True}
    server = dsx.DsxServer(o, lambda: {"connected": False}, port=PORT + 1,
                           owners=lambda: {}, alive=lambda pid: alive["v"], port_files=False)
    server._owners = lambda: {12345: 4242}
    server._names = lambda pid: "mod.exe"
    server._sender(("127.0.0.1", 12345))
    o.apply(parse(packet(trigger(2, 7))), server._source[0])
    assert o.source == "mod.exe (UDP)"
    threading.Thread(target=server._watch_sender, daemon=True).start()
    time.sleep(1.3)
    assert o.active                           # sender still running
    alive["v"] = False
    time.sleep(1.3)
    assert not o.active, "effects not released when the sender exited"
    server.stop()
    assert json.loads(server.reply()) ["isControllerConnected"] is False


def test_payload_file():
    game = tempfile.mkdtemp()
    folder = os.path.join(game, "reframework", "data", "DualSenseX")
    os.makedirs(folder)
    payload = os.path.join(folder, "payload.json")
    bt = FakeBluetooth()
    dev = WiredDualSense(bt)
    watcher = dsx.PayloadWatcher(dev.dsx)
    running = threading.Event()
    running.set()
    t = threading.Thread(target=watcher.watch, args=(game, "re4.exe (payload file)", running.is_set))
    t.start()

    def write(text, wait=True):
        with open(payload, "w", encoding="utf-8") as f:
            f.write(text)
        if wait:
            time.sleep(0.25)

    try:
        for weapon in ("default", "hg", "sg"):
            write("", wait=False)            # the writer truncates, then rewrites
            time.sleep(0.15)
            write(packet(*RE4[weapon]))
            check_report(bt.outputs[-1], *RE4_EXPECT[weapon])
            assert dev.dsx.source == "re4.exe (payload file)"
        write('{"instructions":[{"type":1,"param')   # half-written: ignored, retried
        check_report(bt.outputs[-1], *RE4_EXPECT["sg"])
        write(packet(*RE4["smg"]))
        check_report(bt.outputs[-1], *RE4_EXPECT["smg"])
    finally:
        running.clear()
        t.join(2)
    assert not dev.dsx.active, "effects not released when the game exited"
    assert bt.outputs[-1][11:22] == OFF

    # the scanner finds the game from its exe path
    exe = os.path.join(game, "re4.exe")
    w = dsx.PayloadWatcher(dsx.Overrides(), processes=lambda: {77: "re4.exe", 78: "other.exe"},
                           path_of=lambda pid: exe if pid == 77 else r"C:\Elsewhere\other.exe",
                           alive=lambda pid: False)
    w.scan()
    assert w._folders == {game: dsx.PAYLOAD_PATHS, r"C:\Elsewhere": []}, w._folders

    # a mod installed between two runs of the game: the next run is watched
    fresh = tempfile.mkdtemp()
    procs = {90: "re4.exe"}
    started = []
    w = dsx.PayloadWatcher(dsx.Overrides(), processes=lambda: procs,
                           path_of=lambda pid: os.path.join(fresh, "re4.exe"),
                           alive=lambda pid: False)
    w.watch = lambda *a: started.append(a)
    w.scan()
    assert not started                              # no reframework folder yet: nothing to watch
    os.makedirs(os.path.join(fresh, "reframework", "autorun"))
    procs.clear(); procs[91] = "re4.exe"            # the game restarted after the install
    w.scan()
    assert started and started[0][0] == fresh, started

    # our scripts' "controllerSeen" reaches the tray with the game's exe name
    told = []
    o = dsx.Overrides()
    running.set()
    w = dsx.PayloadWatcher(o, on_controller_seen=lambda src, exe, seen: told.append((exe, seen)))
    t = threading.Thread(target=w.watch, args=(game, "re7.exe (payload file)", running.is_set))
    t.start()
    try:
        time.sleep(0.15)
        with open(payload, "w") as f:
            f.write('{"instructions":[{"type":7,"parameters":[0]}],"controllerSeen":false}')
        time.sleep(0.25)
    finally:
        running.clear()
        t.join(2)
    assert ("re7.exe", False) in told, told

    # two mods' files in one game: both are followed
    ours = os.path.join(game, "reframework", "data", "DualSenseCompanion")
    os.makedirs(ours)
    o = dsx.Overrides()
    running.set()
    w = dsx.PayloadWatcher(o)
    t = threading.Thread(target=w.watch, args=(game, "re4.exe (payload file)", running.is_set))
    t.start()
    try:
        time.sleep(0.2)
        with open(os.path.join(ours, "re4_triggers.json"), "w") as f:
            f.write(packet((7, 0), trigger(2, 22, 3, 6, 8), (4, 0, 2, 190)))
        time.sleep(0.25)
        assert o.r2 == encode_trigger(22, [3, 6, 8]) and o.thresholds[dsx.R2] == 190, o.r2
    finally:
        running.clear()
        t.join(2)


def test_game_suggestions():
    import game_mods
    game = tempfile.mkdtemp()
    exe = os.path.join(game, "re4.exe")
    assert game_mods.suggestion(exe)["name"] == "Resident Evil 4"     # no mod: suggest it
    assert game_mods.suggestion(os.path.join(game, "other.exe")) is None
    autorun = os.path.join(game, "reframework", "autorun")
    os.makedirs(autorun)
    open(os.path.join(autorun, "dualsense_companion_re4.lua"), "w").close()
    assert game_mods.suggestion(exe) is None                          # installed: quiet
    # the payload watcher's scan reports each new process once
    seen = []
    w = dsx.PayloadWatcher(dsx.Overrides(), processes=lambda: {5: "re4.exe"},
                           path_of=lambda pid: exe, alive=lambda pid: False,
                           on_process=lambda pid, path: seen.append((pid, path)))
    w.scan()
    w.scan()
    assert seen == [(5, exe)], seen


def test_port_files():
    root = tempfile.mkdtemp()
    legacy = os.path.join(root, "Temp", "DualSenseX", "DualSenseX_PortNumber.txt")
    current = os.path.join(root, "DSX", "DSX_UDP_PortNumber.txt")
    dsx.write_port_files(legacy=legacy, current=current, running={1: "DSX.exe"})
    assert not os.path.exists(legacy) and not os.path.exists(current)   # real DSX: hands off
    dsx.write_port_files(legacy=legacy, current=current, running={1: "game.exe"})
    assert open(legacy).read() == "6969" and not os.path.exists(current)
    os.makedirs(os.path.dirname(current))
    with open(current, "w") as f:
        f.write("7000")
    dsx.write_port_files(legacy=legacy, current=current, running={1: "DSX.exe"})
    assert open(current).read() == "7000"
    dsx.write_port_files(legacy=legacy, current=current, running={1: "game.exe"})
    assert open(current).read() == "6969"


def test_legacy_payload_paths():
    """Our scripts from before the rename (DualSense Bridge) are still followed."""
    for key in ("re4", "re7", "re2", "re3", "re8"):
        assert "reframework\\data\\DualSenseCompanion\\%s_triggers.json" % key in dsx.PAYLOAD_PATHS
        assert "reframework\\data\\DualSenseBridge\\%s_triggers.json" % key in dsx.PAYLOAD_PATHS


def main():
    test_encoding()
    test_parsing()
    test_overrides()
    test_threshold()
    test_udp()
    test_udp_sender_gone()
    test_payload_file()
    test_game_suggestions()
    test_port_files()
    test_legacy_payload_paths()
    print("OK: DSX trigger encoding, parsing, UDP replies and overrides, payload files, "
          "port files and thresholds all pass")


if __name__ == "__main__":
    main()
