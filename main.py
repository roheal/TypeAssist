#!/usr/bin/env python3
"""
TypeAssist (main.py)

- Tkinter app (auto typer)
- Auto-update: checks GitHub releases for https://github.com/roheal/AutoType
  and downloads an asset if a newer version exists.
- Minimal external deps: pyautogui, keyboard (optional), requests, pillow (icon conversion only)
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading, time, sys, os, queue
import pyautogui
import json

# For update check & download
try:
    import requests
except Exception:
    requests = None

# Optional keyboard (global hotkeys)
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except Exception:
    KEYBOARD_AVAILABLE = False

# -------- App version (bump this before each released version) --------
__version__ = "1.0.0"

# GitHub repo to check releases
GITHUB_OWNER = "roheal"
GITHUB_REPO = "AutoType"   # your repo
GITHUB_API_RELEASES_LATEST = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

# UI / settings
settings = {
    "dark_mode": False,
    "hotkeys_enabled": False,
    "start_hotkey": "f8",
    "pause_hotkey": "f9",
}

# threading helpers
root_event_queue = queue.Queue()
stop_event = threading.Event()
pause_event = threading.Event()
typing_thread = None

def set_status(lbl, txt):
    lbl.configure(text=txt)

# ---------- Updater functions ----------
def check_for_update(status_label, ask_if_update=True):
    """
    Checks GitHub latest release. If newer than __version__, return dict with info.
    If requests not available or error, return None.
    """
    if not requests:
        set_status(status_label, "Update check skipped (requests not installed).")
        return None

    try:
        resp = requests.get(GITHUB_API_RELEASES_LATEST, timeout=8, headers={"Accept":"application/vnd.github.v3+json"})
        if resp.status_code != 200:
            set_status(status_label, f"Update check failed: HTTP {resp.status_code}")
            return None
        data = resp.json()
        remote_tag = str(data.get("tag_name") or data.get("name") or "")
        # Normalize tag (strip leading 'v')
        if remote_tag.startswith("v"):
            remote_tag = remote_tag[1:]
        # compare versions (simple lexicographic fallback)
        if remote_tag and remote_tag != __version__:
            # there is a version difference; we treat any different tag as newer.
            release_info = {
                "tag": remote_tag,
                "body": data.get("body", ""),
                "assets": data.get("assets", []),
                "html_url": data.get("html_url"),
            }
            if ask_if_update:
                if messagebox.askyesno("Update available",
                                       f"A new version ({remote_tag}) is available. You have {__version__}.\nDo you want to download it now?"):
                    download_release_asset(release_info, status_label)
            return release_info
        else:
            set_status(status_label, "No updates found.")
            return None
    except Exception as e:
        set_status(status_label, f"Update check failed: {e}")
        return None

def download_release_asset(release_info, status_label):
    """
    Select an asset to download (prefer .zip or .exe). Downloads to a temp file.
    After download, prompt the user and launch it.
    """
    assets = release_info.get("assets", [])
    if not assets:
        messagebox.showinfo("No downloadable asset", "Release has no uploaded assets to download.")
        return
    # prefer .exe or .zip
    preferred = None
    for ext in (".exe", ".zip", ".msi"):
        for a in assets:
            name = a.get("name","").lower()
            if name.endswith(ext):
                preferred = a
                break
        if preferred:
            break
    if not preferred:
        preferred = assets[0]

    download_url = preferred.get("browser_download_url")
    if not download_url:
        messagebox.showerror("Download failed", "No downloadable URL found for the chosen asset.")
        return

    try:
        set_status(status_label, "Downloading update...")
        # stream download
        r = requests.get(download_url, stream=True, timeout=15)
        total = int(r.headers.get("content-length") or 0)
        tmp_path = os.path.join(os.path.expanduser("~"), "Downloads", preferred.get("name"))
        with open(tmp_path, "wb") as f:
            dl = 0
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    dl += len(chunk)
                    # update status (percentage)
                    if total:
                        pct = int(dl/total*100)
                        set_status(status_label, f"Downloading update... {pct}%")
        set_status(status_label, "Download complete.")
        # Ask to run installer (if .exe) or open containing folder (if zip)
        if tmp_path.lower().endswith(".exe") or tmp_path.lower().endswith(".msi"):
            if messagebox.askyesno("Run installer", f"Downloaded to {tmp_path}\nRun installer now?"):
                try:
                    os.startfile(tmp_path)
                except Exception as e:
                    messagebox.showerror("Run failed", f"Could not run installer: {e}")
        else:
            if messagebox.askyesno("Open file", f"Downloaded to {tmp_path}\nOpen folder?"):
                folder = os.path.dirname(tmp_path)
                os.startfile(folder)
    except Exception as e:
        messagebox.showerror("Download failed", f"Could not download update: {e}")
        set_status(status_label, f"Download failed: {e}")

# ---------- Typing engine ----------
def type_text_worker(text, char_interval, status_label, start_delay=2.0):
    set_status(status_label, f"Starting in {start_delay:.1f}s...")
    for i in range(int(start_delay*10)):
        if stop_event.is_set():
            set_status(status_label, "Cancelled.")
            return
        time.sleep(0.1)
    set_status(status_label, "Typing...")
    try:
        for ch in text:
            if stop_event.is_set():
                set_status(status_label, "Stopped.")
                return
            while pause_event.is_set() and not stop_event.is_set():
                set_status(status_label, "Paused.")
                time.sleep(0.1)
            pyautogui.write(ch)
            time.sleep(char_interval)
        set_status(status_label, "Finished.")
    except Exception as e:
        set_status(status_label, f"Typing error: {e}")

def start_typing(text_widget, speed_val, status_label):
    global typing_thread, stop_event, pause_event
    raw = text_widget.get("1.0", tk.END)
    if not raw.strip():
        messagebox.showinfo("No text", "Please paste or type text first.")
        return
    stop_event.clear()
    pause_event.clear()
    # map speed_val (1..100) to interval (0.12..0.001)
    interval = max(0.001, 0.12 - (speed_val / 100.0) * 0.11)
    typing_thread = threading.Thread(target=type_text_worker, args=(raw, interval, status_label), daemon=True)
    typing_thread.start()

def stop_typing():
    stop_event.set()

def toggle_pause(btn, status_label):
    if pause_event.is_set():
        pause_event.clear()
        btn.configure(text="Pause")
        set_status(status_label, "Resumed.")
    else:
        pause_event.set()
        btn.configure(text="Resume")
        set_status(status_label, "Paused.")

# ---------- UI build ----------
def build_ui():
    root = tk.Tk()
    root.title("TypeAssist")
    root.geometry("560x420")
    root.resizable(False, False)

    # top frame (speed + settings)
    top = tk.Frame(root)
    top.pack(fill="x", padx=10, pady=(8,4))
    tk.Label(top, text="Speed").pack(side="left")
    speed = tk.Scale(top, from_=1, to=100, orient="horizontal", length=260)
    speed.set(70)
    speed.pack(side="left", padx=(6, 14))
    def open_settings():
        open_settings_window(root, status_label)
    tk.Button(top, text="Settings", width=10, command=open_settings).pack(side="right")

    tk.Label(root, text="TypeAssist", font=("Segoe UI", 14, "bold")).pack(pady=(6,2))
    tf = tk.Frame(root)
    tf.pack(padx=10, fill="both")
    tk.Button(tf, text="Paste", width=10, command=lambda: paste_clipboard(text_area, status_label)).grid(row=0, column=0, sticky="n", padx=(0,8), pady=(4,0))
    text_area = scrolledtext.ScrolledText(tf, wrap="word", height=10, width=56)
    text_area.grid(row=0, column=1, pady=(4,0))

    controls = tk.Frame(root)
    controls.pack(fill="x", padx=10, pady=12)
    start_btn = tk.Button(controls, text="Start Typing", width=18, command=lambda: start_typing(text_area, speed.get(), status_label))
    start_btn.pack(side="left", padx=(0,8))
    pause_btn = tk.Button(controls, text="Pause", width=12, command=lambda: toggle_pause(pause_btn, status_label))
    pause_btn.pack(side="left", padx=(0,8))
    stop_btn = tk.Button(controls, text="Stop", width=12, command=stop_typing)
    stop_btn.pack(side="left", padx=(0,8))

    status_frame = tk.Frame(root)
    status_frame.pack(fill="x", padx=10, pady=(0,8))
    status_label = tk.Label(status_frame, text="Ready.", anchor="w")
    status_label.pack(fill="x")

    # Updater button
    up_btn = tk.Button(root, text="Check for Updates", command=lambda: threading.Thread(target=check_for_update, args=(status_label,), daemon=True).start())
    up_btn.pack(pady=(0,6))

    # initial status
    if not requests:
        set_status(status_label, "Requests not available — update check disabled.")
    if not KEYBOARD_AVAILABLE:
        set_status(status_label, "Keyboard module not found — global hotkeys disabled.")

    # on close: stop threads
    def on_close():
        stop_event.set()
        try:
            root.destroy()
        except:
            pass
        sys.exit(0)
    root.protocol("WM_DELETE_WINDOW", on_close)

    # Support global hotkeys if available
    if KEYBOARD_AVAILABLE:
        def on_hot_start():
            start_btn.invoke()
        def on_hot_pause():
            pause_btn.invoke()
        try:
            keyboard.add_hotkey(settings["start_hotkey"], on_hot_start)
            keyboard.add_hotkey(settings["pause_hotkey"], on_hot_pause)
        except Exception:
            pass

    return root

def paste_clipboard(text_widget, status_label):
    try:
        c = text_widget.clipboard_get()
    except Exception:
        c = ""
    if not c:
        messagebox.showinfo("Clipboard empty", "Clipboard empty or non-text.")
        return
    text_widget.delete("1.0", tk.END)
    text_widget.insert(tk.END, c)
    set_status(status_label, "Pasted from clipboard.")

def open_settings_window(parent, status_label):
    win = tk.Toplevel(parent)
    win.title("Settings - TypeAssist")
    win.geometry("420x220")
    win.resizable(False, False)
    f = tk.Frame(win)
    f.pack(padx=12, pady=12, fill="both", expand=True)

    # Theme toggle (placeholder - you can implement actual theme later)
    theme_label = tk.Label(f, text="Theme:")
    theme_label.grid(row=0, column=0, sticky="w")
    def toggle_theme_btn(btn):
        settings["dark_mode"] = not settings["dark_mode"]
        btn.configure(text="Dark Mode" if not settings["dark_mode"] else "Light Mode")
    theme_btn = tk.Button(f, text="Dark Mode", width=12, command=lambda: toggle_theme_btn(theme_btn))
    theme_btn.grid(row=0, column=1, sticky="w", padx=8, pady=6)

    # Hotkeys toggle
    hk_label = tk.Label(f, text="Hotkeys:")
    hk_label.grid(row=1, column=0, sticky="w")
    def toggle_hotkeys(btn):
        settings["hotkeys_enabled"] = not settings["hotkeys_enabled"]
        btn.configure(text="Enabled" if settings["hotkeys_enabled"] else "Disabled")
    hk_btn = tk.Button(f, text="Disabled", width=12, command=lambda: toggle_hotkeys(hk_btn))
    hk_btn.grid(row=1, column=1, sticky="w", padx=8, pady=6)

    tk.Button(f, text="Back", width=12, command=win.destroy).grid(row=4, column=0, columnspan=2, pady=(12,0))

# ---------- Start the UI ----------
if __name__ == "__main__":
    app = build_ui()
    app.mainloop()
