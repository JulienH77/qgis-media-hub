# -*- coding: utf-8 -*-
"""Moteur libVLC 3/4 par ctypes, sans dépendance pip/python-vlc.

Ce module charge les DLL de l'installation VLC du PC (Windows),
mais ne les embarque PAS dans l'extension. API PyQt proche du QMediaPlayer.
"""
import ctypes
import os
import shutil
import sys

from qgis.PyQt.QtCore import QObject, QTimer, pyqtSignal
try:
    from qgis.PyQt.QtMultimedia import QMediaPlayer
except ImportError:
    class QMediaPlayer:
        """Constantes pour le moteur VLC si Qt Multimedia est absent."""
        StoppedState = 0
        PlayingState = 1
        PausedState = 2
        UnknownMediaStatus = 0
        LoadingMedia = 2
        BufferingMedia = 4
        BufferedMedia = 6
        EndOfMedia = 7
        InvalidMedia = 8
        ResourceError = 1


class VLCBackendError(RuntimeError):
    pass


def find_vlc():
    """Cherche l'installation VLC Windows 64 bits (ou autre même architecture)."""
    if sys.platform != "win32":
        return None
    directories = []
    configured = os.environ.get("QGIS_MEDIA_HUB_VLC_DIR", "").strip().strip('"')
    if configured:
        directories.append(configured)
    for var in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(var)
        if base:
            directories.append(os.path.join(base, "VideoLAN", "VLC"))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        directories.append(os.path.join(local, "Programs", "VideoLAN", "VLC"))
    exe = shutil.which("vlc.exe")
    if exe:
        directories.append(os.path.dirname(exe))
    try:
        import winreg
        # Sur certaines installations, l'emplacement est enregistré ici.
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for keypath in (r"SOFTWARE\VideoLAN\VLC", r"SOFTWARE\WOW6432Node\VideoLAN\VLC"):
                try:
                    with winreg.OpenKey(root, keypath) as key:
                        val, _ = winreg.QueryValueEx(key, "InstallDir")
                        if val:
                            directories.append(val)
                except OSError:
                    pass
    except ImportError:
        pass
    for folder in dict.fromkeys(directories):
        candidate = os.path.join(folder, "libvlc.dll")
        if os.path.isfile(candidate) and os.path.isdir(os.path.join(folder, "plugins")):
            return candidate
    return None


