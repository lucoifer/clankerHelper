"""
ARC Raiders quick-use hotkey helper for Windows.

Configured hotkeys send quick-use chords like: Left Alt down -> slot tap -> Left Alt up.
Backquote toggles autorun, and Left Ctrl + Left Shift pauses/resumes macros.

Notes:
- Run with Python on Windows.
- If the game/anti-cheat blocks synthetic input, this script will not bypass that.
- Use in borderless/windowed mode if fullscreen does not receive global hotkeys.
"""

from __future__ import annotations

import ctypes
import json
import msvcrt
from pathlib import Path
import traceback
from ctypes import wintypes
import time


# --- User settings --------------------------------------------------------

# Profile picker. Press 1/2/3 within this many seconds after launch.
ENABLE_PROFILE_PICKER = True
PROFILE_PICK_TIMEOUT_SECONDS = 5
DEFAULT_PROFILE_NAME = "Luci"
PROFILE_ORDER = ("Luci", "SM", "Zak")
PROFILE_COLORS = {
    "Luci": "magenta",
    "SM": "cyan",
    "Zak": "green",
}

# Default quick-use binds. Profiles below copy this until you give me each
# person's real binds.
DEFAULT_HOTKEYS = {
    "3": "3",
    "4": "4",
    "5": "5",
    "6": "6",
    "x": "6",
}

# Each profile can have its own hotkeys and toggle keys.
# Example: "x": "6" means pressing X sends Left Alt + 6.
PROFILES = {
    "Luci": {
        "hotkeys": DEFAULT_HOTKEYS.copy(),
        "autorun_toggle_key": "backquote",
        "display_boost_toggle_key": "b",
    },
    "SM": {
        "hotkeys": DEFAULT_HOTKEYS.copy(),
        "autorun_toggle_key": "backquote",
        "display_boost_toggle_key": "b",
    },
    "Zak": {
        "hotkeys": DEFAULT_HOTKEYS.copy(),
        "autorun_toggle_key": "backquote",
        "display_boost_toggle_key": "b",
    },
}

# Active settings. These are filled from the selected profile at startup.
ACTIVE_PROFILE_NAME = DEFAULT_PROFILE_NAME
HOTKEYS = DEFAULT_HOTKEYS.copy()

# Which key opens your quick-use menu.
QUICK_USE_HOLD_KEY = "left_alt"

# False means macros start enabled as soon as the script opens.
# True means macros start paused until you press the pause/resume combo.
START_MACROS_PAUSED = False

# Lets the same hotkeys work while sprinting/running with Shift held.
REGISTER_HOTKEYS_WHILE_SHIFT_HELD = True

# Keep this False if you want sprint to continue uninterrupted.
# If Arc refuses to select a slot while Shift is held, you can try True, but it
# will briefly interrupt sprint.
TEMPORARILY_RELEASE_SHIFT_WHILE_USING = False

# Only matters when TEMPORARILY_RELEASE_SHIFT_WHILE_USING is True.
RESTORE_SHIFT_AFTER_QUICK_USE = True

# Press this key to toggle autorun.
AUTORUN_TOGGLE_KEY = "backquote"

# Uses the physical key position, so ` works on non-US keyboard layouts too.
USE_PHYSICAL_HOOK_FOR_AUTORUN_TOGGLE = True

# Stops the ` key from also reaching the game/windows while it toggles autorun.
SUPPRESS_AUTORUN_TOGGLE_KEY = True

# These keys are held while autorun is on.
AUTORUN_HOLD_KEYS = ("left_shift", "w")

# Only matters if USE_PHYSICAL_HOOK_FOR_AUTORUN_TOGGLE is False.
# The physical hook already works while Shift is held.
REGISTER_AUTORUN_WHILE_SHIFT_HELD = True

# Press this physical key combo once to pause macros, and again to resume.
ENABLE_PAUSE_TOGGLE = True
PAUSE_TOGGLE_KEYS = ("left_ctrl", "left_shift")

# Pausing releases autorun so it cannot keep moving you while macros are paused.
RELEASE_AUTORUN_WHEN_PAUSED = True

# Press this key to toggle display boost on/off.
DISPLAY_BOOST_TOGGLE_KEY = "b"

# Lets the display boost toggle work while Shift is held.
REGISTER_DISPLAY_BOOST_WHILE_SHIFT_HELD = True

# Display boost values.
# Hardware brightness targets the Windows primary monitor only.
# Gamma targets the Windows primary display DC only, when the driver allows it.
DISPLAY_USE_HARDWARE_BRIGHTNESS = True
DISPLAY_USE_GAMMA_RAMP = True
DISPLAY_BRIGHTNESS_BOOST_PERCENT = 10
DISPLAY_GAMMA_BOOST_PERCENT = 42

# Pausing/exiting restores the original display ramp.
RESTORE_DISPLAY_WHEN_PAUSED = True
RESTORE_DISPLAY_ON_EXIT = True
RESTORE_DISPLAY_STATE_ON_START = True

