import platform
import sys


def get_active_window():
    if platform.system() == "Windows":
        import pygetwindow as gw

        win = gw.getActiveWindow()
        if win is not None:
            return {
                "region": (win.left, win.top, win.width, win.height),
                "title": win.title,
            }
    elif platform.system() == "Darwin":
        from AppKit import NSWorkspace
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListOptionOnScreenOnly,
        )

        active_app = NSWorkspace.sharedWorkspace().activeApplication()
        for window in CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly, kCGNullWindowID
        ):
            if window["kCGWindowOwnerName"] == active_app["NSApplicationName"]:
                return {
                    "region": window["kCGWindowBounds"],
                    "title": window.get("kCGWindowName", "Unknown"),
                }
    elif platform.system() == "Linux":
        from ewmh import EWMH
        from Xlib.display import Display

        ewmh = EWMH()
        win = ewmh.getActiveWindow()
        if win is not None:
            geom = win.get_geometry()
            return {
                "region": (geom.x, geom.y, geom.width, geom.height),
                "title": win.get_wm_name(),
            }
    else:
        print("Unsupported platform: ", platform.system())
        sys.exit(1)