class VLCBackend(QObject):
    """Pont Qt vers libVLC : polling de l'état sur le thread GUI."""

    positionChanged = pyqtSignal(int)
    durationChanged = pyqtSignal(int)
    stateChanged = pyqtSignal(int)
    mediaStatusChanged = pyqtSignal(int)
    seekableChanged = pyqtSignal(bool)
    error = pyqtSignal(int)
    tracksChanged = pyqtSignal(object, object, int, int)

    # Réutilise les mêmes enums que QMediaPlayer (le panneau est agnostique).
    PlayingState = QMediaPlayer.PlayingState
    PausedState = QMediaPlayer.PausedState
    StoppedState = QMediaPlayer.StoppedState

    def __init__(self, video_widget, dll_path, parent=None):
        super().__init__(parent)
        if sys.platform != "win32":
            raise VLCBackendError("Le moteur VLC embarqué est prévu pour Windows.")
        if not dll_path or not os.path.isfile(dll_path):
            raise VLCBackendError("Impossible de trouver libvlc.dll.")

        self._dll_directory_handle = None
        self._dll = None
        self._instance = None
        self._player = None
        self._last_state = QMediaPlayer.StoppedState
        self._last_vlc_state = None
        self._last_seekable = False
        self._length = 0
        self._position = 0
        self._media_loaded = False
        self._muted = False
        self._volume = 75
        self._speed = 1.0
        self._error_message = ""
        self._released = False
        self._video_widget = video_widget
        self._track_cache = None
        self._track_poll_count = 0

        dll_folder = os.path.dirname(dll_path)
        plugins = os.path.join(dll_folder, "plugins")
        # Le chargement des dépendances de VLC est indépendant de celles de QGIS.
        if hasattr(os, "add_dll_directory"):
            self._dll_directory_handle = os.add_dll_directory(dll_folder)
        os.environ["VLC_PLUGIN_PATH"] = plugins
        try:
            self._dll = ctypes.CDLL(dll_path)
            self._setup_functions()
            args = (ctypes.c_char_p * 2)(b"--no-video-title-show", b"--quiet")
            self._instance = self._dll.libvlc_new(2, args)
            if not self._instance:
                raise VLCBackendError("VLC n'a pas réussi à initialiser son moteur (plugins/DLL).")
            self._player = self._dll.libvlc_media_player_new(self._instance)
            if not self._player:
                raise VLCBackendError("Impossible de créer le lecteur VLC.")

            hwnd = int(self._video_widget.winId())
            if not hwnd:
                raise VLCBackendError("Fenêtre vidéo Windows introuvable.")
            self._ensure_clip_children(hwnd)
            self._dll.libvlc_media_player_set_hwnd(self._player, ctypes.c_void_p(hwnd))
            self._dll.libvlc_video_set_mouse_input(self._player, 0)
            self._dll.libvlc_video_set_key_input(self._player, 0)
            self.setVolume(75)
        except Exception:
            self.close()
            raise
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _setup_functions(self):
        P = ctypes.c_void_p
        I = ctypes.c_int
        L = ctypes.c_int64
        F = ctypes.c_float
        S = ctypes.c_char_p
        def bind(name, restype, *argtypes):
            fun = getattr(self._dll, name)
            fun.argtypes = argtypes
            fun.restype = restype
        bind("libvlc_new", P, I, ctypes.POINTER(S))
        bind("libvlc_release", None, P)
        bind("libvlc_media_player_new", P, P)
        bind("libvlc_media_player_release", None, P)
        bind("libvlc_media_new_path", P, P, S)
        bind("libvlc_media_new_location", P, P, S)
        bind("libvlc_media_release", None, P)
        bind("libvlc_media_player_set_media", None, P, P)
        bind("libvlc_media_player_set_hwnd", None, P, P)
        bind("libvlc_media_player_play", I, P)
        bind("libvlc_media_player_stop", None, P)
        bind("libvlc_media_player_set_pause", None, P, I)
        bind("libvlc_media_player_get_state", I, P)
        bind("libvlc_media_player_get_time", L, P)
        bind("libvlc_media_player_get_length", L, P)
        bind("libvlc_media_player_set_time", None, P, L)
        bind("libvlc_media_player_is_seekable", I, P)
        bind("libvlc_media_player_set_rate", I, P, F)
        bind("libvlc_audio_set_volume", I, P, I)
        bind("libvlc_audio_set_mute", None, P, I)
        bind("libvlc_video_set_mouse_input", None, P, I)
        bind("libvlc_video_set_key_input", None, P, I)
        # LibVLC 3: identifiants de pistes (ne pas confondre avec les index).
        for name, result, arguments in (
            ("libvlc_audio_get_track_description", P, (P,)),
            ("libvlc_audio_get_track", I, (P,)),
            ("libvlc_audio_set_track", I, (P, I)),
            ("libvlc_video_get_spu_description", P, (P,)),
            ("libvlc_video_get_spu", I, (P,)),
            ("libvlc_video_set_spu", I, (P, I)),
            ("libvlc_track_description_list_release", None, (P,)),
            ("libvlc_media_player_add_slave", I, (P, I, S, I)),
        ):
            try:
                bind(name, result, *arguments)
            except AttributeError:
                # Autre version de libVLC: la lecture reste disponible.
                pass

    @staticmethod
    def _ensure_clip_children(hwnd):
        """Requis par le rendu VLC dans un HWND enfant Windows."""
        user32 = ctypes.windll.user32
        GWL_STYLE = -16
        WS_CLIPCHILDREN = 0x02000000
        # Style (DWORD 32 bits) même sur un processus Win64.
        user32.GetWindowLongW.argtypes = (ctypes.c_void_p, ctypes.c_int)
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_long)
        user32.SetWindowLongW.restype = ctypes.c_long
        current = user32.GetWindowLongW(ctypes.c_void_p(hwnd), GWL_STYLE)
        user32.SetWindowLongW(ctypes.c_void_p(hwnd), GWL_STYLE, current | WS_CLIPCHILDREN)

    def rebind_surface(self):
        """Rebranche le rendu VLC après changement de fenêtre Qt (PiP/fullscreen)."""
        if not self._player or not self._video_widget:
            return
        hwnd = int(self._video_widget.winId())
        if not hwnd:
            raise VLCBackendError("Impossible de récupérer la surface vidéo Windows.")
        self._ensure_clip_children(hwnd)
        self._dll.libvlc_media_player_set_hwnd(self._player, ctypes.c_void_p(hwnd))

    def isAvailable(self):
        return bool(self._player)

    def load_media(self, kind, source):
        """kind='web' -> URL; kind='local' -> chemin absolu Unicode."""
        self.stop()
        self._media_loaded = False
        self._error_message = ""
        self._length = 0
        self._position = 0
        self._last_vlc_state = None
        self._last_seekable = False
        self._last_state = QMediaPlayer.StoppedState
        self._track_cache = None
        self.tracksChanged.emit([], [], -1, -1)
        self.durationChanged.emit(0)
        self.positionChanged.emit(0)
        self.mediaStatusChanged.emit(QMediaPlayer.LoadingMedia)
        source_bytes = source.encode("utf-8")
        if kind == "web":
            media = self._dll.libvlc_media_new_location(self._instance, source_bytes)
        else:
            media = self._dll.libvlc_media_new_path(self._instance, source_bytes)
        if not media:
            self._set_error("VLC ne peut pas ouvrir cette source.")
            return False
        try:
            self._dll.libvlc_media_player_set_media(self._player, media)
        finally:
            self._dll.libvlc_media_release(media)
        self._media_loaded = True
        return True

    def play(self):
        if not self._media_loaded:
            return
        code = self._dll.libvlc_media_player_play(self._player)
        if code == -1:
            self._set_error("VLC n'a pas pu démarrer la lecture.")
            return
        self.setPlaybackRate(self._speed)

    def pause(self):
        if self._media_loaded:
            self._dll.libvlc_media_player_set_pause(self._player, 1)

    def stop(self):
        if self._player:
            self._dll.libvlc_media_player_stop(self._player)

    def state(self):
        if not self._player:
            return QMediaPlayer.StoppedState
        state = self._dll.libvlc_media_player_get_state(self._player)
        return {
            3: QMediaPlayer.PlayingState,
            4: QMediaPlayer.PausedState,
        }.get(state, QMediaPlayer.StoppedState)

    def position(self):
        return max(0, int(self._dll.libvlc_media_player_get_time(self._player)))

    def setPosition(self, milliseconds):
        if self.isSeekable():
            self._dll.libvlc_media_player_set_time(self._player, max(0, int(milliseconds)))

    def isSeekable(self):
        return bool(self._player and self._dll.libvlc_media_player_is_seekable(self._player))

    def setPlaybackRate(self, speed):
        self._speed = float(speed)
        if not self._media_loaded or not self._player:
            return True
        # VLC peut accepter la demande tout en limitant les taux extrêmes.
        return self._dll.libvlc_media_player_set_rate(self._player, ctypes.c_float(self._speed)) == 0

    def setVolume(self, volume):
        self._volume = max(0, min(200, int(volume)))
        if self._player:
            return self._dll.libvlc_audio_set_volume(self._player, self._volume) == 0
        return True

    def setMuted(self, muted):
        self._muted = bool(muted)
        if self._player:
            self._dll.libvlc_audio_set_mute(self._player, int(self._muted))

    def isMuted(self):
        return self._muted

    def errorString(self):
        return self._error_message

    def _set_error(self, message):
        self._error_message = message
        self.mediaStatusChanged.emit(QMediaPlayer.InvalidMedia)
        self.error.emit(QMediaPlayer.ResourceError)

    def _poll(self):
        if not self._media_loaded or not self._player:
            return
        vlc_state = self._dll.libvlc_media_player_get_state(self._player)
        if vlc_state != self._last_vlc_state:
            self._last_vlc_state = vlc_state
            status = {
                1: QMediaPlayer.LoadingMedia,
                2: QMediaPlayer.BufferingMedia,
                3: QMediaPlayer.BufferedMedia,
                4: QMediaPlayer.BufferedMedia,
                6: QMediaPlayer.EndOfMedia,
                7: QMediaPlayer.InvalidMedia,
            }.get(vlc_state)
            if status is not None:
                if vlc_state == 7:
                    self._error_message = (
                        "VLC n'a pas pu décoder ou ouvrir ce média. "
                        "Vérifie le fichier ou l'URL."
                    )
                self.mediaStatusChanged.emit(status)
                if vlc_state == 7:
                    self.error.emit(QMediaPlayer.ResourceError)
            if vlc_state == 3:
                self.setPlaybackRate(self._speed)
                self.setVolume(self._volume)
        state = self.state()
        if state != self._last_state:
            self._last_state = state
            self.stateChanged.emit(state)
        length = max(0, int(self._dll.libvlc_media_player_get_length(self._player)))
        if length != self._length:
            self._length = length
            self.durationChanged.emit(length)
        current = self.position()
        if current != self._position:
            self._position = current
            self.positionChanged.emit(current)
        self._track_poll_count += 1
        if self._track_poll_count % 5 == 0 and vlc_state in (3, 4):
            self._refresh_tracks()
        seekable = self.isSeekable()
        if seekable != self._last_seekable:
            self._last_seekable = seekable
            self.seekableChanged.emit(seekable)

    def _describe_tracks(self, function_name):
        """Lit les listes chaînées libVLC et libère leur mémoire."""
        fn = getattr(self._dll, function_name, None)
        release = getattr(self._dll, "libvlc_track_description_list_release", None)
        if not self._player or fn is None or release is None:
            return []

        class TrackDescription(ctypes.Structure):
            pass

        TrackDescription._fields_ = [
            ("i_id", ctypes.c_int),
            ("psz_name", ctypes.c_char_p),
            ("p_next", ctypes.POINTER(TrackDescription)),
        ]
        head = fn(self._player)
        if not head:
            return []
        tracks = []
        try:
            node = ctypes.cast(head, ctypes.POINTER(TrackDescription))
            # Limite défensive face à une liste corrompue fournie par la DLL.
            for _ in range(128):
                if not node:
                    break
                item = node.contents
                name = (item.psz_name or b"").decode("utf-8", errors="replace")
                tracks.append((int(item.i_id), name or "Piste {}".format(item.i_id)))
                node = item.p_next
        finally:
            release(ctypes.c_void_p(head))
        return tracks

    def audio_tracks(self):
        return self._describe_tracks("libvlc_audio_get_track_description")

    def subtitle_tracks(self):
        return self._describe_tracks("libvlc_video_get_spu_description")

    def audio_track(self):
        fn = getattr(self._dll, "libvlc_audio_get_track", None)
        return int(fn(self._player)) if fn and self._player else -1

    def subtitle_track(self):
        fn = getattr(self._dll, "libvlc_video_get_spu", None)
        return int(fn(self._player)) if fn and self._player else -1

    def set_audio_track(self, track_id):
        fn = getattr(self._dll, "libvlc_audio_set_track", None)
        return fn(self._player, int(track_id)) == 0 if fn and self._player else False

    def set_subtitle_track(self, track_id):
        fn = getattr(self._dll, "libvlc_video_set_spu", None)
        return fn(self._player, int(track_id)) == 0 if fn and self._player else False

    def add_external_subtitle(self, path):
        """Charge un fichier SRT/ASS/VTT local sur le média VLC actif."""
        fn = getattr(self._dll, "libvlc_media_player_add_slave", None)
        if fn is None or not self._player or not os.path.isfile(path):
            return False
        from pathlib import Path
        uri = Path(path).resolve().as_uri().encode("utf-8")
        ok = fn(self._player, 0, uri, 1) == 0
        if ok:
            self._track_cache = None
            self._refresh_tracks()
        return ok

    def _refresh_tracks(self):
        if not self._player:
            return
        audio, subtitles = self.audio_tracks(), self.subtitle_tracks()
        selected_audio, selected_sub = self.audio_track(), self.subtitle_track()
        snapshot = (tuple(audio), tuple(subtitles), selected_audio, selected_sub)
        if snapshot != self._track_cache:
            self._track_cache = snapshot
            self.tracksChanged.emit(audio, subtitles, selected_audio, selected_sub)

    def close(self):
        if self._released:
            return
        self._released = True
        timer = getattr(self, "_timer", None)
        if timer is not None:
            timer.stop()
        if self._dll and self._player:
            self._dll.libvlc_media_player_stop(self._player)
            self._dll.libvlc_media_player_release(self._player)
            self._player = None
        if self._dll and self._instance:
            self._dll.libvlc_release(self._instance)
            self._instance = None
        if self._dll_directory_handle:
            self._dll_directory_handle.close()
            self._dll_directory_handle = None