# Delays. These are fixed, based on the midpoint of your XML values:
# 234-244 ms -> 239 ms, 64-72 ms -> 68 ms, 64-71 ms -> 68 ms.
DELAY_AFTER_ALT_DOWN_MS = 239
DELAY_SLOT_HOLD_MS = 68
DELAY_BEFORE_ALT_UP_MS = 68

# Tiny buffer after lifting/restoring Shift.
DELAY_AFTER_SHIFT_RELEASE_MS = 10
DELAY_AFTER_SHIFT_RESTORE_MS = 10


# --- Win32 constants ------------------------------------------------------

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
try:
    dxva2 = ctypes.WinDLL("dxva2", use_last_error=True)
except OSError:
    dxva2 = None
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short

INPUT_KEYBOARD = 1
CCHDEVICENAME = 32
STD_OUTPUT_HANDLE = -11
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
MONITORINFOF_PRIMARY = 0x00000001
WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
LLKHF_INJECTED = 0x00000010
LLKHF_LOWER_IL_INJECTED = 0x00000002
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

VK_CODES = {
    "0": 0x30,
    "1": 0x31,
    "2": 0x32,
    "3": 0x33,
    "4": 0x34,
    "5": 0x35,
    "6": 0x36,
    "7": 0x37,
    "8": 0x38,
    "9": 0x39,
    "b": 0x42,
    "w": 0x57,
    "x": 0x58,
    "backquote": 0xC0,
    "comma": 0xBC,
    "left_ctrl": 0xA2,
    "right_ctrl": 0xA3,
    "left_shift": 0xA0,
    "right_shift": 0xA1,
}

SCAN_CODES = {
    "0": 0x0B,
    "1": 0x02,
    "2": 0x03,
    "3": 0x04,
    "4": 0x05,
    "5": 0x06,
    "6": 0x07,
    "7": 0x08,
    "8": 0x09,
    "9": 0x0A,
    "b": 0x30,
    "w": 0x11,
    "x": 0x2D,
    "backquote": 0x29,
    "comma": 0x33,
    "left_alt": 0x38,
    "left_ctrl": 0x1D,
    "right_ctrl": 0x1D,
    "left_shift": 0x2A,
    "right_shift": 0x36,
}

SHIFT_KEYS = ("left_shift", "right_shift")
KEY_LABELS = {
    "b": "B",
    "backquote": "`",
    "comma": ",",
    "left_alt": "Left Alt",
    "left_ctrl": "Left Ctrl",
    "right_ctrl": "Right Ctrl",
    "left_shift": "Left Shift",
    "right_shift": "Right Shift",
    "w": "W",
    "x": "X",
}

VK_TO_KEY = {vk: key for key, vk in VK_CODES.items()}
VK_TO_KEY[0x10] = "left_shift"
VK_TO_KEY[0x11] = "left_ctrl"
SCAN_TO_KEY = {scan: key for key, scan in SCAN_CODES.items()}

ACTION_QUICK_USE = "quick_use"
ACTION_AUTORUN_TOGGLE = "autorun_toggle"
ACTION_DISPLAY_BOOST_TOGGLE = "display_boost_toggle"

macros_paused = START_MACROS_PAUSED
autorun_enabled = False
display_boost_enabled = False
original_gamma_ramp = None
original_monitor_brightness = None
display_boost_components: set[str] = set()
registered_hotkeys: dict[int, tuple[str, str]] = {}
physical_keys_down: set[str] = set()
pause_combo_is_down = False
keyboard_hook_handle = None
keyboard_proc_ref = None


ULONG_PTR = wintypes.WPARAM


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class INPUT_UNION(ctypes.Union):
    _fields_ = (
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    )


class INPUT(ctypes.Structure):
    _fields_ = (
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION),
    )


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = (
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * CCHDEVICENAME),
    )


class PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = (
        ("hPhysicalMonitor", wintypes.HANDLE),
        ("szPhysicalMonitorDescription", wintypes.WCHAR * 128),
    )


GammaChannel = wintypes.WORD * 256


class GammaRamp(ctypes.Structure):
    _fields_ = (
        ("red", GammaChannel),
        ("green", GammaChannel),
        ("blue", GammaChannel),
    )


LRESULT = ctypes.c_ssize_t
MONITORENUMPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HANDLE,
    wintypes.HDC,
    ctypes.POINTER(wintypes.RECT),
    wintypes.LPARAM,
)
HOOKPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)

kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
user32.SetWindowsHookExW.argtypes = (
    ctypes.c_int,
    HOOKPROC,
    wintypes.HANDLE,
    wintypes.DWORD,
)
user32.SetWindowsHookExW.restype = wintypes.HANDLE
user32.CallNextHookEx.argtypes = (
    wintypes.HANDLE,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = (wintypes.HANDLE,)
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
kernel32.GetStdHandle.argtypes = (wintypes.DWORD,)
kernel32.GetStdHandle.restype = wintypes.HANDLE
kernel32.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
kernel32.GetConsoleMode.restype = wintypes.BOOL
kernel32.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)
kernel32.SetConsoleMode.restype = wintypes.BOOL
user32.EnumDisplayMonitors.argtypes = (
    wintypes.HDC,
    ctypes.POINTER(wintypes.RECT),
    MONITORENUMPROC,
    wintypes.LPARAM,
)
user32.EnumDisplayMonitors.restype = wintypes.BOOL
user32.GetMonitorInfoW.argtypes = (wintypes.HANDLE, ctypes.POINTER(MONITORINFOEXW))
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.GetDC.argtypes = (wintypes.HWND,)
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
user32.ReleaseDC.restype = ctypes.c_int
gdi32.CreateDCW.argtypes = (
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    ctypes.c_void_p,
)
gdi32.CreateDCW.restype = wintypes.HDC
gdi32.DeleteDC.argtypes = (wintypes.HDC,)
gdi32.DeleteDC.restype = wintypes.BOOL
gdi32.GetDeviceGammaRamp.argtypes = (wintypes.HDC, ctypes.POINTER(GammaRamp))
gdi32.GetDeviceGammaRamp.restype = wintypes.BOOL
gdi32.SetDeviceGammaRamp.argtypes = (wintypes.HDC, ctypes.POINTER(GammaRamp))
gdi32.SetDeviceGammaRamp.restype = wintypes.BOOL

if dxva2 is not None:
    dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    )
    dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.restype = wintypes.BOOL
    dxva2.GetPhysicalMonitorsFromHMONITOR.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(PHYSICAL_MONITOR),
    )
    dxva2.GetPhysicalMonitorsFromHMONITOR.restype = wintypes.BOOL
    dxva2.DestroyPhysicalMonitors.argtypes = (
        wintypes.DWORD,
        ctypes.POINTER(PHYSICAL_MONITOR),
    )
    dxva2.DestroyPhysicalMonitors.restype = wintypes.BOOL
    dxva2.GetMonitorBrightness.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
    )
    dxva2.GetMonitorBrightness.restype = wintypes.BOOL
    dxva2.SetMonitorBrightness.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    dxva2.SetMonitorBrightness.restype = wintypes.BOOL


def msleep(milliseconds: int) -> None:
    time.sleep(milliseconds / 1000)


def send_scan(scan_code: int, key_up: bool = False) -> None:
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0)
    event = INPUT(
        type=INPUT_KEYBOARD,
        union=INPUT_UNION(
            ki=KEYBDINPUT(
                wVk=0,
                wScan=scan_code,
                dwFlags=flags,
                time=0,
                dwExtraInfo=0,
            )
        ),
    )

    sent = user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(event))
    if sent != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def is_key_down(key_name: str) -> bool:
    return bool(user32.GetAsyncKeyState(VK_CODES[key_name]) & 0x8000)


def held_shift_keys() -> list[str]:
    return [key_name for key_name in SHIFT_KEYS if is_key_down(key_name)]


def release_keys(key_names: list[str]) -> None:
    for key_name in key_names:
        send_scan(SCAN_CODES[key_name], key_up=True)


def press_keys(key_names: list[str]) -> None:
    for key_name in key_names:
        send_scan(SCAN_CODES[key_name])


def key_label(key_name: str) -> str:
    return KEY_LABELS.get(key_name, key_name.upper() if len(key_name) == 1 else key_name)


COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "cyan": "\033[96m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "magenta": "\033[95m",
    "blue": "\033[94m",
    "white": "\033[97m",
}


def enable_console_colors() -> None:
    handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    if not handle:
        return

    mode = wintypes.DWORD()
    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        kernel32.SetConsoleMode(
            handle,
            mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING,
        )


def color(text: str, color_name: str) -> str:
    return f"{COLORS.get(color_name, '')}{text}{COLORS['reset']}"


def profile_label(profile_name: str) -> str:
    return color(profile_name, PROFILE_COLORS.get(profile_name, "white"))


def status(text: str, color_name: str = "cyan") -> None:
    print(color(text, color_name))


def print_rule() -> None:
    print(color("=" * 58, "blue"))


def print_banner() -> None:
    print()
    print_rule()
    print(color("ARC RAIDERS QUICK-USE HELPER", "cyan"))
    print(color("profile binds | autorun | display boost | pause toggle", "dim"))
    print_rule()


def apply_profile(profile_name: str) -> None:
    global ACTIVE_PROFILE_NAME, HOTKEYS, AUTORUN_TOGGLE_KEY, DISPLAY_BOOST_TOGGLE_KEY

    profile = PROFILES.get(profile_name, PROFILES[DEFAULT_PROFILE_NAME])
    ACTIVE_PROFILE_NAME = profile_name if profile_name in PROFILES else DEFAULT_PROFILE_NAME
    HOTKEYS = dict(profile.get("hotkeys", DEFAULT_HOTKEYS))
    AUTORUN_TOGGLE_KEY = profile.get("autorun_toggle_key", AUTORUN_TOGGLE_KEY)
    DISPLAY_BOOST_TOGGLE_KEY = profile.get(
        "display_boost_toggle_key",
        DISPLAY_BOOST_TOGGLE_KEY,
    )


