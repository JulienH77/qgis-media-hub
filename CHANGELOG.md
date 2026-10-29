# Changelog

## 1.4.0 — 2026-10-29

Consolidated public update since the last published QGIS repository version **1.3.2**. The intermediate 1.4.1–1.4.3 packages were local development builds, not previously published official versions.

### Radio
- Add **Franceinfo** with the user-supplied high-quality AAC URL `http://direct.franceinfo.fr/live/franceinfo-hifi.aac` and alternative hosts/formats.
- Add **Europe 1, NRJ, Nostalgie, Chérie FM, RTL2, France Culture, France Musique, RFM, Skyrock and Fun Radio**, for 15 built-in French stations.
- Render each station as a **compact 94×94 px square tile**, with a responsive grid and one-click playback.
- Display the names of custom stations inside their own square tiles.
- Retain alternative stream retry, proxy-aware QGIS radio relay, diagnostics and opening streams in external VLC.

### Video player
- Add a **local video folder picker** and **dropdown library**; remember the folder and start playback on selection.
- Automatically load the containing folder after opening a video file and provide a **refresh** action (non-recursive scan).
- Add VLC **audio track and subtitle track selection**, plus external SRT/ASS/SSA/VTT subtitle loading.
- Enlarge the main Play/Pause button, improve Windows button contrast and fix invisible ±10 s controls in the floating player.
- Reorganize the Picture-in-Picture controls: Return to QGIS at left, −10 / Play / +10 geometrically centered, Fullscreen at right; volume and speed on a separate row.
- Keep PiP volume (up to 200% with VLC), 0.1× speed increments and fullscreen.

### Customizable keyboard shortcuts
- Add an actual **Settings dialog** with editable video/PiP shortcuts, restore-defaults button, conflict detection and enable/disable option.
- Default shortcuts: **Space** play/pause; **Left/Right** skip ±10 s; **Up/Down** volume ±5%; **S** 1.0× speed; **Q/D** speed −/+0.1×.
- Persist key bindings locally in QSettings. Video shortcuts do not intentionally override the QGIS map canvas shortcuts.
- Add configurable startup visibility, network/proxy radio preference and volume control to Settings.

### Web and general
- When Qt WebEngine is missing, open addresses and YouTube shortcuts in the system browser instead of blocking all navigation.
- Preserve the native-looking light QGIS dock layout, persistent notes, toolbar access, author attribution and MIT licensing.
- Improve publication metadata and documentation in English and French.

### Known limitations
- Radio stream URLs may change or be blocked by workplace networks; not all new streams have been tested end-to-end from a QGIS Windows installation.
- Embedded Web browsing still requires optional PyQtWebEngine (Qt5); no claim is made for QGIS 4 / Qt6.
- The library lists only videos directly inside the selected folder; native VLC rendering can affect keyboard focus on some Windows setups.

## 1.3.2 — 2026-10-28
- Replace subprocess calls with Qt QProcess for launching external VLC.
- Use scoped Qt enumerations and remove unused imports.
- Keep publishing metadata and the MIT license credited to JulienH77.

## 1.3.1 — 2026-10-28
- Prepare English plugin metadata, icon and author credits for QGIS repository publication.

## 1.3.0 — 2026-10
- Handle HTTP redirects in the radio relay.

## 1.2.0 — 2026-10
- Add proxy-aware QGIS relay for radio.

## 1.1.0 — 2026-10
- Add audio diagnostics and alternative radio streams.

## 1.0.0 — 2026-10
- Initial video, web, radio and notes dock.
