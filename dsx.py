"""Stand-in for DualSenseX (DSX), so DSX game mods drive the triggers and lights.

Mods talk to DSX in one of two ways, and the app answers both:
  * UDP JSON to 127.0.0.1:6969, with a reply to every packet (DsxServer);
  * a payload file written next to the game for a helper exe to forward (PayloadWatcher).

Both feed one Overrides object, which WiredDualSense patches into every output report the
game sends (games also write report 0x02 for rumble and lights, which would otherwise reset
the triggers). See reference/dsx-mods.md.

Sources: the instruction set, trigger modes and reply follow the DSX mod examples
(Paliverse); the named preset trigger patterns are DualSenseY-v2's
(source/scePadCustomTriggers.cpp, MIT, (c) 2026 WujekFoliarz); the parametric modes follow
Nielk1's TriggerEffectGenerator (MIT, (c) 2021-2022 John "Nielk1" Klein).
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import socket
import struct
import threading
import time

PORT = 6969
REPLY_STATUS = "DSX Received UDP Instructions"
UDP_IDLE = 15.0          # s without packets before a UDP mod whose process can't be found lets go
LEGACY_PORT_FILE = r"C:\Temp\DualSenseX\DualSenseX_PortNumber.txt"            # v2 mods
CURRENT_PORT_FILE = os.path.join(os.environ.get("LOCALAPPDATA", "."), "DSX",
                                 "DSX_UDP_PortNumber.txt")                     # v3.1 mods

# Payload files some mods write for a helper exe, relative to the game exe's folder.
# A new mod is one more line here.
PAYLOAD_PATHS = [
    r"reframework\data\DualSenseX\payload.json",   # lunati_'s REFramework mods (RE4 Remake, ...)
    r"reframework\data\DualSenseCompanion\re4_triggers.json",   # our RE4 Remake script (mods/re4-remake)
    r"reframework\data\DualSenseCompanion\re7_triggers.json",   # our RE7 script (mods/re7)
    r"reframework\data\DualSenseCompanion\re2_triggers.json",   # our RE2 script (mods/re2)
    r"reframework\data\DualSenseCompanion\re3_triggers.json",   # our RE3 script (mods/re3)
    r"reframework\data\DualSenseCompanion\re8_triggers.json",   # our Village script (mods/re8)
]
# Our scripts from before the rename (DualSense Bridge): still followed, so an existing
# install keeps working until the app moves it over (mod_installer.migrate).
PAYLOAD_PATHS += [p.replace("DualSenseCompanion", "DualSenseBridge") for p in PAYLOAD_PATHS
                  if "DualSenseCompanion" in p]

# -- instructions -------------------------------------------------------------------------
GET_STATUS, TRIGGER, RGB, PLAYER_LED, THRESHOLD, MIC_LED, PLAYER_LED_NEW, RESET = range(8)
TYPE_NAMES = ["getdsxstatus", "triggerupdate", "rgbupdate", "playerled", "triggerthreshold",
              "micled", "playerlednewrevision", "resettousersettings"]
L2, R2 = 1, 2

MODE_NAMES = [
    "Normal", "GameCube", "VerySoft", "Soft", "Hard", "VeryHard", "Hardest", "Rigid",
    "VibrateTrigger", "Choppy", "Medium", "VibrateTriggerPulse", "CustomTriggerValue",
    "Resistance", "Bow", "Galloping", "SemiAutomaticGun", "AutomaticGun", "Machine",
    "VIBRATE_TRIGGER_10Hz", "OFF", "FEEDBACK", "WEAPON", "VIBRATION", "SLOPE_FEEDBACK",
    "MULTIPLE_POSITION_FEEDBACK", "MULTIPLE_POSITION_VIBRATION"]


def _number(v):
    """A parameter as an int, as leniently as DSX: numbers truncate, booleans are 1/0,
    numeric strings parse, anything else (null, objects, words) is 0."""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v) if v == v and abs(v) != float("inf") else 0
    if isinstance(v, str):
        s = v.strip()
        try:
            return int(float(s))
        except ValueError:
            return 1 if s.lower() == "true" else 0
    return 0


def _key(obj, name):
    for k, v in obj.items():
        if isinstance(k, str) and k.lower() == name:
            return v
    return None


def parse(data):
    """A datagram or payload file -> [(type, [int params])], or None if it isn't one.
    Instructions whose type can't be read are skipped; the rest are kept in order."""
    if isinstance(data, (bytes, bytearray)):
        data = bytes(data).decode("utf-8", "replace")
    text = data.strip("\0 \t\r\n\ufeff")
    if not text:
        return None
    try:
        root = json.loads(text)
    except ValueError:
        try:   # trailing commas, as some hand-written mods send
            root = json.loads(re.sub(r",\s*([\]}])", r"\1", text))
        except ValueError:
            return None
    if not isinstance(root, dict):
        return None
    items = _key(root, "instructions")
    if not isinstance(items, list):
        return None
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        t = _key(item, "type")
        if isinstance(t, str):
            name = t.strip().lower()
            if name in TYPE_NAMES:
                t = TYPE_NAMES.index(name)
            elif name == "invalid":         # the v2 example's unused slots
                t = GET_STATUS
            else:
                try:
                    t = int(float(name))
                except ValueError:
                    continue
        elif isinstance(t, (int, float)) and not isinstance(t, bool):
            t = int(t)
        else:
            continue
        params = _key(item, "parameters")
        out.append((t, [_number(p) for p in params] if isinstance(params, list) else []))
    return out