def choose_profile_name() -> str:
    if not ENABLE_PROFILE_PICKER:
        return DEFAULT_PROFILE_NAME

    choices = {
        str(index): profile_name
        for index, profile_name in enumerate(PROFILE_ORDER, start=1)
        if profile_name in PROFILES
    }

    print_banner()
    print(color("Choose profile:", "white"))
    for number, profile_name in choices.items():
        default_marker = "  default" if profile_name == DEFAULT_PROFILE_NAME else ""
        print(f"  {color(number, 'yellow')}  {profile_label(profile_name)}{color(default_marker, 'dim')}")
    print()

    deadline = time.monotonic() + PROFILE_PICK_TIMEOUT_SECONDS
    last_remaining = None

    while True:
        remaining = max(0, int(deadline - time.monotonic() + 0.999))
        if remaining != last_remaining:
            print(
                "\r"
                + color(
                    f"Press 1/2/3 within {remaining}s, or wait for {DEFAULT_PROFILE_NAME}...",
                    "dim",
                ),
                end="",
                flush=True,
            )
            last_remaining = remaining

        if msvcrt.kbhit():
            key = msvcrt.getwch()
            if key in choices:
                print()
                selected = choices[key]
                print(f"Selected profile: {profile_label(selected)}")
                return selected
            if key in ("\r", "\n"):
                print()
                print(f"Selected default profile: {profile_label(DEFAULT_PROFILE_NAME)}")
                return DEFAULT_PROFILE_NAME

        if time.monotonic() >= deadline:
            print()
            print(f"No profile selected. Defaulting to {profile_label(DEFAULT_PROFILE_NAME)}.")
            return DEFAULT_PROFILE_NAME

        time.sleep(0.05)


def print_active_layout() -> None:
    quick_use_label = key_label(QUICK_USE_HOLD_KEY)
    print()
    print_rule()
    print(f"Profile: {profile_label(ACTIVE_PROFILE_NAME)}")
    print(color(f"Macros: {'PAUSED' if macros_paused else 'ENABLED'}", "green" if not macros_paused else "yellow"))
    print_rule()

    print(color("Quick Use", "cyan"))
    for hotkey_key, slot_key in HOTKEYS.items():
        print(f"  {key_label(hotkey_key):>7} -> {quick_use_label} + {slot_key}")
        if REGISTER_HOTKEYS_WHILE_SHIFT_HELD:
            print(f"  {'Shift+' + key_label(hotkey_key):>7} -> {quick_use_label} + {slot_key}")

    if AUTORUN_TOGGLE_KEY:
        held_keys = " + ".join(key_label(key_name) for key_name in AUTORUN_HOLD_KEYS)
        print(color("Autorun", "cyan"))
        print(f"  {key_label(AUTORUN_TOGGLE_KEY):>7} -> toggle {held_keys}")
        if USE_PHYSICAL_HOOK_FOR_AUTORUN_TOGGLE:
            print(color("          physical key detection enabled", "dim"))

    if DISPLAY_BOOST_TOGGLE_KEY:
        print(color("Display", "cyan"))
        print(
            f"  {key_label(DISPLAY_BOOST_TOGGLE_KEY):>7} -> "
            f"+{DISPLAY_BRIGHTNESS_BOOST_PERCENT}% brightness / "
            f"+{DISPLAY_GAMMA_BOOST_PERCENT}% gamma"
        )

    if ENABLE_PAUSE_TOGGLE:
        pause_keys = " + ".join(key_label(key_name) for key_name in PAUSE_TOGGLE_KEYS)
        print(color("Safety", "cyan"))
        print(f"  {pause_keys} -> pause/resume macros")

    print_rule()
    print(color("Press Ctrl+C in this window to stop.", "dim"))


def set_autorun(enabled: bool) -> None:
    global autorun_enabled

    if enabled == autorun_enabled:
        return

    if enabled:
        press_keys(AUTORUN_HOLD_KEYS)
    else:
        release_keys(reversed(AUTORUN_HOLD_KEYS))

    autorun_enabled = enabled
    status(f"\nAutorun {'ON' if autorun_enabled else 'OFF'}", "green" if autorun_enabled else "yellow")


