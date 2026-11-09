"""Small native Windows launcher. No Tk, WebView or extra runtime dependency."""

from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
import webbrowser


def show(service, validate_portable, open_browser: bool = True) -> int:
    from portable_update import discover, install

    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

    class WNDCLASS(ctypes.Structure):
        _fields_ = [("style", w.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int), ("hInstance", w.HINSTANCE), ("hIcon", w.HICON),
                    ("hCursor", w.HANDLE), ("hbrBackground", w.HBRUSH), ("lpszMenuName", w.LPCWSTR),
                    ("lpszClassName", w.LPCWSTR)]

    user.DefWindowProcW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
    user.DefWindowProcW.restype = LRESULT
    user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
    user.CreateWindowExW.restype = w.HWND
    user.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
    user.RegisterClassW.restype = w.WORD
    user.GetMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT]
    user.GetMessageW.restype = w.BOOL
    user.DispatchMessageW.argtypes = [ctypes.POINTER(w.MSG)]
    user.DispatchMessageW.restype = LRESULT
    user.TranslateMessage.argtypes = [ctypes.POINTER(w.MSG)]
    user.SendMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
    user.SendMessageW.restype = LRESULT
    user.SetWindowTextW.argtypes = [w.HWND, w.LPCWSTR]
    user.EnableWindow.argtypes = [w.HWND, w.BOOL]
    user.DestroyWindow.argtypes = [w.HWND]
    user.ShowWindow.argtypes = [w.HWND, ctypes.c_int]
    user.UpdateWindow.argtypes = [w.HWND]
    user.SetTimer.argtypes = [w.HWND, ctypes.c_size_t, w.UINT, w.LPVOID]
    user.MessageBoxW.argtypes = [w.HWND, w.LPCWSTR, w.LPCWSTR, w.UINT]
    user.LoadImageW.argtypes = [w.HINSTANCE, w.LPCWSTR, w.UINT, ctypes.c_int, ctypes.c_int, w.UINT]
    user.LoadImageW.restype = w.HANDLE
    user.LoadCursorW.argtypes = [w.HINSTANCE, w.LPVOID]
    user.LoadCursorW.restype = w.HANDLE
    user.IsDialogMessageW.argtypes = [w.HWND, ctypes.POINTER(w.MSG)]
    kernel.GetModuleHandleW.argtypes = [w.LPCWSTR]
    kernel.GetModuleHandleW.restype = w.HMODULE
    gdi.GetStockObject.argtypes = [ctypes.c_int]
    gdi.GetStockObject.restype = w.HANDLE

    instance = kernel.GetModuleHandleW(None)
    messages: queue.Queue = queue.Queue()
    controls = {}
    closing, updating, ready_notified = False, False, False
    update_root: Path | None = None
    launched = False
    switch_requested = False
    start_deadline = time.monotonic() + 30

    def background(function, event):
        def run():
            try:
                messages.put((event, function()))
            except Exception as exc:
                messages.put(("error", str(exc)))
        threading.Thread(target=run, name="portable-update", daemon=True).start()

    def text(value):
        user.SetWindowTextW(controls["status"], value)

    def quit_app(hwnd):
        nonlocal closing
        if updating:
            user.MessageBoxW(hwnd, "Attendez la fin du téléchargement avant de quitter.", "Mise à jour", 0x40)
            return
        if not service.finished.is_set() and user.MessageBoxW(hwnd,
                "Arrêter le service local et fermer Vanguard FAT Studio ?\nEnregistrez les brouillons utiles dans le navigateur.\nL’historique des essais sera conservé.",
                "Quitter Vanguard FAT Studio", 0x24) != 6:
            return
        closing = True
        service.stop()
        text("Arrêt du service et fermeture des fichiers…")
        user.EnableWindow(controls[1], False)
        user.EnableWindow(controls[2], False)

    @WNDPROC
    def window_proc(hwnd, message, wp, lp):
        nonlocal closing, updating, ready_notified, update_root, launched, switch_requested
        if message == 0x0010:  # WM_CLOSE
            quit_app(hwnd)
            return 0
        if message == 0x0002:  # WM_DESTROY
            user.PostQuitMessage(0)
            return 0
        if message == 0x0111:  # WM_COMMAND
            button = wp & 0xffff
            if button == 1 and service.ready and not service.stopping:
                webbrowser.open(service.url)
            elif button == 2 and not updating:
                if update_root:
                    if user.MessageBoxW(hwnd, "Fermer cette version et ouvrir le nouveau portable avec le même dossier de données ?\nEnregistrez vos brouillons avant de continuer.", "Utiliser le nouveau portable", 0x24) == 6:
                        switch_requested = True
                        closing = True
                        service.stop()
                        text("Fermeture avant ouverture de la nouvelle version…")
                else:
                    updating = True
                    user.EnableWindow(controls[2], False)
                    text("Recherche du portable publié sur GitHub…")
                    background(discover, "candidate")
            elif button == 3:
                quit_app(hwnd)
            elif button == 4:
                os.startfile(service.data)
            return 0
        if message == 0x0113:  # WM_TIMER
            if service.server and service.server.started and not ready_notified:
                ready_notified = service.ready = True
                text(f"Prêt · version {service.record['version']}\n{service.url}\nVous pouvez réduire cette fenêtre pendant votre travail.")
                user.EnableWindow(controls[1], True)
                if open_browser:
                    webbrowser.open(service.url)
            if not ready_notified and not service.finished.is_set() and time.monotonic() > start_deadline:
                service.error = "Le démarrage a dépassé le délai prévu. Consultez le journal du lanceur."
                service.stop()
            if service.finished.is_set():
                if closing or (service.stopping and not service.error and not updating):
                    if switch_requested and update_root and not launched:
                        launched = True
                        try:
                            subprocess.Popen([str(update_root / "runtime/pythonw.exe"), "-B", "-X", "utf8",
                                              str(update_root / "launch.py"), "--gui", "--data-dir", str(service.data),
                                              "--port", str(service.port)], cwd=update_root,
                                             creationflags=subprocess.CREATE_NO_WINDOW)
                        except OSError as exc:
                            user.MessageBoxW(hwnd, f"La nouvelle copie n’a pas pu s’ouvrir : {exc}\nOuvrez son lanceur depuis {update_root}.", "Mise à jour préparée", 0x10)
                    user.DestroyWindow(hwnd)
                    return 0
                if service.error:
                    text(service.error + "\nLe journal portable-launcher.log est dans le dossier de données.")
                    user.EnableWindow(controls[1], False)
            try:
                while True:
                    event, value = messages.get_nowait()
                    if event == "candidate":
                        current_source = service.record.get("source_commit", "")
                        if (len(current_source) >= 7 and value["release"].removeprefix("v") == service.record["version"]
                                and re.search(r"(?:^|[-_.])" + re.escape(current_source[:7]) + r"(?:[-_.]|$)", value["name"])):
                            updating = False
                            text("Ce portable correspond à la version publiée sur GitHub.\nVersion : " + service.record["version"])
                            user.EnableWindow(controls[2], True)
                            continue
                        description = (f"Version actuelle : {service.record['version']}\nSource : {service.record.get('source_commit', '')[:12] or 'non renseignée'}\n"
                                       f"Portable publié : {value['release']}\n{value['name']}\nSHA-256 : {value['sha256']}\n\n"
                                       "Télécharger et vérifier dans un nouveau dossier à côté de cette version ?\nLes projets et l’historique restent dans leur dossier actuel.")
                        if user.MessageBoxW(hwnd, description, "Préparer une mise à jour", 0x24) == 6:
                            destination = service.root.parent / value["name"][:-4]
                            text("Téléchargement et vérification du nouveau portable…")
                            background(lambda candidate=value, target=destination: install(candidate, target, validate_portable), "installed")
                        else:
                            updating = False
                            text("Recherche terminée. La version actuelle reste ouverte.")
                            user.EnableWindow(controls[2], True)
                    elif event == "installed":
                        updating = False
                        manifest = json.loads((value / "portable-manifest.json").read_text(encoding="utf-8"))
                        if manifest.get("application_wheel_sha256") == service.record.get("wheel_sha256"):
                            text(f"Le portable publié contient déjà la même application.\nCopie vérifiée : {value}")
                        else:
                            update_root = value
                            text(f"Portable vérifié : {manifest.get('application_version', '?')}\nSource : {manifest.get('source_commit', '')[:12]}\n{value}")
                            user.SetWindowTextW(controls[2], "Utiliser la mise à jour")
                        user.EnableWindow(controls[2], True)
                    elif event == "error":
                        updating = False
                        text(value + "\nLa version actuelle et les données sont conservées.")
                        user.EnableWindow(controls[2], True)
            except queue.Empty:
                pass
            return 0
        return user.DefWindowProcW(hwnd, message, wp, lp)

    class_name = "VanguardPortable" + service.record["instance_id"]
    icon = user.LoadImageW(None, str(service.root / "vanguard.ico"), 1, 0, 0, 0x10 | 0x40)
    definition = WNDCLASS(0, window_proc, 0, 0, instance, icon, user.LoadCursorW(None, 32512), 6, None, class_name)
    if not user.RegisterClassW(ctypes.byref(definition)):
        raise ctypes.WinError(ctypes.get_last_error())
    hwnd = user.CreateWindowExW(0, class_name, "Vanguard FAT Studio", 0x00CA0000,
                                -2147483648, -2147483648, 660, 330, None, None, instance, None)
    if not hwnd:
        raise ctypes.WinError(ctypes.get_last_error())
    font = gdi.GetStockObject(17)

    def control(kind, label, x, y, width, height, identifier=0):
        handle = user.CreateWindowExW(0, kind, label, 0x50000000 | (0x10000 if kind == "BUTTON" else 0),
                                      x, y, width, height, hwnd, identifier, instance, None)
        user.SendMessageW(handle, 0x0030, font, 1)
        return handle

    control("STATIC", "Vanguard FAT Studio", 24, 22, 600, 25)
    controls["status"] = control("STATIC", "Démarrage du service local…", 24, 62, 600, 105)
    controls[1] = control("BUTTON", "Ouvrir FAT Studio", 24, 180, 180, 36, 1)
    controls[2] = control("BUTTON", "Mise à jour", 218, 180, 185, 36, 2)
    controls[3] = control("BUTTON", "Quitter", 418, 180, 195, 36, 3)
    controls[4] = control("BUTTON", "Ouvrir le dossier de données", 24, 232, 300, 30, 4)
    user.EnableWindow(controls[1], False)
    user.SetTimer(hwnd, 1, 150, None)
    user.ShowWindow(hwnd, 5)
    user.UpdateWindow(hwnd)
    service.start()
    message = w.MSG()
    while (result := user.GetMessageW(ctypes.byref(message), None, 0, 0)) > 0:
        if not user.IsDialogMessageW(hwnd, ctypes.byref(message)):
            user.TranslateMessage(ctypes.byref(message))
            user.DispatchMessageW(ctypes.byref(message))
    if result == -1:
        service.stop()
        raise ctypes.WinError(ctypes.get_last_error())
    return 2 if service.error else 0
