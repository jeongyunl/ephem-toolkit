"""Platform helpers for desktop application startup."""

from __future__ import annotations

import ctypes
import sys


def activate_macos_application(platform: str | None = None) -> bool:
    """Activate the current process as a foreground macOS application.

    Returns ``True`` when the macOS Objective-C runtime accepted the activation
    request. Returns ``False`` on non-macOS platforms or when activation cannot
    be performed.
    """
    selected_platform = sys.platform if platform is None else platform
    if not selected_platform.startswith("darwin"):
        return False

    try:
        objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.objc_msgSend.restype = ctypes.c_void_p

        ns_application_class = objc.objc_getClass(b"NSApplication")
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        shared_application = objc.objc_msgSend(
            ns_application_class,
            objc.sel_registerName(b"sharedApplication"),
        )

        objc.objc_msgSend.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_bool,
        ]
        objc.objc_msgSend(
            shared_application,
            objc.sel_registerName(b"activateIgnoringOtherApps:"),
            True,
        )
        return True
    except (AttributeError, OSError, TypeError):
        return False


def activate_application(platform: str | None = None) -> bool:
    """Activate the current desktop application on supported platforms.

    Parameters
    ----------
    platform:
        Optional platform override for tests or callers with preselected
        platform state. Defaults to :data:`sys.platform`.

    Returns
    -------
    bool
        ``True`` when activation was requested successfully; ``False`` when the
        platform has no activation implementation or activation was unavailable.

    Notes
    -----
    This function intentionally only provides macOS activation. Linux and
    Windows window managers do not have an equivalent cross-toolkit process
    activation contract.
    """
    selected_platform = sys.platform if platform is None else platform
    if selected_platform.startswith("darwin"):
        return activate_macos_application(selected_platform)
    return False
