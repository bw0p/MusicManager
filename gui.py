import os
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import filedialog, messagebox, ttk

from audio_utils import ensure_id3_header, first_contributing_artist, load_audio
from models import TrackItem
from rename_rules import (
    apply_remove_rules,
    clean_spaces,
    extract_index_with_pair,
    remove_between_delims,
    safe_filename,
)
from tag_service import (
    TAG_FIELDS,
    TAG_KEY_BY_LABEL,
    apply_pending_tags,
    extract_tag_value_from_filename,
    read_supported_tags,
)
from warning_service import get_duplicate_track_ids, get_warnings


AUDIO_EXTS = {".mp3", ".m4a", ".flac", ".ogg", ".opus", ".wav", ".aiff", ".aac"}


class MusicFixGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Music File Manager")
        self.geometry("1250x780")
        self.minsize(900, 600)

        self.folder: str | None = None
        self.items: list[TrackItem] = []

        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_top_bar()
        self._build_file_table()
        self._build_workstations()

        self.status_label = ttk.Label(
            self,
            text="Choose a folder to begin. Changes remain pending until Apply Changes is pressed.",
        )
        self.status_label.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 8))

    def _build_top_bar(self):
        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Button(top, text="Choose Folder", command=self.choose_folder).grid(row=0, column=0)
        self.folder_label = ttk.Label(top, text="No folder selected")
        self.folder_label.grid(row=0, column=1, sticky="w", padx=10)
        ttk.Button(top, text="Clear All Pending Changes", command=self.clear_all_changes).grid(
            row=0, column=2, padx=6
        )
        ttk.Button(top, text="Apply Changes", command=self.apply_changes).grid(row=0, column=3)

    def _build_file_table(self):
        table_frame = ttk.Frame(self, padding=(10, 0))
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = (
            "current",
            "proposed",
            "artist",
            "albumartist",
            "album",
            "date",
            "genre",
            "track",
            "warnings",
        )
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        headings = {
            "current": "Current Filename",
            "proposed": "Proposed Filename",
            "artist": "Contributing Artist",
            "albumartist": "Album Artist",
            "album": "Album",
            "date": "Year",
            "genre": "Genre",
            "track": "Track #",
            "warnings": "Warnings",
        }
        widths = {
            "current": 280,
            "proposed": 280,
            "artist": 170,
            "albumartist": 170,
            "album": 170,
            "date": 80,
            "genre": 130,
            "track": 80,
            "warnings": 300,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                minwidth=60,
                stretch=False,
                anchor="center" if column in {"date", "track"} else "w",
            )

        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")

    def _build_workstations(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=2, column=0, sticky="ew", padx=10, pady=8)

        self.filename_tab = ttk.Frame(self.notebook, padding=10)
        self.tags_tab = ttk.Frame(self.notebook, padding=10)
        self.track_tab = ttk.Frame(self.notebook, padding=10)
        self.album_art_tab = ttk.Frame(self.notebook, padding=10)
        self.settings_tab = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.filename_tab, text="Filename Cleanup")
        self.notebook.add(self.tags_tab, text="Tags")
        self.notebook.add(self.track_tab, text="Track Order")
        self.notebook.add(self.album_art_tab, text="Album Art")
        self.notebook.add(self.settings_tab, text="Settings")

        self._equalize_tab_widths()

        self._build_filename_tab()
        self._build_tags_tab()
        self._build_track_tab()
        self._build_placeholder_tabs()

    def _equalize_tab_widths(self):
        labels = ["Filename Cleanup", "Tags", "Track Order", "Album Art", "Settings"]
        tab_font = tkfont.nametofont("TkDefaultFont")
        widest = max(tab_font.measure(label) for label in labels)
        for tab_id, label in zip(self.notebook.tabs(), labels):
            extra = widest - tab_font.measure(label)
            left = 12 + extra // 2
            right = 12 + extra - extra // 2
            self.notebook.tab(tab_id, padding=(left, 4, right, 4))

    def _build_filename_tab(self):
        self.filename_tab.columnconfigure(1, weight=1)

        ttk.Button(self.filename_tab, text="?", width=3, command=self.show_remove_rules_help).grid(
            row=0, column=0, sticky="nw", padx=(0, 6)
        )
        ttk.Label(self.filename_tab, text="Remove text from filename (one rule per line):").grid(
            row=0, column=1, sticky="w"
        )

        self.remove_text = tk.Text(self.filename_tab, height=4)
        self.remove_text.grid(row=1, column=0, columnspan=4, sticky="ew", pady=5)
        self.remove_text.insert("1.0", "SpotiDownloader.com - \n")
        self.remove_text.bind("<KeyRelease>", lambda _event: self.recompute_proposed_names())

        self.smart_spaces_var = tk.BooleanVar(value=True)
        self.smart_spaces_var.trace_add("write", lambda *_args: self.recompute_proposed_names())
        ttk.Checkbutton(
            self.filename_tab,
            text="Smart spacing",
            variable=self.smart_spaces_var,
        ).grid(row=2, column=0, sticky="w")

        self.between_enabled = tk.BooleanVar(value=False)
        self.between_enabled.trace_add("write", lambda *_args: self.recompute_proposed_names())
        ttk.Checkbutton(
            self.filename_tab,
            text="Remove text between delimiters",
            variable=self.between_enabled,
        ).grid(row=2, column=1, sticky="w", padx=(12, 0))

        ttk.Label(self.filename_tab, text="Pair:").grid(row=2, column=2, padx=(12, 4))
        self.between_pair = ttk.Entry(self.filename_tab, width=6)
        self.between_pair.config(
            validate="key",
            validatecommand=(self.register(lambda value: len(value) <= 2), "%P"),
        )
        self.between_pair.insert(0, "[]")
        self.between_pair.bind("<KeyRelease>", lambda _event: self.recompute_proposed_names())
        self.between_pair.grid(row=2, column=3, sticky="w")

        ttk.Button(
            self.filename_tab,
            text="Preview Filename Changes",
            command=self.recompute_proposed_names,
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))

    def _build_tags_tab(self):
        ttk.Label(self.tags_tab, text="Field:").grid(row=0, column=0, sticky="w")
        self.tag_field_var = tk.StringVar(value=TAG_FIELDS[0].label)
        self.tag_field_combo = ttk.Combobox(
            self.tags_tab,
            textvariable=self.tag_field_var,
            values=[field.label for field in TAG_FIELDS],
            state="readonly",
            width=22,
        )
        self.tag_field_combo.grid(row=0, column=1, sticky="w", padx=(6, 18))

        ttk.Label(self.tags_tab, text="Value:").grid(row=0, column=2, sticky="w")
        self.tag_value_entry = ttk.Entry(self.tags_tab, width=42)
        self.tag_value_entry.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Button(self.tags_tab, text="Apply to Selected", command=self.apply_tag_to_selected).grid(
            row=1, column=0, pady=(10, 0), sticky="w"
        )
        ttk.Button(self.tags_tab, text="Apply to All", command=self.apply_tag_to_all).grid(
            row=1, column=1, pady=(10, 0), sticky="w", padx=6
        )
        ttk.Button(self.tags_tab, text="Erase from Selected", command=self.erase_tag_from_selected).grid(
            row=1, column=2, pady=(10, 0), sticky="w"
        )
        ttk.Button(self.tags_tab, text="Erase from All", command=self.erase_tag_from_all).grid(
            row=1, column=3, pady=(10, 0), sticky="w", padx=6
        )
        ttk.Button(self.tags_tab, text="Reset Selected Edit", command=self.reset_tag_for_selected).grid(
            row=2, column=0, pady=(8, 0), sticky="w"
        )
        ttk.Button(self.tags_tab, text="Reset All Edits for Field", command=self.reset_tag_for_all).grid(
            row=2, column=1, columnspan=2, pady=(8, 0), sticky="w", padx=6
        )

        separator = ttk.Separator(self.tags_tab)
        separator.grid(row=3, column=0, columnspan=4, sticky="ew", pady=12)
        ttk.Label(self.tags_tab, text="Extract selected field from filename").grid(
            row=4, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(self.tags_tab, text="Text before:").grid(row=5, column=0, sticky="e", pady=(6, 0))
        self.tag_extract_before_entry = ttk.Entry(self.tags_tab, width=16)
        self.tag_extract_before_entry.grid(row=5, column=1, sticky="w", padx=6, pady=(6, 0))
        ttk.Label(self.tags_tab, text="Text after:").grid(row=5, column=2, sticky="e", pady=(6, 0))
        self.tag_extract_after_entry = ttk.Entry(self.tags_tab, width=16)
        self.tag_extract_after_entry.grid(row=5, column=3, sticky="w", padx=6, pady=(6, 0))
        ttk.Button(
            self.tags_tab,
            text="Extract for Selected",
            command=self.extract_tag_from_selected_filenames,
        ).grid(row=6, column=0, sticky="w", pady=(8, 0))
        ttk.Button(
            self.tags_tab,
            text="Extract for All",
            command=self.extract_tag_from_all_filenames,
        ).grid(row=6, column=1, sticky="w", padx=6, pady=(8, 0))
        ttk.Label(
            self.tags_tab,
            text="Example: before '[' and after ']' extracts Artist from Song [Artist] 2026.",
        ).grid(row=7, column=0, columnspan=4, sticky="w", pady=(8, 0))

    def _build_track_tab(self):
        ttk.Button(self.track_tab, text="Move Up", command=lambda: self.move_selected(-1)).grid(row=0, column=0)
        ttk.Button(self.track_tab, text="Move Down", command=lambda: self.move_selected(1)).grid(
            row=0, column=1, padx=6
        )
        ttk.Button(
            self.track_tab,
            text="Use Table Order as Track #",
            command=self.apply_order_as_track_numbers,
        ).grid(row=0, column=2, padx=(12, 6))
        ttk.Button(
            self.track_tab,
            text="Renumber Duplicates by Table Order",
            command=self.renumber_duplicates_by_table_order,
        ).grid(row=0, column=3)

        ttk.Label(self.track_tab, text="Extract markers:").grid(row=1, column=0, sticky="e", pady=(12, 0))
        self.track_pair = ttk.Entry(self.track_tab, width=6)
        self.track_pair.config(
            validate="key",
            validatecommand=(self.register(lambda value: len(value) <= 2), "%P"),
        )
        self.track_pair.insert(0, "[]")
        self.track_pair.grid(row=1, column=1, sticky="w", pady=(12, 0))
        ttk.Button(
            self.track_tab,
            text="Extract Track # from Filename",
            command=self.extract_track_from_titles,
        ).grid(row=1, column=2, pady=(12, 0), sticky="w")

        ttk.Label(self.track_tab, text="Track #:").grid(row=2, column=0, sticky="e", pady=(12, 0))
        self.track_value_entry = ttk.Entry(self.track_tab, width=8)
        self.track_value_entry.grid(row=2, column=1, sticky="w", pady=(12, 0))
        ttk.Button(self.track_tab, text="Set Selected", command=self.set_track_selected).grid(
            row=2, column=2, sticky="w", pady=(12, 0)
        )
        ttk.Button(self.track_tab, text="Erase Selected", command=self.erase_track_selected).grid(
            row=2, column=3, sticky="w", padx=6, pady=(12, 0)
        )
        ttk.Button(self.track_tab, text="Reset Selected Edit", command=self.clear_track_selected).grid(
            row=2, column=4, sticky="w", pady=(12, 0)
        )
        ttk.Button(self.track_tab, text="Reset All Track Edits", command=self.clear_track_all).grid(
            row=2, column=5, sticky="w", padx=6, pady=(12, 0)
        )

    def _build_placeholder_tabs(self):
        ttk.Label(
            self.album_art_tab,
            text="Album artwork tools will be added here after the tag and apply services are stable.",
        ).pack(anchor="w")
        ttk.Label(
            self.settings_tab,
            text="Saved rules, theme, confirmation, and backup options will be added here.",
        ).pack(anchor="w")

    def choose_folder(self):
        path = filedialog.askdirectory()
        if not path:
            return
        self.folder = path
        self.folder_label.config(text=path)
        self.scan_folder()

    def scan_folder(self):
        if not self.folder:
            messagebox.showwarning("No folder", "Choose a folder first.")
            return

        self.items.clear()
        rules, smart, use_between, pair = self._filename_options()

        for filename in sorted(os.listdir(self.folder)):
            src = os.path.join(self.folder, filename)
            ext = os.path.splitext(filename)[1].lower()
            if not os.path.isfile(src) or ext not in AUDIO_EXTS:
                continue

            audio, error = load_audio(src)
            tags = read_supported_tags(audio) if audio is not None else {}
            artist_first = first_contributing_artist(audio) or "" if audio is not None else ""
            proposed_filename, validation_warnings = self._propose_filename(
                filename, ext, rules, smart, use_between, pair
            )

            self.items.append(
                TrackItem(
                    path=Path(src),
                    filename=filename,
                    ext=ext,
                    proposed_filename=proposed_filename,
                    audio_ok=audio is not None,
                    read_error=error,
                    artist_first=artist_first,
                    tags=tags,
                    validation_warnings=validation_warnings,
                )
            )

        self._refresh_tree()
        self.status_label.config(text=f"Loaded {len(self.items)} audio file(s).")

    def _refresh_tree(self):
        selected = set(self.tree.selection())
        for row in self.tree.get_children():
            self.tree.delete(row)

        duplicate_track_ids = get_duplicate_track_ids(self.items)
        for index, item in enumerate(self.items):
            iid = str(index)
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    item.filename,
                    item.proposed_filename,
                    item.effective_tag("artist"),
                    item.effective_tag("albumartist"),
                    item.effective_tag("album"),
                    item.effective_tag("date"),
                    item.effective_tag("genre"),
                    item.effective_tag("tracknumber"),
                    "; ".join(get_warnings(item, duplicate_track_ids)),
                ),
            )
            if iid in selected:
                self.tree.selection_add(iid)

    def _selected_items(self, show_message=True) -> list[TrackItem]:
        selected = [self.items[int(iid)] for iid in self.tree.selection()]
        if not selected and show_message:
            messagebox.showinfo("No selection", "Select one or more tracks first.")
        return selected

    def _selected_tag_key(self) -> str:
        return TAG_KEY_BY_LABEL[self.tag_field_var.get()]

    def apply_tag_to_selected(self):
        self._apply_tag(self._selected_items(), self.tag_value_entry.get())

    def apply_tag_to_all(self):
        self._apply_tag(self.items, self.tag_value_entry.get())

    def _apply_tag(self, items: list[TrackItem], value: str):
        if not items:
            return
        value = value.strip()
        if not value:
            messagebox.showwarning("Empty value", "Enter a value, or use Erase to remove the tag.")
            return
        key = self._selected_tag_key()
        for item in items:
            item.set_pending_tag(key, value)
        self._refresh_tree()

    def erase_tag_from_selected(self):
        self._erase_tag(self._selected_items())

    def erase_tag_from_all(self):
        self._erase_tag(self.items)

    def _erase_tag(self, items: list[TrackItem]):
        if not items:
            return
        key = self._selected_tag_key()
        for item in items:
            item.erase_tag(key)
        self._refresh_tree()

    def reset_tag_for_selected(self):
        self._reset_tag(self._selected_items())

    def reset_tag_for_all(self):
        self._reset_tag(self.items)

    def _reset_tag(self, items: list[TrackItem]):
        if not items:
            return
        key = self._selected_tag_key()
        for item in items:
            item.reset_pending_tag(key)
        self._refresh_tree()

    def extract_tag_from_selected_filenames(self):
        self._extract_tag_from_filenames(self._selected_items())

    def extract_tag_from_all_filenames(self):
        self._extract_tag_from_filenames(self.items)

    def _extract_tag_from_filenames(self, items: list[TrackItem]):
        if not items:
            return
        text_before = self.tag_extract_before_entry.get()
        text_after = self.tag_extract_after_entry.get()
        if not text_before and not text_after:
            messagebox.showwarning(
                "Extraction boundaries required",
                "Enter text that appears before or after the value you want to extract.",
            )
            return

        key = self._selected_tag_key()
        changed = 0
        for item in items:
            value = extract_tag_value_from_filename(
                item.proposed_filename,
                text_before,
                text_after,
            )
            if value is not None:
                item.set_pending_tag(key, value)
                changed += 1

        self._refresh_tree()
        messagebox.showinfo(
            "Extract Tag",
            f"Extracted {self.tag_field_var.get()} for {changed} file(s).",
        )

    def move_selected(self, direction: int):
        selected = self.tree.selection()
        if not selected:
            return

        indices = sorted(int(iid) for iid in selected)
        if direction < 0:
            for index in indices:
                if index > 0:
                    self.items[index - 1], self.items[index] = self.items[index], self.items[index - 1]
        else:
            for index in reversed(indices):
                if index < len(self.items) - 1:
                    self.items[index + 1], self.items[index] = self.items[index], self.items[index + 1]

        self._refresh_tree()
        self.tree.selection_set(
            [str(max(0, min(len(self.items) - 1, index + direction))) for index in indices]
        )

    def apply_order_as_track_numbers(self):
        for index, item in enumerate(self.items, start=1):
            item.set_pending_tag("tracknumber", f"{index:02d}")
        self._refresh_tree()

    def renumber_duplicates_by_table_order(self):
        if not get_duplicate_track_ids(self.items):
            messagebox.showinfo("No duplicates", "No duplicate track numbers were found.")
            return
        if not messagebox.askyesno(
            "Renumber tracks",
            "To guarantee unique track numbers, all tracks will be numbered using the current table order. Continue?",
        ):
            return
        self.apply_order_as_track_numbers()

    def extract_track_from_titles(self):
        pair = self.track_pair.get().strip()
        if len(pair) != 2:
            messagebox.showwarning(
                "Invalid extract markers",
                "Extract markers must be exactly 2 characters, such as [], %%, or ''.",
            )
            return

        changed = 0
        for item in self.items:
            if item.effective_tag("tracknumber"):
                continue
            title = os.path.splitext(item.proposed_filename)[0]
            track_number = extract_index_with_pair(title, pair)
            if track_number is not None:
                item.set_pending_tag("tracknumber", f"{track_number:02d}")
                changed += 1

        self._refresh_tree()
        messagebox.showinfo("Extract Track #", f"Set track numbers for {changed} file(s).")

    def set_track_selected(self):
        value = self.track_value_entry.get().strip()
        if not value:
            messagebox.showwarning("Empty value", "Enter a track number first.")
            return
        for item in self._selected_items():
            item.set_pending_tag("tracknumber", value)
        self._refresh_tree()

    def erase_track_selected(self):
        for item in self._selected_items():
            item.erase_tag("tracknumber")
        self._refresh_tree()

    def clear_track_selected(self):
        for item in self._selected_items():
            item.reset_pending_tag("tracknumber")
        self._refresh_tree()

    def clear_track_all(self):
        for item in self.items:
            item.reset_pending_tag("tracknumber")
        self._refresh_tree()

    def clear_all_changes(self):
        for item in self.items:
            item.clear_pending_tags()
        self.recompute_proposed_names()

    def _filename_options(self):
        rules = self.remove_text.get("1.0", "end").splitlines()
        return (
            rules,
            bool(self.smart_spaces_var.get()),
            bool(self.between_enabled.get()),
            self.between_pair.get(),
        )

    def _propose_filename(self, filename, ext, rules, smart, use_between, pair):
        proposed_base = apply_remove_rules(os.path.splitext(filename)[0], rules, smart_spaces=smart)
        warnings = []
        if use_between:
            if len(pair) == 2:
                proposed_base = remove_between_delims(proposed_base, pair[0], pair[1])
            else:
                warnings.append("Delimiter pair must be exactly 2 characters (e.g. [] or &&).")
        proposed_base = safe_filename(clean_spaces(proposed_base))
        return proposed_base + ext, warnings

    def recompute_proposed_names(self):
        rules, smart, use_between, pair = self._filename_options()
        for item in self.items:
            item.proposed_filename, item.validation_warnings = self._propose_filename(
                item.filename, item.ext, rules, smart, use_between, pair
            )
        self._refresh_tree()

    def apply_changes(self):
        if not self.folder or not self.items:
            return

        duplicate_track_ids = get_duplicate_track_ids(self.items)
        if duplicate_track_ids:
            duplicate_list = ", ".join(
                sorted(
                    duplicate_track_ids,
                    key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value),
                )
            )
            messagebox.showwarning(
                "Duplicate track numbers",
                "Two or more tracks share the same track number.\n\n"
                f"Duplicate track numbers: {duplicate_list}\n\n"
                "Correct them in the Track Order tab before applying changes.",
            )
            return

        if not messagebox.askyesno("Apply", "This will rename files and write tags. Continue?"):
            return

        existing = set(os.listdir(self.folder))
        rename_operations = []
        for item in self.items:
            old = item.filename
            new = item.proposed_filename
            if old == new:
                continue

            base, ext = os.path.splitext(new)
            candidate = new
            suffix = 1
            while candidate in existing and candidate != old:
                candidate = f"{base} ({suffix}){ext}"
                suffix += 1
            existing.discard(old)
            existing.add(candidate)
            rename_operations.append((item, candidate))

        for item, candidate in rename_operations:
            destination = Path(self.folder) / candidate
            try:
                item.path.rename(destination)
            except Exception as error:
                messagebox.showerror(
                    "Rename failed",
                    f"Could not rename:\n{item.filename}\n\nto:\n{candidate}\n\n"
                    "A file with that name may already exist or be open in another program.\n\n"
                    f"Technical detail: {error}",
                )
                return
            item.filename = candidate
            item.proposed_filename = candidate
            item.path = destination

        tag_errors = 0
        tag_skipped = 0
        for item in self.items:
            if item.path.suffix.lower() == ".mp3":
                ensure_id3_header(str(item.path))

            audio, error = load_audio(str(item.path))
            if audio is None:
                tag_skipped += 1
                if error:
                    print(f"[apply load_audio] {item.filename}: {error}")
                continue

            try:
                apply_pending_tags(audio, item)
                audio.save()
            except Exception as error:
                tag_errors += 1
                print(f"[tag save failed] {item.filename}: {type(error).__name__}: {error}")

        self.scan_folder()
        message = "Changes applied."
        if tag_skipped:
            message += f"\n\n{tag_skipped} file(s) could not be opened for tag editing."
        if tag_errors:
            message += f"\n\n{tag_errors} file(s) failed while saving tags."
        messagebox.showinfo("Apply Changes", message)

    def show_remove_rules_help(self):
        messagebox.showinfo(
            "Filename Cleanup Help",
            "Enter one piece of text to remove per line. Rules are applied in order.\n\n"
            "Smart spacing tolerates extra spaces around hyphens.\n\n"
            "Enable delimiter removal and enter a two-character pair such as [], (), or && "
            "to remove the delimiters and the text between them.",
        )
