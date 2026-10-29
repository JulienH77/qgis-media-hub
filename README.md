# Media Hub for QGIS 3.44

**Media Hub** is an experimental, lightweight multimedia and web dock for **QGIS 3.44 (Qt 5)** on Windows. Its interface uses standard Qt widgets so it blends with QGIS panels.

**Author:** [JulienH77](https://github.com/JulienH77)  
**License:** MIT (see [LICENSE](LICENSE))  
**Version:** 1.3.2 — experimental

## Features

- **Local video:** play video files and direct HTTP(S) media URLs using system VLC when available. Playback/pause, seek ±10 seconds, position slider, speed in increments of 0.1× (0.1×–5×), PiP floating window, fullscreen, and VLC volume control to 200%.
- **Web:** built-in Qt WebEngine/Chromium browser, address/search field, back/forward/refresh, bookmarks, and shortcuts including YouTube. Web browsing is optional and video services may not be fully compatible.
- **Radio:** presets for RTL, France Inter, FIP, RMC, custom direct-stream URLs, audio diagnostic, retry/fallback and optional proxy-aware network relay using QGIS. Stream availability depends on the broadcaster and the network.
- **Notes:** auto-saved local scratchpad for QGIS expressions, SQL snippets or task notes.
- **QGIS integration:** right/left dock, detachable panel, toolbar and Extensions menu, configurable open-on-start, saved preferences.

## Compatibility and dependencies

- **Designed for QGIS 3.44.x (Qt 5), primarily Windows 64-bit.** Not claimed compatible with QGIS 4 / Qt 6, Linux or macOS. No binary libraries are included.
- **VLC Media Player 64-bit:** install separately from [VideoLAN](https://www.videolan.org/vlc/). The plugin dynamically finds `libvlc.dll` on Windows; Python `vlc` bindings are not needed. The Qt Multimedia fallback is limited and may fail to play some formats.
- **Qt WebEngine / PyQtWebEngine (Qt 5):** optional. If missing, the Web tab shows a diagnostic. On QGIS OSGeo4W installations, it may be supplied as the `python3-pyqtwebengine` package. Do not install unrelated PyQt builds into QGIS's Python environment.
- **Internet radio:** HTTPS access to stream hosts is needed. On restricted networks, a redirect, proxy or policy may prevent playback even when browsing works. The QGIS relay cannot bypass network restrictions.

## Installation

1. In QGIS open **Plugins → Manage and Install Plugins → Install from ZIP**.
2. Select the release ZIP (it must contain a top-level `media_hub/` directory) and install it.
3. Enable Media Hub and open its dock from **Plugins → Media Hub** or the **Media Hub** toolbar.
4. If upgrading from an earlier locally installed build, fully restart QGIS to ensure native VLC resources are unloaded.

## Quick tests in QGIS 3.44

1. Open a short local MP4 in **Video**, verify play/pause, ±10 s, speed 1.1×, PiP and fullscreen (Esc to exit).
2. Open the **Web** tab, test the YouTube shortcut and a simple website. Record the diagnostic if WebEngine is unavailable.
3. Use **Radio → Test sound** (offline), then try **RTL** with **QGIS network/proxy** enabled and disabled. Try **In VLC** only to compare with the external VLC application. Some streams are inaccessible from enterprise networks.
4. Enter text in **Notes**, restart QGIS and confirm it is restored.
5. Restart QGIS and check the toolbar action and **Open on startup** setting.

## Known limitations / status

This release is **experimental**. A previous version could not load radio streams on one restricted network; version 1.3 introduced HTTP redirect handling but has **not been confirmed working on that network yet**. Qt WebEngine may be slower or unsupported for some web/video sites, and some streaming services require DRM unavailable in this embedded browser. Streaming a URL from a webpage is not the same as opening a direct media stream. No guarantee is made for radio availability or VLC volume beyond 100% without clipping.

This release updates attribution, packaging and documentation only; it does **not** fix any outstanding media playback bugs in version 1.3. It is intended for testing and for a first **experimental** listing once the publication requirements and real QGIS runtime tests are satisfied.

## Privacy

No telemetry or analytics. Web pages and radio stations are contacted only when you choose to use them. Notes, favorites and preferences are stored locally with QSettings. The radio relay binds to `127.0.0.1` only; it does not host a publicly accessible server.

## Support and sources

Bug reports: [GitHub Issues](https://github.com/JulienH77/qgis-media-hub/issues) (available once the repository has been created). Source: [GitHub repository](https://github.com/JulienH77/qgis-media-hub) (same condition).

Please include: QGIS version, Windows version, VLC 64-bit version, Media Hub version, a screenshot/error message and whether external VLC can play the same stream. Avoid sharing private access tokens, internal URLs or passwords in issue reports.

## Acknowledgements

Designed and maintained by **JulienH77**. The plugin integrates with QGIS and dynamically uses system VLC and optional Qt WebEngine, all provided separately under their respective licenses. This is an independent extension and is not affiliated with or endorsed by QGIS, VLC, YouTube or radio broadcasters.


## What's new in 1.4.0
- Click radio station picture tiles to tune into a station. Personal stations render their names inside their tiles.
- VLC audio and subtitle streams are selectable from dropdown menus; external SRT/ASS/VTT subtitles can be loaded with the SRT button (once video track information becomes available). Qt Multimedia fallback does not expose these controls.
- PiP includes volume and smaller skip buttons. Keyboard shortcuts when video/PiP has focus: **Space** play/pause; **Left/Right** -/+ 10 seconds; **Up/Down** volume -/+ 5%; **S** speed 1.0; **Q/D** speed -/+ 0.1.
- **WebEngine is an optional OSGeo4W package.** On Windows, install `python3-pyqtwebengine` using **OSGeo4W Setup > Advanced Install**, then restart QGIS. Without it, website navigation opens the system browser (YouTube stays functional outside the dock). An embedded fast Chromium browser cannot work without its underlying bindings.
- Station tiles are illustrative wordmark artwork made specifically for this plugin, not the stations' official brand assets.

Radio streams may be blocked by workplace proxies; this release does not assert that RTL playback is working on every network. Test on your local network before publishing as stable.
