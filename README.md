# Media Hub 1.4.0 — QGIS plugin

A clean, light multimedia dock panel for **QGIS 3.44.x (Qt5), Windows 64-bit**. Developed and maintained by **[JulienH77](https://github.com/JulienH77)**. Distributed under the [MIT license](LICENSE).

## Features

- **Video:** local videos and direct media links (MP4/MKV/AVI etc., codec-dependent), video folder browser, remembered folder, dropdown selection, refresh, ±10 s, pause, variable speed (0.1–5× in 0.1 increments), audio/subtitle tracks using VLC and external subtitles (SRT/ASS/VTT).
- **Floating PiP/fullscreen:** always-on-top mini-player, centered transport controls, dedicated volume up to 200% with VLC, speed control, and return to QGIS.
- **Customizable shortcuts:** Settings → Keyboard shortcuts to reassign Space/arrow keys/Q/S/D, reset defaults or disable keys entirely; stored locally. Default video shortcuts work only in the Video tab and PiP, not globally in the QGIS map canvas.
- **Radio:** 15 built-in French national stations: **RTL, France Inter, FIP, RMC, Franceinfo, Europe 1, NRJ, Nostalgie, Chérie FM, RTL2, France Culture, France Musique, RFM, Skyrock, Fun Radio**. Compact square station tiles, user-defined stations, multiple stream candidates, diagnostics, optional QGIS proxy relay and external VLC launch.
- **Web:** optional embedded Qt WebEngine/Chromium browser, including a YouTube shortcut; if unavailable, use the default Windows browser.
- **Notes:** persistent local scratchpad for QGIS expressions, SQL and task notes.
- **Settings:** customizable key bindings, open on QGIS startup, radio proxy use, and current volume.

## Install

1. **QGIS 3.44.x**, primarily Windows 64-bit. The package has not been verified for QGIS 4 / Qt6.
2. Install VLC Media Player **64-bit** on the machine for the full media and radio feature set. The extension dynamically loads the VLC installation: no VLC binary is bundled.
3. Optional embedded Web tab: install the matching **Qt5 PyQtWebEngine** package in OSGeo4W (`python3-pyqtwebengine`) and restart QGIS. Do **not** install an unrelated global PyQt build into QGIS.
4. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**. Select the release ZIP, which contains a top-level `media_hub/` folder. Restart QGIS after replacing an earlier version.
5. Open the dock using **Plugins → Media Hub** or its toolbar button. Click **⚙** to configure shortcuts and preferences.

## Default video/PiP keyboard shortcuts

| Key | Action |
| --- | --- |
| Space | Play/pause |
| ← / → | Back/forward 10 seconds |
| ↑ / ↓ | Volume up/down 5% |
| S | Reset speed to 1.0× |
| Q / D | Decrease/increase speed by 0.1× |
| Escape | Exit PiP fullscreen |

Shortcuts may depend on native VLC focus under Windows; they are not global operating-system shortcuts.

## Privacy and limitations

No telemetry. Notes, settings, last folder and favorites are stored on your computer using QSettings. Radio and video links are accessed only when you request them. The QGIS radio relay binds to loopback. Streaming services may block playback or require a proxy or DRM. The embedded browser does not guarantee YouTube compatibility. All radio URLs are subject to broadcaster changes; their availability is not guaranteed, especially on restricted workplace networks.

Station tile illustrations are original text-based illustrations for this plugin, **not official radio logos**. Radio trademarks belong to their owners. This project is not affiliated with QGIS, VideoLAN, Google or any radio broadcaster.

## Release information

This **1.4.0** release consolidates all enhancements built since the last officially published QGIS plugin **1.3.2**. See the detailed [CHANGELOG](CHANGELOG.md).

Source code: https://github.com/JulienH77/qgis-media-hub  
Bugs and feature requests: https://github.com/JulienH77/qgis-media-hub/issues

When reporting a stream problem, provide your QGIS and VLC versions, the station, and whether the same URL plays in standalone VLC. Do not disclose internal network addresses or credentials.
