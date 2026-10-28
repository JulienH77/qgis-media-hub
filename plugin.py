# -*- coding: utf-8 -*-
"""Chargement de l'extension et visibilité de sa barre d'outils."""

from pathlib import Path

from qgis.PyQt.QtCore import Qt, QSettings
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox


class MediaHubPlugin:
    MENU = "&Media Hub"
    KEY = "qgis_media_hub/"

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.toolbar = None
        self.dock = None

    def initGui(self):  # noqa: N802
        self.action = QAction(QIcon(str(Path(__file__).with_name("icon.svg"))),
                              "Media Hub — Vidéo, Web, Radio (JulienH77)", self.iface.mainWindow())
        self.action.setObjectName("qgisMediaHubAction")
        self.action.setCheckable(True)
        self.action.setToolTip("Media Hub — par JulienH77 · QGIS 3.44")
        self.action.toggled.connect(self._toggle)
        self.iface.addPluginToMenu(self.MENU, self.action)

        # Barre dédiée, nom stable : évite que le bouton soit enfoui au prochain lancement.
        self.toolbar = self.iface.addToolBar("Media Hub")
        self.toolbar.setObjectName("qgisMediaHubToolbar")
        self.toolbar.addAction(self.action)
        self.toolbar.show()

        if str(QSettings().value(self.KEY + "open_on_start", "false")).lower() in ("true", "1"):
            self.action.setChecked(True)

    def _toggle(self, show):
        if not show:
            if self.dock:
                self.dock.hide()
            return
        if self.dock is None:
            try:
                from .dock import MediaHubDock
                self.dock = MediaHubDock(self.iface.mainWindow())
                self.dock.visibilityChanged.connect(self._visibility_changed)
                self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
            except Exception as exc:
                self.action.blockSignals(True)
                self.action.setChecked(False)
                self.action.blockSignals(False)
                QMessageBox.warning(self.iface.mainWindow(), "Media Hub — Erreur",
                                    "Impossible d'ouvrir le panneau :\n\n{}".format(exc))
                self.dock = None
                return
        self.dock.show()
        self.dock.raise_()

    def _visibility_changed(self, visible):
        if self.action:
            self.action.blockSignals(True)
            self.action.setChecked(bool(visible))
            self.action.blockSignals(False)

    def unload(self):
        if self.dock is not None:
            self.dock.shutdown()
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
        if self.action:
            self.iface.removePluginMenu(self.MENU, self.action)
            self.action.toggled.disconnect(self._toggle)
            self.action.deleteLater()
            self.action = None
        if self.toolbar:
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar.deleteLater()
            self.toolbar = None
