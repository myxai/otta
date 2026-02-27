"""DeskManager — pywebview window lifecycle + pystray system tray.

Closing the main window hides it to the system tray instead of quitting.
Double-click the tray icon (or use the right-click menu) to restore.

Usage (from app.py):
    from desk_manager import DeskManager
    mgr = DeskManager(port=19280)
    mgr.run()                     # blocks until quit
"""

import contextlib
import locale
import math
import sys
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_webview_available = False
_pystray_available = False

try:
    import webview

    _webview_available = True
except ImportError:
    pass

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont

    _pystray_available = True
except ImportError:
    pass


# --------------------------------------------------------------------------- #
# Tray icon generation — render the 🌀 emoji onto a transparent icon
# --------------------------------------------------------------------------- #


def _make_tray_icon(size: int = 64) -> "Image.Image":
    """Draw a 🌀-style swirl icon programmatically."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size / 2, size / 2
    draw.ellipse([1, 1, size - 1, size - 1], fill=(30, 30, 46, 255))

    steps = 200
    max_r = size * 0.38
    for i in range(steps):
        t = i / steps
        angle = t * 4 * math.pi
        r = max_r * t
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        dot = max(1.5, 3.0 * (1 - t * 0.5))
        alpha = int(255 * (0.5 + 0.5 * t))
        color = (137, 180, 250, alpha)
        draw.ellipse([x - dot, y - dot, x + dot, y + dot], fill=color)

    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(137, 180, 250, 255))
    return img


# --------------------------------------------------------------------------- #
# DeskManager
# --------------------------------------------------------------------------- #


class DeskManager:
    """Coordinates the main webview window and the system tray icon."""

    def __init__(self, port: int = 19280, api_token: str | None = None):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self.api_token = api_token

        self.main_window: object | None = None
        self._tray: object | None = None
        self._tray_thread: threading.Thread | None = None
        self._resume_thread: threading.Thread | None = None
        self._quitting = False

        self._get_unread_count = None  # callable, injected from app.py
        self._get_token_usage = None  # callable, injected from app.py
        self._on_resume: Callable | None = None  # callable, injected from app.py
        self.lang: str = self._detect_lang()  # "zh" or "en"
        self.close_action: str = "minimize"  # "minimize" (hide to tray) or "quit"

    # ---- i18n ------------------------------------------------------------- #

    _T = {
        "zh": {
            "open": "打开 MyxAI Desk",
            "quit": "退出",
            "unread": "📬 未读消息: {}",
            "no_unread": "📭 无未读消息",
            "tokens": "{} 今日 Token: {}",
            "tokens_na": "🔥 今日 Token: --",
            "wan": "{}万",
        },
        "en": {
            "open": "Open MyxAI Desk",
            "quit": "Quit",
            "unread": "📬 Unread: {}",
            "no_unread": "📭 No unread messages",
            "tokens": "{} Today Token: {}",
            "tokens_na": "🔥 Today Token: --",
            "wan": "{}万",
        },
    }

    @staticmethod
    def _detect_lang() -> str:
        try:
            loc = locale.getdefaultlocale()[0] or ""
        except Exception:
            loc = ""
        return "zh" if loc.lower().startswith("zh") else "en"

    def _t(self, key: str) -> str:
        return self._T.get(self.lang, self._T["en"]).get(key, key)

    # ---- window show / hide ----------------------------------------------- #

    def show_main(self):
        w = self.main_window
        if not w:
            return
        for fn in ("show", "restore", "maximize", "bring_to_front", "focus"):
            if hasattr(w, fn):
                try:
                    getattr(w, fn)()
                except Exception:
                    continue

    def hide_main(self):
        w = self.main_window
        if not w:
            return
        for fn in ("hide", "minimize"):
            if hasattr(w, fn):
                try:
                    getattr(w, fn)()
                    return
                except Exception:
                    continue

    # ---- tray ------------------------------------------------------------- #

    def start_tray(self):
        if not _pystray_available:
            return
        self._tray_thread = threading.Thread(target=self._tray_run, daemon=True)
        self._tray_thread.start()

    def _tray_run(self):
        image = _make_tray_icon()
        menu = pystray.Menu(
            pystray.MenuItem(lambda _: self._t("open"), self._on_tray_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self._label_unread, self._on_tray_unread),
            pystray.MenuItem(self._label_tokens, self._on_tray_tokens),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda _: self._t("quit"), self._on_tray_quit),
        )
        self._tray = pystray.Icon("myxai_desk", image, "MyxAI Desk", menu)
        self._tray.run()

    def _label_unread(self, item) -> str:
        try:
            if self._get_unread_count:
                n = self._get_unread_count()
                if n > 0:
                    return self._t("unread").format(n)
            return self._t("no_unread")
        except Exception:
            return self._t("no_unread")

    def _label_tokens(self, item) -> str:
        try:
            if self._get_token_usage:
                usage = self._get_token_usage()
                total = usage.get("total_tokens", 0)
                cost = usage.get("cost", 0)
                alert_level = usage.get("alert_level", "green")
                
                # Select indicator emoji based on alert level
                if alert_level == "red":
                    indicator = "🔴"
                elif alert_level == "yellow":
                    indicator = "🟡"
                else:
                    indicator = "🟢"
                
                # Format token display
                if total >= 10000:
                    display = self._t("wan").format(f"{total / 10000:.1f}")
                else:
                    display = f"{total:,}"
                
                # Add cost if configured
                if cost > 0:
                    display += f" ¥{cost:.2f}"
                
                return self._t("tokens").format(indicator, display)
            return self._t("tokens_na")
        except Exception:
            return self._t("tokens_na")

    def _stop_tray(self):
        if self._tray:
            with contextlib.suppress(Exception):
                self._tray.stop()
            self._tray = None

    def _on_tray_open(self, icon=None, item=None):
        self.show_main()

    def _on_tray_unread(self, icon=None, item=None):
        self.show_main()
        self._navigate_page("reports")

    def _on_tray_tokens(self, icon=None, item=None):
        self.show_main()
        self._navigate_page("stats")

    def _on_tray_quit(self, icon=None, item=None):
        self.quit()

    def _navigate_page(self, page: str):
        w = self.main_window
        if not w:
            return
        with contextlib.suppress(Exception):
            w.evaluate_js(f"if(typeof switchPage==='function')switchPage('{page}');")

    # ---- system resume listener (Windows) --------------------------------- #

    def start_resume_listener(self):
        """Start a background thread that listens for OS sleep/resume events.

        On Windows, uses ctypes to listen for WM_POWERBROADCAST messages.
        On other platforms this is a no-op (catch-up still works via startup
        and the periodic heartbeat tick).
        """
        if sys.platform != "win32" or not self._on_resume:
            return
        self._resume_thread = threading.Thread(
            target=self._resume_listener_win32,
            daemon=True,
        )
        self._resume_thread.start()

    def _resume_listener_win32(self):
        """Hidden window message loop that catches PBT_APMRESUMEAUTOMATIC."""
        try:
            import ctypes
            import ctypes.wintypes as wt

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            WM_POWERBROADCAST = 0x0218
            PBT_APMRESUMEAUTOMATIC = 0x0012
            PBT_APMRESUMESUSPEND = 0x0007

            LRESULT = ctypes.c_ssize_t

            user32.DefWindowProcW.argtypes = [
                wt.HWND,
                wt.UINT,
                wt.WPARAM,
                wt.LPARAM,
            ]
            user32.DefWindowProcW.restype = LRESULT

            WNDPROC = ctypes.WINFUNCTYPE(
                LRESULT,
                wt.HWND,
                wt.UINT,
                wt.WPARAM,
                wt.LPARAM,
            )

            def wnd_proc(hwnd, msg, wparam, lparam):
                if msg == WM_POWERBROADCAST:
                    if wparam in (PBT_APMRESUMEAUTOMATIC, PBT_APMRESUMESUSPEND):
                        print("[desk_manager] OS resume detected — running catch-up")
                        if self._on_resume:
                            threading.Thread(
                                target=self._on_resume,
                                daemon=True,
                            ).start()
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            wnd_proc_cb = WNDPROC(wnd_proc)

            class WNDCLASSEXW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wt.UINT),
                    ("style", wt.UINT),
                    ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wt.HINSTANCE),
                    ("hIcon", wt.HICON),
                    ("hCursor", wt.HANDLE),
                    ("hbrBackground", wt.HBRUSH),
                    ("lpszMenuName", wt.LPCWSTR),
                    ("lpszClassName", wt.LPCWSTR),
                    ("hIconSm", wt.HICON),
                ]

            hinstance = kernel32.GetModuleHandleW(None)
            class_name = "MyxAI_PowerMonitor"

            wc = WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wc.lpfnWndProc = wnd_proc_cb
            wc.hInstance = hinstance
            wc.lpszClassName = class_name

            user32.RegisterClassExW.restype = wt.ATOM
            atom = user32.RegisterClassExW(ctypes.byref(wc))
            if not atom:
                err = kernel32.GetLastError()
                if err != 1410:  # ERROR_CLASS_ALREADY_EXISTS is fine
                    print(f"[desk_manager] Failed to register power monitor class (err={err})")
                    return

            user32.CreateWindowExW.restype = wt.HWND
            hwnd = user32.CreateWindowExW(
                0,
                class_name,
                "MyxAI Power Monitor",
                0,
                0,
                0,
                0,
                0,
                None,
                None,
                hinstance,
                None,
            )
            if not hwnd:
                print("[desk_manager] Failed to create power monitor window")
                return

            print("[desk_manager] Power resume listener active")

            msg = wt.MSG()
            while not self._quitting:
                ret = user32.GetMessageW(ctypes.byref(msg), hwnd, 0, 0)
                if ret <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        except Exception as exc:
            print(f"[desk_manager] Resume listener error (non-fatal): {exc}")

    # ---- quit ------------------------------------------------------------- #

    def quit(self):
        """Tear down tray and destroy all webview windows."""
        if self._quitting:
            return
        self._quitting = True
        self._stop_tray()
        try:
            for win in webview.windows[:]:
                win.destroy()
        except Exception:
            pass

    # ---- closing event handler -------------------------------------------- #

    def on_main_closing(self):
        """Intercept the native X button.

        When ``close_action`` is ``"minimize"`` (default), hides the window
        to the system tray.  When ``"quit"``, terminates the application.

        Returns ``False`` to cancel the real close (hide mode).
        """
        if self._quitting:
            return True
        if self.close_action == "quit":
            self.quit()
            return True
        self.hide_main()
        return False

    # ---- API token injection --------------------------------------------- #

    def _inject_api_token(self):
        """Inject the API token into the webview JS context.

        Called on every ``loaded`` event so the token survives page
        navigations and refreshes inside the pywebview window.
        """
        if self.main_window and self.api_token:
            with contextlib.suppress(Exception):
                self.main_window.evaluate_js(
                    f"window.__myxai_token = '{self.api_token}';"
                    "sessionStorage.setItem('__myxai_token', window.__myxai_token);"
                )

    # ---- webview entry point ---------------------------------------------- #

    def run(self, start_func=None):
        """Create the main window and enter the webview event loop (blocking).

        If ``start_func`` is provided it will be called with the main window
        as its sole argument (runs in a background thread by pywebview).

        ``background_color`` is set to match the app's dark theme so the
        window is dark from the first frame — no white flash even if Flask
        is still starting up.
        """
        if not _webview_available:
            raise RuntimeError("pywebview is not installed")

        self.main_window = webview.create_window(
            "MyxAI Desk",
            self.base_url,
            width=1280,
            height=860,
            min_size=(960, 640),
            maximized=True,
            background_color="#1e1e2e",
        )

        with contextlib.suppress(Exception):
            self.main_window.events.closing += self.on_main_closing

        if self.api_token:
            with contextlib.suppress(Exception):
                self.main_window.events.loaded += self._inject_api_token

        self.start_tray()
        self.start_resume_listener()

        kwargs = {}
        if start_func:
            kwargs["func"] = start_func
            kwargs["args"] = [self.main_window]

        webview.start(**kwargs)