def api_failure(function_name: str) -> RuntimeError:
    error_code = ctypes.get_last_error()
    if error_code:
        message = ctypes.FormatError(error_code).strip()
        return RuntimeError(f"{function_name} failed: {message} (WinError {error_code})")

    return RuntimeError(f"{function_name} failed; the driver returned no error code")


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def get_primary_monitor() -> tuple[int, str]:
    primary_monitor: dict[str, int | str] = {}

    @MONITORENUMPROC
    def enum_proc(hmonitor, hdc, rect, data):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            if info.dwFlags & MONITORINFOF_PRIMARY:
                primary_monitor["handle"] = hmonitor
                primary_monitor["device"] = info.szDevice
                return False
        return True

    ctypes.set_last_error(0)
    user32.EnumDisplayMonitors(None, None, enum_proc, 0)

    if "handle" not in primary_monitor:
        raise api_failure("EnumDisplayMonitors/GetMonitorInfoW")

    return int(primary_monitor["handle"]), str(primary_monitor["device"])


def create_primary_display_dc() -> wintypes.HDC:
    _, device_name = get_primary_monitor()

    hdc = gdi32.CreateDCW(None, device_name, None, None)
    if not hdc:
        hdc = gdi32.CreateDCW("DISPLAY", device_name, None, None)
    if not hdc:
        raise api_failure(f"CreateDCW for primary display {device_name}")

    return hdc


def get_gamma_ramp() -> GammaRamp:
    hdc = create_primary_display_dc()

    ramp = GammaRamp()
    try:
        ctypes.set_last_error(0)
        if not gdi32.GetDeviceGammaRamp(hdc, ctypes.byref(ramp)):
            raise api_failure("GetDeviceGammaRamp for primary display")
    finally:
        gdi32.DeleteDC(hdc)

    return ramp


def set_gamma_ramp(ramp: GammaRamp) -> None:
    hdc = create_primary_display_dc()

    try:
        ctypes.set_last_error(0)
        if not gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp)):
            raise api_failure("SetDeviceGammaRamp for primary display")
    finally:
        gdi32.DeleteDC(hdc)


def open_primary_physical_monitors():
    if dxva2 is None:
        raise RuntimeError("dxva2.dll is not available on this Windows install")

    hmonitor, _ = get_primary_monitor()
    count = wintypes.DWORD()

    ctypes.set_last_error(0)
    if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(
        hmonitor,
        ctypes.byref(count),
    ):
        raise api_failure("GetNumberOfPhysicalMonitorsFromHMONITOR")
    if count.value == 0:
        raise RuntimeError("Windows did not expose a physical monitor for the primary display")

    monitors = (PHYSICAL_MONITOR * count.value)()
    ctypes.set_last_error(0)
    if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmonitor, count, monitors):
        raise api_failure("GetPhysicalMonitorsFromHMONITOR")

    return monitors, count.value


def destroy_physical_monitors(monitors, count: int) -> None:
    if dxva2 is not None and monitors is not None and count:
        dxva2.DestroyPhysicalMonitors(count, monitors)


def get_primary_monitor_brightness() -> list[tuple[int, int, int]]:
    monitors = None
    count = 0
    values: list[tuple[int, int, int]] = []

    try:
        monitors, count = open_primary_physical_monitors()
        for index in range(count):
            minimum = wintypes.DWORD()
            current = wintypes.DWORD()
            maximum = wintypes.DWORD()

            ctypes.set_last_error(0)
            if not dxva2.GetMonitorBrightness(
                monitors[index].hPhysicalMonitor,
                ctypes.byref(minimum),
                ctypes.byref(current),
                ctypes.byref(maximum),
            ):
                raise api_failure("GetMonitorBrightness for primary monitor")

            values.append((minimum.value, current.value, maximum.value))
    finally:
        destroy_physical_monitors(monitors, count)

    return values


def set_primary_monitor_brightness_values(target_values: list[int]) -> None:
    monitors = None
    count = 0

    try:
        monitors, count = open_primary_physical_monitors()
        if count < len(target_values):
            raise RuntimeError("Primary monitor handle count changed before brightness restore")

        for index, target_value in enumerate(target_values):
            ctypes.set_last_error(0)
            if not dxva2.SetMonitorBrightness(
                monitors[index].hPhysicalMonitor,
                wintypes.DWORD(target_value),
            ):
                raise api_failure("SetMonitorBrightness for primary monitor")
    finally:
        destroy_physical_monitors(monitors, count)


def build_boosted_brightness_values(
    brightness_values: list[tuple[int, int, int]],
) -> list[int]:
    boosted_values = []

    for minimum, current, maximum in brightness_values:
        boost_amount = round((maximum - minimum) * (DISPLAY_BRIGHTNESS_BOOST_PERCENT / 100))
        boosted_values.append(clamp_int(current + boost_amount, minimum, maximum))

    return boosted_values


def display_restore_state_path() -> Path:
    return Path(__file__).with_suffix(".display_restore.json")


def save_display_restore_state(brightness_values: list[tuple[int, int, int]]) -> None:
    state = {
        "primary_monitor_brightness": [
            current for _, current, _ in brightness_values
        ],
    }
    display_restore_state_path().write_text(json.dumps(state), encoding="utf-8")