# -- trigger effects (11 bytes: mode + 10 parameters) -------------------------------------
OFF = bytes([0x05]) + bytes(10)
_FEEDBACK, _BOW, _GALLOP, _WEAPON, _VIBRATION, _MACHINE = 0x21, 0x22, 0x23, 0x25, 0x26, 0x27

# The named presets DSX never published, as DualSenseY-v2 sends them.
PRESETS = {
    1: (0x02, 144, 160, 255, 0, 0, 0, 0, 0, 0, 0),              # GameCube
    2: (0x02, 128, 160, 255, 0, 0, 0, 0, 0, 0, 0),              # VerySoft
    3: (0x21, 69, 160, 255, 0, 0, 0, 0, 0, 0, 0),               # Soft
    4: (0x21, 32, 160, 255, 255, 255, 255, 255, 0, 0, 0),       # Hard
    5: (0x21, 16, 160, 255, 255, 255, 255, 255, 0, 0, 0),       # VeryHard
    6: (0x02, 0, 255, 255, 255, 255, 255, 255, 0, 0, 0),        # Hardest
    7: (0x01, 0, 255, 0, 0, 0, 0, 0, 0, 0, 0),                  # Rigid
    9: (0x21, 2, 39, 33, 39, 38, 2, 0, 0, 0, 0),                # Choppy
    10: (0x22, 2, 35, 1, 6, 6, 1, 33, 0, 0, 0),                 # Medium
    11: (0x27, 37, 35, 6, 39, 33, 35, 34, 0, 0, 0),             # VibrateTriggerPulse
}

# CustomTriggerValue modes 0-16: Off; Rigid and Pulse, plain / A (0x20) / B (0x04) / AB;
# then the VibrateResistance and VibratePulse variants.
CUSTOM_MODES = [0x00, 0x01, 0x21, 0x05, 0x25, 0x02, 0x22, 0x06, 0x26,
                0x06, 0x26, 0x06, 0x26, 0x27, 0x27, 0x27, 0x27]


def _zones(mode, active, values):
    b = bytearray(11)
    b[0] = mode
    struct.pack_into("<HI", b, 1, active, values)
    return b


def _feedback(position, strength):
    if position > 9 or strength > 8:
        return None
    if strength == 0:
        return bytearray(OFF)
    force = (strength - 1) & 7
    values = active = 0
    for i in range(position, 10):
        values |= force << (3 * i)
        active |= 1 << i
    return _zones(_FEEDBACK, active, values)


