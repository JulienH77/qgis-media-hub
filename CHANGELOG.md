## 1.5.1 — Compatibility and installation fixes

- Fixed the Flake8 E741 ambiguous identifier in the VLC binding layer.
- Updated the settings dialog to use Qt's scoped DialogCode and `exec()` API.
- Kept compatibility for optional Qt multimedia and WebEngine installations, avoiding direct static imports from `PyQt5`.
- Documented why GitHub source archives are not directly installable QGIS plugin ZIPs.
- No intentional changes to the video, radio, Web, or notes features.

# Changelog

## 1.5.0 — 2026-10-30 (revised build)

### Final UI refinements (same 1.5.0 release)
- Restore the PiP/fullscreen playback-speed control to the same editable numeric field as the main QGIS video panel (0.1x–5.0x, steps of 0.1x), with two-way synchronization and identical light/dark styling.
- PiP and fullscreen: added a synchronized seek bar with elapsed and total time, and drag-to-seek.
- Compact VLC-inspired volume control with mute button; shared numeric playback-speed field with 0.1x steps.
- Smaller radio tiles with readable station names below each square, including international stations without a logo.
- Redesigned Web tab: address/navigation row, quick links, bookmarks and a more readable WebEngine fallback.
- Preserved 1.5.0 version number, QGIS 3.44 compatibility, and existing radio/video settings.


### Video player and floating controls
- Add optional **Dark mode** (previously called "Cinema"), scoped to Media Hub and its floating player.
- Add the persistent **Hide/Show controls** button, available in PiP and fullscreen, plus configurable **H** shortcut.
- **Reduce PiP/fullscreen controls from three rows to two** with tighter margins, 26 px primary buttons and a compact speaker/volume/speed strip alongside the theme and hide buttons. Keep playback buttons centered, QGIS return left and fullscreen right.
- Preserve per-session theme and controls visibility preferences.

### Radio country grouping
- Use **one France entry**, like the other countries, with five featured stations including **RTL and Franceinfo**.
- For other countries, fetch five popular stations from the Radio Browser directory, caching successful responses locally.
- Assign a **country to each new custom radio station**. Custom stations appear only under their assigned country, not in every country.
- Allow changing a custom station's country; the old "My radios" view now contains only legacy stations without an identified country.
- Migrate older station lists to a validated, country-aware format without deleting existing station URLs; recognized French names are attributed to France.

### French and English interface
- Add **French and English UI translations** of major panels, controls, tooltips and settings.
- Choose **Automatic (QGIS/system locale)**, French or English under Settings → Preferences.
- Do not translate user-defined station names, saved notes, media paths or URLs.

### Known limitations
- Playback and remote radio discovery depend on VLC installation, codecs, stream availability and network/proxy restrictions.
- Embedded Web requires Qt5 PyQtWebEngine; external browser fallback remains supported.
- Actual visual behaviour of native VLC windows and international streaming needs testing in QGIS on Windows.
- QGIS 3.44/Qt5 target, not verified with QGIS 4/Qt6.

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