def clear_display_restore_state() -> None:
    try:
        display_restore_state_path().unlink(missing_ok=True)
    except OSError as exc:
        status(f"\nCould not remove display restore state file: {exc}", "yellow")


def restore_display_state_from_file() -> None:
    if not RESTORE_DISPLAY_STATE_ON_START:
        return

    state_path = display_restore_state_path()
    if not state_path.exists():
        return

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        brightness_values = state.get("primary_monitor_brightness")
        if brightness_values:
            set_primary_monitor_brightness_values([int(value) for value in brightness_values])
            status("\nRestored primary monitor brightness from previous run.", "green")
        clear_display_restore_state()
    except Exception as exc:
        status(f"\nCould not restore saved display state: {exc}", "yellow")


def build_boosted_gamma_ramp(base_ramp: GammaRamp) -> GammaRamp:
    boosted_ramp = GammaRamp()
    brightness_multiplier = 1 + (DISPLAY_BRIGHTNESS_BOOST_PERCENT / 100)
    gamma_multiplier = 1 + (DISPLAY_GAMMA_BOOST_PERCENT / 100)
    gamma_power = 1 / gamma_multiplier

    for channel_name in ("red", "green", "blue"):
        source_channel = getattr(base_ramp, channel_name)
        boosted_channel = getattr(boosted_ramp, channel_name)
        previous_value = 0

        for index in range(256):
            normalized = max(0, min(1, source_channel[index] / 65535))
            boosted = (normalized ** gamma_power) * brightness_multiplier
            value = int(max(0, min(65535, boosted * 65535)))

            # Some display drivers reject non-monotonic gamma ramps.
            value = max(previous_value, value)
            boosted_channel[index] = value
            previous_value = value

    return boosted_ramp


def set_display_boost(enabled: bool) -> None:
    global display_boost_enabled, original_gamma_ramp, original_monitor_brightness

    if enabled == display_boost_enabled:
        return

    if enabled:
        warnings: list[str] = []
        display_boost_components.clear()
        original_monitor_brightness = None
        original_gamma_ramp = None

        if DISPLAY_USE_HARDWARE_BRIGHTNESS:
            try:
                original_monitor_brightness = get_primary_monitor_brightness()
                save_display_restore_state(original_monitor_brightness)
                set_primary_monitor_brightness_values(
                    build_boosted_brightness_values(original_monitor_brightness)
                )
                display_boost_components.add("brightness")
            except Exception as exc:
                if original_monitor_brightness is not None:
                    try:
                        original_values = [current for _, current, _ in original_monitor_brightness]
                        set_primary_monitor_brightness_values(original_values)
                        clear_display_restore_state()
                    except Exception:
                        pass
                original_monitor_brightness = None
                warnings.append(f"brightness unavailable: {exc}")

        if DISPLAY_USE_GAMMA_RAMP:
            try:
                original_gamma_ramp = get_gamma_ramp()
                set_gamma_ramp(build_boosted_gamma_ramp(original_gamma_ramp))
                display_boost_components.add("gamma")
            except Exception as exc:
                original_gamma_ramp = None
                warnings.append(f"gamma unavailable: {exc}")

        display_boost_enabled = bool(display_boost_components)
        if display_boost_enabled:
            parts = " + ".join(sorted(display_boost_components))
            status(f"\nDisplay boost ON ({parts})", "green")
        else:
            status("\nDisplay boost could not be enabled.", "red")

        for warning in warnings:
            status(f"  {warning}", "yellow")
        return

    warnings = []

    if "gamma" in display_boost_components and original_gamma_ramp is not None:
        try:
            set_gamma_ramp(original_gamma_ramp)
        except Exception as exc:
            warnings.append(f"gamma restore failed: {exc}")

    if "brightness" in display_boost_components and original_monitor_brightness is not None:
        try:
            original_values = [current for _, current, _ in original_monitor_brightness]
            set_primary_monitor_brightness_values(original_values)
            clear_display_restore_state()
        except Exception as exc:
            warnings.append(f"brightness restore failed: {exc}")

    display_boost_components.clear()
    original_gamma_ramp = None
    original_monitor_brightness = None
    display_boost_enabled = False
    status("\nDisplay boost OFF", "yellow")
    for warning in warnings:
        status(f"  {warning}", "yellow")


def tap_quick_use_slot(slot_key: str) -> None:
    slot_scan = SCAN_CODES[slot_key]
    quick_use_scan = SCAN_CODES[QUICK_USE_HOLD_KEY]
    lifted_shift_keys = (
        held_shift_keys() if TEMPORARILY_RELEASE_SHIFT_WHILE_USING else []
    )
    quick_use_is_down = False
    slot_is_down = False

    try:
        if lifted_shift_keys:
            release_keys(lifted_shift_keys)
            msleep(DELAY_AFTER_SHIFT_RELEASE_MS)

        send_scan(quick_use_scan)
        quick_use_is_down = True
        msleep(DELAY_AFTER_ALT_DOWN_MS)

        send_scan(slot_scan)
        slot_is_down = True
        msleep(DELAY_SLOT_HOLD_MS)
        send_scan(slot_scan, key_up=True)
        slot_is_down = False

        msleep(DELAY_BEFORE_ALT_UP_MS)
    finally:
        if slot_is_down:
            send_scan(slot_scan, key_up=True)
        if quick_use_is_down:
            send_scan(quick_use_scan, key_up=True)
        if lifted_shift_keys and RESTORE_SHIFT_AFTER_QUICK_USE:
            press_keys(lifted_shift_keys)
            msleep(DELAY_AFTER_SHIFT_RESTORE_MS)