def _vibration(position, amplitude, frequency):
    if position > 9 or amplitude > 8:
        return None
    if amplitude == 0 or frequency == 0:
        return bytearray(OFF)
    strength = (amplitude - 1) & 7
    values = active = 0
    for i in range(position, 10):
        values |= strength << (3 * i)
        active |= 1 << i
    b = _zones(_VIBRATION, active, values)
    b[9] = frequency
    return b


def _multi_feedback(strengths):
    values = active = 0
    for i, s in enumerate(strengths[:10]):
        if s > 8:
            return None
        if s:
            values |= ((s - 1) & 7) << (3 * i)
            active |= 1 << i
    return _zones(_FEEDBACK, active, values) if active else bytearray(OFF)


def _multi_vibration(frequency, amplitudes):
    values = active = 0
    for i, a in enumerate(amplitudes[:10]):
        if a > 8:
            return None
        if a:
            values |= ((a - 1) & 7) << (3 * i)
            active |= 1 << i
    if not frequency or not active:
        return bytearray(OFF)
    b = _zones(_VIBRATION, active, values)
    b[9] = frequency
    return b


def _slope(start, end, s0, s1):
    if start > 8 or end > 9 or end <= start or not (1 <= s0 <= 8) or not (1 <= s1 <= 8):
        return None
    slope = (s1 - s0) / (end - start)
    strengths = [0] * 10
    for i in range(start, 10):
        strengths[i] = round(s0 + slope * (i - start)) if i <= end else s1   # to even, as C#
    return _multi_feedback(strengths)


def _two_points(mode, start, end):
    b = bytearray(11)
    b[0] = mode
    struct.pack_into("<H", b, 1, (1 << start) | (1 << end))
    return b


def _weapon(start, end, strength):
    if start > 7 or start < 2 or end > 8 or end <= start or strength > 8:
        return None
    if strength == 0:
        return bytearray(OFF)
    b = _two_points(_WEAPON, start, end)
    b[3] = strength - 1
    return b


def _bow(start, end, strength, snap):
    if start > 8 or end > 8 or start >= end or strength > 8 or snap > 8:
        return None
    if end == 0 or strength == 0 or snap == 0:
        return bytearray(OFF)
    b = _two_points(_BOW, start, end)
    struct.pack_into("<H", b, 3, ((strength - 1) & 7) | (((snap - 1) & 7) << 3))
    return b


def _galloping(start, end, first, second, frequency):
    if start > 8 or end > 9 or start >= end or second > 7 or first > 6 or first >= second:
        return None
    if frequency == 0:
        return bytearray(OFF)
    b = _two_points(_GALLOP, start, end)
    b[3] = (second & 7) | ((first & 7) << 3)
    b[4] = frequency
    return b


def _machine(start, end, a, b_, frequency, period):
    if start > 8 or end > 9 or end <= start or a > 7 or b_ > 7:
        return None
    if frequency == 0:
        return bytearray(OFF)
    b = _two_points(_MACHINE, start, end)
    b[3] = (a & 7) | ((b_ & 7) << 3)
    b[4], b[5] = frequency, period
    return b


def _custom(p):
    """CustomTriggerValue: custom mode, then up to seven values: 1-6 to bytes 1-6 and the
    seventh to byte 9 (where mode 0x26 reads its frequency). Missing values are 0."""
    if not p or p[0] >= len(CUSTOM_MODES):
        return None
    b = bytearray(11)
    b[0] = CUSTOM_MODES[p[0]]
    for i in range(1, 7):
        b[i] = p[i] if i < len(p) else 0
    b[9] = p[7] if len(p) > 7 else 0
    return b


# mode -> (parameters needed, encoder taking them)
_ENCODERS = {
    13: (2, _feedback), 21: (2, _feedback),
    14: (4, _bow),
    15: (5, _galloping),
    16: (3, _weapon), 22: (3, _weapon),
    17: (3, _vibration), 23: (3, _vibration),
    18: (6, _machine),
    24: (4, _slope),
    25: (10, lambda *s: _multi_feedback(s)),
    26: (11, lambda f, *a: _multi_vibration(f, a)),
}


