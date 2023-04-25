# This file is part of this GitHub repository: https://github.com/abdnh/anki-media-exporter
# All Credit goes to abdnh

from __future__ import annotations

import time
from concurrent.futures import Future
from typing import Any

import aqt
from anki.decks import DeckId
from aqt import gui_hooks, mw
from aqt.editor import Editor

try:
    from aqt.browser.browser import Browser
except ImportError:
    from aqt.browser import Browser

from aqt.qt import *
from aqt.utils import tooltip

from .media_exporter import DeckMediaExporter, MediaExporter, NoteMediaExporter

AUDIO_EXTS = aqt.editor.audio

def get_export_folder(parent: QWidget) -> str:
    "Get the export folder from the user."
    return QFileDialog.getExistingDirectory(
        parent, caption="Choose the folder where you want to export the files to"
    )


def get_configured_exts(config: dict[str, Any]) -> set | None:
    return set(AUDIO_EXTS) if config.get("audio_only", False) else None


def get_configured_search_field(config: dict[str, Any]) -> str | None:
    return config.get("search_in_field", None)


def export_with_progress(
    parent: QWidget, exporter: MediaExporter, note_count: int
) -> None:
    folder = get_export_folder(parent)
    want_cancel = False

    def export_task() -> int:
        last_progress = 0.0
        media_i = 0
        for notes_i, (media_i, _) in enumerate(exporter.export(folder)):
            if time.time() - last_progress >= 0.1:
                last_progress = time.time()
                mw.taskman.run_on_main(
                    lambda notes_i=notes_i + 1, media_i=media_i: update_progress(
                        notes_i, note_count, media_i
                    )
                )
                if want_cancel:
                    break
        return media_i

    def update_progress(notes_i: int, note_count: int, media_i: int) -> None:
        nonlocal want_cancel
        mw.progress.update(
            label=f"Processed {notes_i} notes and exported {media_i} files",
            max=note_count,
            value=notes_i,
        )
        want_cancel = mw.progress.want_cancel()

    def on_done(future: Future) -> None:
        try:
            count = future.result()
        finally:
            mw.progress.finish()
        tooltip(f"Exported {count} media files", parent=parent)

    mw.progress.start(label="Exporting media...", parent=parent)
    mw.progress.set_title("AnkiCollab")
    mw.taskman.run_in_background(export_task, on_done=on_done)


def on_deck_browser_will_show_options_menu(menu: QMenu, did: int) -> None:
    """Adds a menu item under the gears icon to export a deck's media files."""

    def export_media() -> None:
        config = mw.addonManager.getConfig(__name__)
        field = get_configured_search_field(config)
        exts = get_configured_exts(config)
        exporter = DeckMediaExporter(mw.col, DeckId(did), field, exts)
        note_count = mw.col.decks.card_count([DeckId(did)], include_subdecks=True)
        export_with_progress(mw, exporter, note_count)

    action = menu.addAction("Export Media")
    qconnect(action.triggered, export_media)
    

def add_browser_menu_item(browser: Browser) -> None:
    def export_selected() -> None:
        config = mw.addonManager.getConfig(__name__)
        field = get_configured_search_field(config)
        exts = get_configured_exts(config)
        selected_notes = [mw.col.get_note(nid) for nid in browser.selected_notes()]
        exporter = NoteMediaExporter(mw.col, selected_notes, field, exts)
        note_count = len(selected_notes)
        export_with_progress(browser, exporter, note_count)

    action = QAction("Export Media", browser)
    qconnect(action.triggered, export_selected)
    browser.form.menu_Notes.addAction(action)