def register_key_action(
    hotkey_ids: dict[int, tuple[str, str]],
    hotkey_id: int,
    hotkey_key: str,
    action_type: str,
    action_value: str,
    include_shift_variant: bool,
) -> int:
    if hotkey_key not in VK_CODES:
        raise ValueError(f"Unsupported hotkey: {hotkey_key!r}")

    modifiers_to_register = [MOD_NOREPEAT]
    if include_shift_variant:
        modifiers_to_register.append(MOD_SHIFT | MOD_NOREPEAT)

    for modifiers in modifiers_to_register:
        hotkey_label = key_label(hotkey_key)
        if modifiers & MOD_SHIFT:
            hotkey_label = f"Shift + {hotkey_label}"

        ctypes.set_last_error(0)
        ok = user32.RegisterHotKey(None, hotkey_id, modifiers, VK_CODES[hotkey_key])
        if not ok:
            error_code = ctypes.get_last_error()
            if error_code == 1409:
                status(
                    f"\nWarning: {hotkey_label} is already registered by another app/script, so I skipped it.",
                    "yellow",
                )
                status("Close any older macro CMD windows if you expected this key to work here.", "dim")
                continue

            raise ctypes.WinError(error_code)

        hotkey_ids[hotkey_id] = (action_type, action_value)
        hotkey_id += 1

    return hotkey_id


def register_hotkeys() -> dict[int, tuple[str, str]]:
    hotkey_ids: dict[int, tuple[str, str]] = {}
    hotkey_id = 1

    if QUICK_USE_HOLD_KEY not in SCAN_CODES:
        raise ValueError(f"Unsupported quick-use hold key: {QUICK_USE_HOLD_KEY!r}")

    for hotkey_key, slot_key in HOTKEYS.items():
        if slot_key not in SCAN_CODES:
            raise ValueError(f"Unsupported slot key: {slot_key!r}")

        hotkey_id = register_key_action(
            hotkey_ids,
            hotkey_id,
            hotkey_key,
            ACTION_QUICK_USE,
            slot_key,
            REGISTER_HOTKEYS_WHILE_SHIFT_HELD,
        )

    if AUTORUN_TOGGLE_KEY and not USE_PHYSICAL_HOOK_FOR_AUTORUN_TOGGLE:
        for key_name in AUTORUN_HOLD_KEYS:
            if key_name not in SCAN_CODES:
                raise ValueError(f"Unsupported autorun hold key: {key_name!r}")

        hotkey_id = register_key_action(
            hotkey_ids,
            hotkey_id,
            AUTORUN_TOGGLE_KEY,
            ACTION_AUTORUN_TOGGLE,
            AUTORUN_TOGGLE_KEY,
            REGISTER_AUTORUN_WHILE_SHIFT_HELD,
        )

    if DISPLAY_BOOST_TOGGLE_KEY:
        hotkey_id = register_key_action(
            hotkey_ids,
            hotkey_id,
            DISPLAY_BOOST_TOGGLE_KEY,
            ACTION_DISPLAY_BOOST_TOGGLE,
            DISPLAY_BOOST_TOGGLE_KEY,
            REGISTER_DISPLAY_BOOST_WHILE_SHIFT_HELD,
        )

    return hotkey_ids


def unregister_hotkeys(hotkey_ids: dict[int, tuple[str, str]]) -> None:
    for hotkey_id in hotkey_ids:
        user32.UnregisterHotKey(None, hotkey_id)


def enable_hotkeys() -> None:
    global registered_hotkeys

    if not registered_hotkeys:
        registered_hotkeys = register_hotkeys()
        if not registered_hotkeys:
            status(
                "\nNo global hotkeys were registered. Another macro window may still be running.",
                "yellow",
            )


def disable_hotkeys() -> None:
    global registered_hotkeys

    if registered_hotkeys:
        unregister_hotkeys(registered_hotkeys)
        registered_hotkeys = {}


def toggle_macros_paused() -> None:
    global macros_paused

    macros_paused = not macros_paused
    if macros_paused:
        disable_hotkeys()
        if RELEASE_AUTORUN_WHEN_PAUSED:
            set_autorun(False)
        if RESTORE_DISPLAY_WHEN_PAUSED:
            set_display_boost(False)
        status("\nMacros PAUSED", "yellow")
    else:
        enable_hotkeys()
        status("\nMacros RESUMED", "green")