def encode_trigger(mode, params):
    """A TriggerUpdate's mode and the parameters after the side -> 11 bytes, or None for an
    unknown mode or bad parameters (the caller then keeps the previous effect)."""
    p = [max(0, min(255, v)) for v in params]
    if mode in (0, 20):                       # Normal, OFF
        b = bytearray(OFF)
    elif mode == 8:                           # VibrateTrigger: frequency, 10 if absent
        b = _vibration(0, 8, p[0] if p else 10)
    elif mode == 19:                          # VIBRATE_TRIGGER_10Hz
        b = _vibration(0, 8, 10)
    elif mode == 12:
        b = _custom(p)
    elif mode in PRESETS:                     # presets take no parameters; extras are ignored
        b = bytearray(PRESETS[mode])
    elif mode in _ENCODERS:
        need, fn = _ENCODERS[mode]
        b = fn(*p[:need]) if len(p) >= need else None
    else:
        b = None
    return bytes(b) if b is not None else None


PLAYER_PATTERNS = [0x04, 0x0A, 0x15, 0x1B, 0x1F, 0x00]   # PlayerLEDNewRevision 0-4, 5 = off
MIC_VALUES = {0: 1, 1: 2, 2: 0}                           # On, Pulse, Off -> report values


# -- the override state --------------------------------------------------------------------
# USB output report 0x02 offsets (including the report id byte)
VALID0, VALID1 = 1, 2
R2_VALID, L2_VALID = 0x04, 0x08
MIC_VALID, LIGHTBAR_VALID, PLAYER_VALID = 0x01, 0x04, 0x10
MIC_BYTE, R2_EFFECT, L2_EFFECT, PLAYER_LEDS, LIGHTBAR = 9, 11, 22, 44, 45
OUTPUT_SIZE = 48
# USB input report 0x01
L2_ANALOG, R2_ANALOG, BUTTONS1 = 5, 6, 9
L2_BUTTON, R2_BUTTON = 0x04, 0x08


