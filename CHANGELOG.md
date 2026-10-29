# Changelog

## 1.4.0 — 2026-10-29
- Radio stations displayed as a selectable two-column tile grid. Clicking plays; custom stations display their names inside the tile.
- Audio and subtitle track selection for local VLC video; import of external subtitle files (SRT/ASS/VTT). Track discovery updates during playback.
- PiP controls: compact ±10 s buttons, volume 0–200%, keyboard controls: Space, left/right, up/down, S, Q, D.
- Embedded WebEngine remains optional; missing component causes YouTube and other site buttons to open in the normal browser instead of a dead tab.
- White, QGIS-native dock design; English metadata; MIT licensed by JulienH77.

# Changelog

## 1.3.2 — 2026-10-28
- Replace `subprocess.Popen` with Qt `QProcess.startDetached()` to start an installed VLC instance without a shell, keeping the executable path and media URL separate.
- Use scoped Qt enum names supported in QGIS 3.44 (Qt 5.15), reducing Qt 6 migration warnings without claiming QGIS 4 compatibility.
- Remove unused imports and update English publication metadata.
- No change to media decoding, radio feeds, or proxy transport. Radio playback is still experimental.

## 1.3.1 — 2026-10-28
- Prepare official QGIS repository packaging and English metadata.
- Credit JulienH77 in the plugin interface, metadata, README and MIT LICENSE.
- Add a PNG icon and publication documentation.
- **No change to the radio, web, or video playback engines.**

## 1.3.0 — 2026-10
- Follow HTTP redirects for QGIS relay radio streams; improve radio error reporting.

## 1.2.0 — 2026-10
- Add optional proxy-aware QGIS network relay for radio playback.

## 1.1.0 — 2026-10
- Add additional radio sources, audio test and stream diagnostics.

## 1.0.0 — 2026-10
- Initial video, web, radio and notes dock.
