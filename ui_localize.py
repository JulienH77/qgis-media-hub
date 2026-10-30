# -*- coding: utf-8 -*-
"""Translate static Qt labels/controls without changing persisted user content."""
from qgis.PyQt.QtWidgets import (
    QLabel, QPushButton, QToolButton, QCheckBox, QTabWidget, QLineEdit, QWidget
)
from .i18n import tr_ui


def apply_localization(root):
    """Apply French/English to known static widgets in a panel or dialog.

    Original French captions are stored on each Qt widget. This permits
    switching the language back without losing the original strings.
    User-entered data (notes, URLs, radio names) is never translated.
    """
    for widget in [root] + root.findChildren((QLabel, QPushButton, QToolButton, QCheckBox, QTabWidget, QLineEdit, QWidget)):
        if isinstance(widget, (QLabel, QPushButton, QToolButton, QCheckBox)):
            src = widget.property('mediahub_original_label')
            if src is None:
                src = widget.text()
                widget.setProperty('mediahub_original_label', src)
            if isinstance(src, str):
                widget.setText(tr_ui(src))
        if isinstance(widget, QLineEdit):
            ph = widget.property('mediahub_original_placeholder')
            if ph is None:
                ph = widget.placeholderText()
                widget.setProperty('mediahub_original_placeholder', ph)
            if isinstance(ph, str):
                widget.setPlaceholderText(tr_ui(ph))
        tip = widget.property('mediahub_original_tooltip')
        if tip is None:
            tip = widget.toolTip()
            widget.setProperty('mediahub_original_tooltip', tip)
        if isinstance(tip, str):
            widget.setToolTip(tr_ui(tip))
        if isinstance(widget, QTabWidget):
            for index in range(widget.count()):
                key = 'mediahub_tab_' + str(index)
                text = widget.property(key)
                if text is None:
                    text = widget.tabText(index)
                    widget.setProperty(key, text)
                widget.setTabText(index, tr_ui(text))
