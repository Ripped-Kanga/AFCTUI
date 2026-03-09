"""Textual file browser modal for selecting audio files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Label, Tree

from afctui.converter import is_audio_file


class _AudioTree(DirectoryTree):
    """DirectoryTree that shows only directories and supported audio files.

    Hidden files and folders (names starting with '.') are always excluded.
    """

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            p for p in paths
            if not p.name.startswith(".")
            and (p.is_dir() or is_audio_file(p))
        ]


class FileBrowserScreen(ModalScreen[str | None]):
    """Modal file browser for selecting an audio file."""

    CSS = """
    FileBrowserScreen {
        align: center middle;
    }
    #fb-dialog {
        width: 80%;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1;
    }
    #fb-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        width: 100%;
    }
    #fb-tree {
        height: 1fr;
        border: solid $panel;
    }
    #fb-status {
        height: 1;
        margin-top: 1;
    }
    #fb-buttons {
        height: 3;
        margin-top: 1;
        layout: horizontal;
        align: center middle;
    }
    #fb-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._selected_path: str | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="fb-dialog"):
            yield Label("Select an Audio File", id="fb-title")
            yield _AudioTree(Path.home(), id="fb-tree")
            yield Label("Navigate with arrows, Enter to select", id="fb-status")
            with Horizontal(id="fb-buttons"):
                yield Button("Select", variant="primary", id="fb-select", disabled=True)
                yield Button("Cancel", id="fb-cancel")

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        if is_audio_file(event.path):
            self.dismiss(str(event.path))
        else:
            self.query_one("#fb-status", Label).update(
                f"[red]Unsupported format: {event.path.suffix or '(none)'}[/]"
            )

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        try:
            path: Path = event.node.data.path
        except AttributeError:
            return
        if path.is_file() and is_audio_file(path):
            self._selected_path = str(path)
            self.query_one("#fb-status", Label).update(str(path))
            self.query_one("#fb-select", Button).disabled = False
        else:
            self._selected_path = None
            self.query_one("#fb-status", Label).update(f"[dim]{path.name or str(path)}[/]")
            self.query_one("#fb-select", Button).disabled = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fb-select" and self._selected_path:
            self.dismiss(self._selected_path)
        elif event.button.id == "fb-cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
