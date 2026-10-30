# Media Hub 1.5.0 — QGIS plugin

A clean multimedia dock panel with optional dark mode and French/English interface for **QGIS 3.44.x (Qt5), Windows 64-bit**. Developed and maintained by **[JulienH77](https://github.com/JulienH77)**. Distributed under the [MIT license](LICENSE).

## Features

- **Video:** local videos and direct media links (MP4/MKV/AVI etc., codec-dependent), video folder browser, remembered folder, dropdown selection, refresh, ±10 s, pause, variable speed (0.1–5× in 0.1 increments), audio/subtitle tracks using VLC and external subtitles (SRT/ASS/VTT).
- **Floating PiP/fullscreen:** always-on-top mini-player, centered transport controls, compact, two-row toolbar with a speaker/volume control up to 200% with VLC and speed control and return to QGIS. A persistent small button collapses/restores transport and sound controls in both floating and fullscreen views.
- **Customizable shortcuts:** Settings → Keyboard shortcuts to reassign Space/arrow keys/Q/S/D, reset defaults or disable keys entirely; stored locally. Default video shortcuts work only in the Video tab and PiP, not globally in the QGIS map canvas.
- **Radio:** one France entry with five featured stations (**RTL, Franceinfo, France Inter, FIP and RMC**); country chooser (up to five top-clicked stations from Radio Browser for other countries); cached results and custom stations assigned to individual countries. Legacy stations are migrated, with an uncategorized category when no country is known. Compact square tiles, alternate stream candidates, optional QGIS proxy relay and external VLC remain available. The remaining French stream definitions are retained in the code but no longer displayed as a second France category.
- **Web:** optional embedded Qt WebEngine/Chromium browser, including a YouTube shortcut; if unavailable, use the default Windows browser.
- **Notes:** persistent local scratchpad for QGIS expressions, SQL and task notes.
- **Dark mode:** toggle between light native-QGIS appearance and dark movie-viewing appearance using the moon/sun button in the main panel or floating player. Preferences persist. The fullscreen/PiP Hide button and default **H** shortcut collapse controls but preserve a compact restore strip.
- **Settings:** customizable key bindings, open on QGIS startup, radio proxy use, current volume, dark mode preferences, and **language selection (Auto / Français / English)**.

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
| H | Hide/show PiP and fullscreen control bars |
| Escape | Exit PiP fullscreen |

Shortcuts may depend on native VLC focus under Windows; they are not global operating-system shortcuts.

## Privacy and limitations

No telemetry. Notes, settings, custom radio country associations, last folder and favorites are stored on your computer using QSettings. Radio and video links are accessed only when you request them. Selecting a country other than France retrieves a small station catalog from the third-party [Radio Browser directory](https://www.radio-browser.info/), using the current QGIS network configuration. Country results are cached locally for offline reuse. Radio Browser click counts are not a national audience ranking. The QGIS radio relay binds to loopback. Streaming services may block playback or require a proxy or DRM. The embedded browser does not guarantee YouTube compatibility. All radio URLs are subject to broadcaster changes; their availability is not guaranteed, especially on restricted workplace networks.

Station tile illustrations are original text-based illustrations for this plugin, **not official radio logos**. Radio trademarks belong to their owners. This project is not affiliated with QGIS, VideoLAN, Google or any radio broadcaster.

## Release information

Version **1.5.0** adds dark mode, more compact PiP/fullscreen controls, country-specific custom radio stations and bilingual French/English UI while retaining the full feature set from 1.4.0. See the detailed [CHANGELOG](CHANGELOG.md).

Source code: https://github.com/JulienH77/qgis-media-hub  
Bugs and feature requests: https://github.com/JulienH77/qgis-media-hub/issues

When reporting a stream problem, provide your QGIS and VLC versions, the station, and whether the same URL plays in standalone VLC. Do not disclose internal network addresses or credentials.

### Updated controls (Media Hub 1.5.0)
The floating PiP/fullscreen video includes a second, synchronized seek bar with elapsed and total times. Drag the handle to seek. The compact volume control can amplify VLC audio up to 200 percent and supports muting, while the speed field matches the main QGIS player (direct entry, 0.1x to 5.0x, 0.1x steps). These controls can still be hidden with the Show/Hide button or the configurable H shortcut.

Radio stations appear as compact square logos or initials with their full names underneath. The redesigned Web tab keeps the YouTube quick link, bookmarks and external-browser fallback if Qt WebEngine is missing.
