# -*- coding: utf-8 -*-
"""QGIS Media Hub — Extension pour QGIS 3.44 (Qt 5)."""


def classFactory(iface):  # noqa: N802 — convention des plugins QGIS
    from .plugin import MediaHubPlugin
    return MediaHubPlugin(iface)