class Overrides:
    """What mods have set, patched over the game's output. Every field is None (the game's
    own) until a mod sets it. on_change(cleared) is called after each change, outside the
    lock; cleared is True when everything went back to the game."""

    FIELDS = ("l2", "r2", "rgb", "player", "mic")

    def __init__(self, on_change=None):
        self.on_change = on_change
        self.on_status = None                # the tray: refresh its status line
        self._lock = threading.Lock()
        self.l2 = self.r2 = self.rgb = self.player = self.mic = None
        self.thresholds = {L2: 0, R2: 0}
        self.l2_mode = self.r2_mode = None   # mode numbers, for the tray's status line
        self.source = None                   # who set them, e.g. "re4.exe (payload file)"
        self.enabled = True

    @property
    def active(self):
        return any(getattr(self, f) is not None for f in self.FIELDS) or any(self.thresholds.values())

    def _state(self):
        return (self.l2, self.r2, self.rgb, self.player, self.mic, tuple(self.thresholds.values()))

    def apply(self, instructions, source):
        """Apply parsed instructions in order. Returns True if anything changed."""
        if not self.enabled or not instructions:
            return False
        with self._lock:
            before = self._state()
            for t, p in instructions:
                if t == GET_STATUS or not p and t != RESET:
                    continue
                if t != RESET and p[0] > 0:   # one controller: index 0, or negative for "all"
                    continue
                args = p[1:]
                try:
                    self._apply_one(t, args)
                except (IndexError, ValueError):
                    pass                       # bad instruction: keep the previous state
            changed = self._state() != before
            if changed:
                self.source = source if self.active else None
            cleared = changed and not self.active
        if changed:
            self._changed(cleared)
        return changed

    def _changed(self, cleared):
        if self.on_change:
            self.on_change(cleared)
        if self.on_status:
            try:
                self.on_status()
            except Exception:
                pass

    def _apply_one(self, t, a):
        if t == TRIGGER:
            side, mode = a[0], a[1]
            effect = encode_trigger(mode, a[2:])
            if effect is None or side not in (L2, R2):
                return
            if side == L2:
                self.l2, self.l2_mode = effect, mode
            else:
                self.r2, self.r2_mode = effect, mode
        elif t == RGB:
            r, g, b = (max(0, min(255, v)) for v in a[:3])
            k = max(0, min(255, a[3])) if len(a) > 3 else 255   # v3 brightness
            self.rgb = (r * k // 255, g * k // 255, b * k // 255)
        elif t == PLAYER_LED:
            if a:
                self.player = sum(1 << i for i, v in enumerate(a[:5]) if v)
        elif t == PLAYER_LED_NEW:
            if 0 <= a[0] < len(PLAYER_PATTERNS):
                self.player = PLAYER_PATTERNS[a[0]]
        elif t == MIC_LED:
            if a[0] in MIC_VALUES:
                self.mic = MIC_VALUES[a[0]]
        elif t == THRESHOLD:
            if a[0] in (L2, R2):
                self.thresholds[a[0]] = max(0, min(255, a[1]))
        elif t == RESET:
            self._clear()

    def _clear(self):
        self.l2 = self.r2 = self.rgb = self.player = self.mic = None
        self.l2_mode = self.r2_mode = None
        self.thresholds = {L2: 0, R2: 0}

    def release(self, source=None):
        """Give everything back to the game: when `source` (if given) is the one that set it."""
        with self._lock:
            if not self.active or source is not None and self.source != source:
                return False
            self._clear()
            self.source = None
        self._changed(True)
        return True

    def patch(self, report):
        """A game's (or our own) output report 0x02 with the overrides written over it."""
        with self._lock:
            if not self.active:
                return report
            r = bytearray(report).ljust(OUTPUT_SIZE, b"\0")
            if self.r2 is not None:
                r[R2_EFFECT:R2_EFFECT + 11] = self.r2
                r[VALID0] |= R2_VALID
            if self.l2 is not None:
                r[L2_EFFECT:L2_EFFECT + 11] = self.l2
                r[VALID0] |= L2_VALID
            if self.mic is not None:
                r[MIC_BYTE] = self.mic
                r[VALID1] |= MIC_VALID
            if self.player is not None:
                r[PLAYER_LEDS] = self.player
                r[VALID1] |= PLAYER_VALID
            if self.rgb is not None:
                r[LIGHTBAR:LIGHTBAR + 3] = bytes(self.rgb)
                r[VALID1] |= LIGHTBAR_VALID
            return bytes(r)

    def own_report(self):
        """A report of our own: zeros except the overridden fields and their flags. With
        nothing overridden, both triggers off, so a mod's resistance doesn't linger."""
        if not self.active:
            r = bytearray(OUTPUT_SIZE)
            r[0], r[VALID0] = 0x02, R2_VALID | L2_VALID
            r[R2_EFFECT:R2_EFFECT + 11] = OFF
            r[L2_EFFECT:L2_EFFECT + 11] = OFF
            return bytes(r)
        return self.patch(bytes([0x02]) + bytes(OUTPUT_SIZE - 1))

    def filter_input(self, report):
        """Trigger thresholds: below the point, the trigger reads 0 and its button is up."""
        l2, r2 = self.thresholds[L2], self.thresholds[R2]
        if not (l2 or r2) or len(report) <= BUTTONS1:
            return report
        r = bytearray(report)
        for point, axis, bit in ((l2, L2_ANALOG, L2_BUTTON), (r2, R2_ANALOG, R2_BUTTON)):
            if point and r[axis] < point:
                r[axis] = 0
                r[BUTTONS1] &= ~bit & 0xFF
        return bytes(r)

    def describe(self):
        """e.g. 'L2 Resistance, R2 VerySoft, lightbar' (for the tray)."""
        with self._lock:
            parts = []
            for name, mode, eff in (("L2", self.l2_mode, self.l2), ("R2", self.r2_mode, self.r2)):
                if eff is not None:
                    parts.append(f"{name} {MODE_NAMES[mode] if 0 <= mode < len(MODE_NAMES) else mode}")
            if self.rgb is not None:
                parts.append("lightbar")
            if self.player is not None:
                parts.append("player lights")
            if self.mic is not None:
                parts.append("mic light")
            if any(self.thresholds.values()):
                parts.append("trigger threshold")
            return ", ".join(parts)


# -- Windows: processes and UDP port owners --------------------------------------------------
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.OpenProcess.restype = wt.HANDLE
_k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k32.CloseHandle.argtypes = [wt.HANDLE]
_k32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
_k32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
_k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", wt.WCHAR * 260)]


def list_processes():
    """{pid: exe file name} of everything running."""
    snap = _k32.CreateToolhelp32Snapshot(0x2, 0)   # TH32CS_SNAPPROCESS
    if not snap or snap == wt.HANDLE(-1).value:
        return {}
    out = {}
    try:
        e = _PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(e)
        ok = _k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            out[e.th32ProcessID] = e.szExeFile
            ok = _k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        _k32.CloseHandle(snap)
    return out


def process_path(pid):
    h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wt.DWORD(len(buf))
        return buf.value if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else None
    finally:
        _k32.CloseHandle(h)


def process_alive(pid):
    h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    try:
        code = wt.DWORD()
        return bool(_k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == STILL_ACTIVE
    finally:
        _k32.CloseHandle(h)


def dsx_running(processes=None):
    return any(n.lower() == "dsx.exe" for n in (processes or list_processes()).values())


def udp_owners():
    """{local UDP port: owning pid} for IPv4 sockets (GetExtendedUdpTable)."""
    iphlp = ctypes.WinDLL("iphlpapi")
    size = wt.DWORD(0)
    iphlp.GetExtendedUdpTable(None, ctypes.byref(size), False, socket.AF_INET, 1, 0)
    buf = ctypes.create_string_buffer(size.value + 1024)
    size = wt.DWORD(len(buf))
    if iphlp.GetExtendedUdpTable(buf, ctypes.byref(size), False, socket.AF_INET, 1, 0):
        return {}   # UDP_TABLE_OWNER_PID
    count = struct.unpack_from("<I", buf, 0)[0]
    owners = {}
    for i in range(count):
        _addr, port, pid = struct.unpack_from("<III", buf, 4 + 12 * i)
        owners[socket.ntohs(port & 0xFFFF)] = pid
    return owners


# -- port files ------------------------------------------------------------------------------
def write_port_files(port=PORT, legacy=LEGACY_PORT_FILE, current=CURRENT_PORT_FILE, running=None):
    """Tell mods which port to use, unless a real DSX is running (it owns these files).
    The v2 file is created if missing; the v3.1 file only fixed if it names another port."""
    if dsx_running(running):
        return
    for path, create in ((legacy, True), (current, port != PORT)):
        try:
            with open(path, encoding="utf-8-sig") as f:
                if f.read().strip() == str(port):
                    continue
        except FileNotFoundError:
            if not create:
                continue
        except (OSError, ValueError):
            pass
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="ascii") as f:
                f.write(str(port))
            print(f"[mods] wrote port {port} to {path}")
        except OSError as e:
            print(f"[mods] could not write {path}: {e}")


# -- UDP ---------------------------------------------------------------------------------------
SIO_UDP_CONNRESET = 0x9800000C


def _disable_connreset(sock):
    """Without this, an ICMP 'port unreachable' (a mod closed its socket before our reply
    arrived) makes the next recvfrom fail with WSAECONNRESET."""
    off = wt.DWORD(0)
    returned = wt.DWORD()
    ctypes.WinDLL("ws2_32").WSAIoctl(ctypes.c_size_t(sock.fileno()), SIO_UDP_CONNRESET,
                                     ctypes.byref(off), 4, None, 0, ctypes.byref(returned),
                                     None, None)


class DsxServer:
    """UDP stand-in for DSX on 127.0.0.1:6969. status() -> dict(connected, battery, mac)."""

    RETRY = 30.0     # s between tries while the port is taken (e.g. a real DSX)

    def __init__(self, overrides, status, port=PORT, owners=udp_owners, alive=process_alive,
                 names=None, port_files=True):
        self.overrides, self.status, self.port = overrides, status, port
        self._owners, self._alive = owners, alive
        self._names = names or (lambda pid: (list_processes().get(pid) or f"process {pid}"))
        self._port_files = port_files
        self._sock = None
        self._stop = threading.Event()
        self._senders = {}           # (addr) -> pid or None
        self._source = None          # (source label, pid or None, last packet time)
        self._logged_busy = False
        self.listening = False

    def start(self):
        self._stop.clear()
        threading.Thread(target=self._run, daemon=True, name="dsx-udp").start()
        threading.Thread(target=self._watch_sender, daemon=True, name="dsx-udp-sender").start()

    def stop(self):
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass

    def _bind(self):
        try:
            busy = self.port in self._owners()
        except OSError:
            busy = False
        if not busy:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                s.bind(("127.0.0.1", self.port))
                _disable_connreset(s)
                s.settimeout(1.0)
                return s
            except OSError:
                s.close()
        if not self._logged_busy:
            self._logged_busy = True
            print(f"[mods] UDP port {self.port} is in use (DSX running?); leaving it to that app")
        return None

    def _run(self):
        while not self._stop.is_set():
            self._sock = self._bind()
            if not self._sock:
                self._stop.wait(self.RETRY)
                continue
            self.listening = True
            print(f"[mods] listening for game mods on UDP 127.0.0.1:{self.port}")
            if self._port_files:
                write_port_files(self.port)
            try:
                self._serve()
            finally:
                self.listening = False
                self._sock.close()

    def _serve(self):
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(65535)
            except socket.timeout:
                continue
            except ConnectionResetError:
                continue
            except OSError:
                if self._stop.is_set():
                    return
                raise
            if addr[0] != "127.0.0.1":
                continue
            instructions = parse(data)
            # Reply first: some mods block on receive without a timeout.
            try:
                self._sock.sendto(self.reply(), addr)
            except OSError:
                pass
            if instructions is None:
                continue
            self._sender(addr)
            self.overrides.apply(instructions, self._source[0])

    def reply(self):
        st = self.status()
        battery = st.get("battery", 0) if st.get("connected") else 0
        devices = [{"Index": 0, "MacAddress": st.get("mac", ""), "DeviceType": 0,
                    "ConnectionType": 0, "BatteryLevel": battery, "IsSupportAT": True,
                    "IsSupportLightBar": True, "IsSupportPlayerLED": True,
                    "IsSupportMicLED": True}] if st.get("connected") else []
        return json.dumps({"Status": REPLY_STATUS,
                           "TimeReceived": time.strftime("%Y/%m/%d %I:%M:%S %p"),
                           "isControllerConnected": bool(st.get("connected")),
                           "BatteryLevel": battery, "Devices": devices}).encode()

    def _sender(self, addr):
        """Who sent this (the process owning its source port, if it can be found)."""
        if addr not in self._senders:
            try:
                pid = self._owners().get(addr[1])
            except OSError:
                pid = None
            label = f"{self._names(pid)} (UDP)" if pid else f"UDP port {addr[1]}"
            self._senders[addr] = (pid, label)
            print(f"[mods] mod connected: {label}")
        pid, label = self._senders[addr]
        self._source = (label, pid, time.monotonic())

    def _watch_sender(self):
        """Hold effects while the sender runs; without a process to watch, until it's quiet."""
        while not self._stop.wait(1.0):
            if not self._source:
                continue
            label, pid, last = self._source
            gone = not self._alive(pid) if pid else time.monotonic() - last > UDP_IDLE
            if gone:
                self._source = None
                self._senders.clear()
                if self.overrides.release(label):
                    print(f"[mods] {label} {'exited' if pid else 'went quiet'}; effects released")


# -- payload files ---------------------------------------------------------------------------
def controller_seen(data):
    """Our scripts' "controllerSeen" (whether the game sees any controller), or None."""
    try:
        root = json.loads(bytes(data).decode("utf-8", "replace").strip("\0 \t\r\n\ufeff"))
    except ValueError:
        return None
    value = _key(root, "controllerseen") if isinstance(root, dict) else None
    return value if isinstance(value, bool) else None



class PayloadWatcher:
    """Finds running games with a known mod payload file next to them and applies it."""

    SCAN = 3.0       # s between process scans
    POLL = 0.05      # s between checks of a watched file

    def __init__(self, overrides, processes=list_processes, path_of=process_path,
                 alive=process_alive, paths=PAYLOAD_PATHS, on_process=None,
                 on_controller_seen=None):
        self.overrides = overrides
        # called with (source, exe file name, seen): our game scripts report whether the game
        # sees a controller at all ("controllerSeen" in their payload)
        self.on_controller_seen = on_controller_seen
        self.on_process = on_process   # called with (pid, exe path) for each new process
        self._processes, self._path_of, self._alive, self._paths = processes, path_of, alive, paths
        self._stop = threading.Event()
        self._seen = {}          # pid -> exe name, processes already looked at
        self._folders = {}       # exe folder -> could hold a payload (its top folder exists)
        self._watching = set()   # pids being watched

    def start(self):
        self._stop.clear()
        threading.Thread(target=self._scan_loop, daemon=True, name="dsx-payload").start()

    def stop(self):
        self._stop.set()

    def _scan_loop(self):
        while not self._stop.is_set():
            try:
                self.scan()
            except Exception as e:     # never let one odd process stop the scanner
                print(f"[mods] process scan failed: {e}")
            self._stop.wait(self.SCAN)

    def scan(self):
        procs = self._processes()
        self._seen = {p: n for p, n in self._seen.items() if p in procs}
        for pid, name in procs.items():
            if pid in self._seen or pid in self._watching:
                continue
            self._seen[pid] = name
            exe = self._path_of(pid)
            if not exe:
                continue
            if self.on_process:
                try:
                    self.on_process(pid, exe)
                except Exception as e:
                    print(f"[mods] game check failed: {e}")
            folder = os.path.dirname(exe)
            if folder.lower().startswith(os.environ.get("SystemRoot", r"C:\Windows").lower()):
                continue
            # Checked again for every new process, not cached per folder: a mod (or its
            # loader) may have been installed since the game last ran.
            self._folders[folder] = [p for p in self._paths
                                     if os.path.isdir(os.path.join(folder, p.split("\\")[0]))]
            if self._folders[folder]:
                self._watching.add(pid)
                threading.Thread(target=self.watch, daemon=True, name=f"dsx-payload-{pid}",
                                 args=(folder, f"{name} (payload file)",
                                       lambda pid=pid: self._alive(pid), pid)).start()

    def watch(self, folder, source, alive, pid=None):
        """Watch the folder's payload files while alive(); release the overrides after."""
        candidates = [os.path.join(folder, p) for p in self._folders.get(folder, self._paths)]
        last, announced = {}, set()     # per file: the (mtime, size) last applied
        try:
            while alive() and not self._stop.is_set():
                for path in candidates:   # each file on its own: a game may have two mods
                    try:
                        st = os.stat(path)
                    except OSError:
                        continue
                    stamp = (st.st_mtime_ns, st.st_size)
                    if stamp == last.get(path):
                        continue
                    try:
                        with open(path, "rb") as f:
                            data = f.read()
                    except OSError:
                        continue          # being written; try again next poll
                    instructions = parse(data)
                    if instructions is None:   # empty or half-written: read it again next poll
                        continue
                    last[path] = stamp
                    if instructions and path not in announced:
                        announced.add(path)
                        print(f"[mods] mod connected: {source} ({path})")
                    self.overrides.apply(instructions, source)
                    seen = controller_seen(data)
                    if seen is not None and self.on_controller_seen:
                        try:
                            self.on_controller_seen(source, source.split(" ")[0], seen)
                        except Exception as e:
                            print(f"[mods] controller check failed: {e}")
                self._stop.wait(self.POLL)
        finally:
            self._watching.discard(pid)
            if self.overrides.release(source):
                print(f"[mods] {source} exited; effects released")