def toggle_autorun_from_hook() -> None:
    if macros_paused:
        return

    try:
        set_autorun(not autorun_enabled)
    except Exception:
        print("\nError while toggling autorun:")
        traceback.print_exc()


def update_pause_combo_state() -> None:
    global pause_combo_is_down

    combo_is_down = all(key_name in physical_keys_down for key_name in PAUSE_TOGGLE_KEYS)
    if combo_is_down and not pause_combo_is_down:
        toggle_macros_paused()
    pause_combo_is_down = combo_is_down


def keyboard_hook_proc(n_code: int, w_param: int, l_param: int) -> int:
    try:
        if n_code == HC_ACTION:
            event = ctypes.cast(
                l_param,
                ctypes.POINTER(KBDLLHOOKSTRUCT),
            ).contents
            is_injected = bool(event.flags & (LLKHF_INJECTED | LLKHF_LOWER_IL_INJECTED))
            key_name = VK_TO_KEY.get(event.vkCode)
            physical_key_name = SCAN_TO_KEY.get(event.scanCode, key_name)

            tracking_key_name = key_name or physical_key_name

            if tracking_key_name and not is_injected:
                was_down = tracking_key_name in physical_keys_down
                if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    physical_keys_down.add(tracking_key_name)
                elif w_param in (WM_KEYUP, WM_SYSKEYUP):
                    physical_keys_down.discard(tracking_key_name)

                if ENABLE_PAUSE_TOGGLE and key_name in PAUSE_TOGGLE_KEYS:
                    update_pause_combo_state()

                if (
                    USE_PHYSICAL_HOOK_FOR_AUTORUN_TOGGLE
                    and AUTORUN_TOGGLE_KEY
                    and physical_key_name == AUTORUN_TOGGLE_KEY
                ):
                    if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN) and not was_down:
                        toggle_autorun_from_hook()

                    if SUPPRESS_AUTORUN_TOGGLE_KEY and not macros_paused:
                        return 1
    except Exception:
        print("\nError inside keyboard hook:")
        traceback.print_exc()

    return user32.CallNextHookEx(keyboard_hook_handle, n_code, w_param, l_param)


def install_keyboard_hook() -> None:
    global keyboard_hook_handle, keyboard_proc_ref

    if not (ENABLE_PAUSE_TOGGLE or USE_PHYSICAL_HOOK_FOR_AUTORUN_TOGGLE):
        return

    if ENABLE_PAUSE_TOGGLE:
        for key_name in PAUSE_TOGGLE_KEYS:
            if key_name not in VK_CODES:
                raise ValueError(f"Unsupported pause toggle key: {key_name!r}")

    if USE_PHYSICAL_HOOK_FOR_AUTORUN_TOGGLE and AUTORUN_TOGGLE_KEY not in SCAN_CODES:
        raise ValueError(f"Unsupported autorun toggle key: {AUTORUN_TOGGLE_KEY!r}")

    keyboard_proc_ref = HOOKPROC(keyboard_hook_proc)
    module_handle = kernel32.GetModuleHandleW(None)
    keyboard_hook_handle = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL,
        keyboard_proc_ref,
        module_handle,
        0,
    )
    if not keyboard_hook_handle:
        raise ctypes.WinError(ctypes.get_last_error())


def uninstall_keyboard_hook() -> None:
    global keyboard_hook_handle, keyboard_proc_ref

    if keyboard_hook_handle:
        user32.UnhookWindowsHookEx(keyboard_hook_handle)
        keyboard_hook_handle = None
        keyboard_proc_ref = None


def main() -> None:
    enable_console_colors()
    apply_profile(choose_profile_name())
    restore_display_state_from_file()
    if not macros_paused:
        enable_hotkeys()
    install_keyboard_hook()
    print_active_layout()

    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                action = registered_hotkeys.get(msg.wParam)
                if action:
                    action_type, action_value = action

                    if macros_paused:
                        continue

                    try:
                        if action_type == ACTION_QUICK_USE:
                            disable_hotkeys()
                            tap_quick_use_slot(action_value)
                        elif action_type == ACTION_AUTORUN_TOGGLE:
                            set_autorun(not autorun_enabled)
                        elif action_type == ACTION_DISPLAY_BOOST_TOGGLE:
                            set_display_boost(not display_boost_enabled)
                    except Exception:
                        print("\nError while running hotkey action:")
                        traceback.print_exc()
                        print("\nThe script is still running. Press Ctrl+C to stop.")
                    finally:
                        if not macros_paused:
                            enable_hotkeys()
    except KeyboardInterrupt:
        pass
    finally:
        set_autorun(False)
        if RESTORE_DISPLAY_ON_EXIT:
            set_display_boost(False)
        disable_hotkeys()
        uninstall_keyboard_hook()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("\nFatal error:")
        traceback.print_exc()
        input("\nPress Enter to close...")
