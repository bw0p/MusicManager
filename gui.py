import ctypes
import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import filedialog, ttk

import themed_dialogs as messagebox
from models import TrackItem
from rename_rules import extract_index_with_pair
from services.apply_service import ApplyError, apply_changes as apply_item_changes
from services.artwork_service import ArtworkError, extract_embedded_artwork, load_artwork_file
from services.scanner import ScanOptions, propose_filename, scan_folder as scan_audio_folder
from services.settings_service import AppSettings, RulePreset, load_settings, save_settings
from tag_service import (
    TAG_FIELDS,
    TAG_KEY_BY_LABEL,
    extract_tag_value_from_filename,
    title_from_filename,
)
from warning_service import get_duplicate_track_ids, get_warnings


def _set_windows_app_mode(dark: bool):
    if sys.platform != "win32":
        return
    try:
        kernel32 = ctypes.WinDLL("kernel32")
        uxtheme = ctypes.WinDLL("uxtheme")
        kernel32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel32.GetProcAddress.restype = ctypes.c_void_p
        address = kernel32.GetProcAddress(uxtheme._handle, ctypes.c_void_p(135))
        if address:
            set_preferred_app_mode = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int)(address)
            set_preferred_app_mode(2 if dark else 3)
        flush_address = kernel32.GetProcAddress(uxtheme._handle, ctypes.c_void_p(136))
        if flush_address:
            ctypes.WINFUNCTYPE(None)(flush_address)()
    except (AttributeError, OSError, ValueError):
        pass


class MusicFixGUI(tk.Tk):
    def __init__(self):
        settings = load_settings()
        _set_windows_app_mode(settings.theme == "Dark")
        super().__init__()
        self.withdraw()
        self.settings = settings
        self.title("Music File Manager")
        self.geometry("1250x780")
        self.minsize(900, 600)

        self.active_rules = self.settings.active_rules()
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        messagebox.configure(
            self,
            lambda: self.theme_var.get() == "Dark" if hasattr(self, "theme_var") else self.settings.theme == "Dark",
            self._apply_windows_window_theme,
        )

        self.folder: Path | None = None
        self.items: list[TrackItem] = []
        self.selected_artwork = None

        self._build_ui()
        self.apply_theme(self.settings.theme, force_titlebar_refresh=False)
        self.update_idletasks()
        self.deiconify()
        self.after_idle(lambda: self._apply_windows_window_theme(self, self.settings.theme == "Dark"))

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
            "title",
            "artist",
            "albumartist",
            "album",
            "date",
            "genre",
            "track",
            "artwork",
            "warnings",
        )
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        headings = {
            "current": "Current Filename",
            "proposed": "Proposed Filename",
            "title": "Title",
            "artist": "Contributing Artist",
            "albumartist": "Album Artist",
            "album": "Album",
            "date": "Year",
            "genre": "Genre",
            "track": "Track #",
            "artwork": "Artwork",
            "warnings": "Warnings",
        }
        widths = {
            "current": 280,
            "proposed": 280,
            "title": 220,
            "artist": 170,
            "albumartist": 170,
            "album": 170,
            "date": 80,
            "genre": 130,
            "track": 80,
            "artwork": 90,
            "warnings": 300,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                minwidth=60,
                stretch=False,
                anchor="center" if column in {"date", "track", "artwork"} else "w",
            )

        vertical = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            style="App.Vertical.TScrollbar",
            command=self.tree.yview,
        )
        horizontal = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            style="App.Horizontal.TScrollbar",
            command=self.tree.xview,
        )
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
        self._build_album_art_tab()
        self._build_settings_tab()

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
        saved_rules = "\n".join(self.active_rules.remove_rules)
        self.remove_text.insert("1.0", saved_rules + ("\n" if saved_rules else ""))
        self.remove_text.bind("<KeyRelease>", lambda _event: self.recompute_proposed_names())

        options = ttk.Frame(self.filename_tab)
        options.grid(row=2, column=0, columnspan=4, sticky="w")

        self.smart_spaces_var = tk.BooleanVar(value=self.active_rules.smart_spaces)
        self.smart_spaces_var.trace_add("write", lambda *_args: self.recompute_proposed_names())
        ttk.Checkbutton(
            options,
            text="Smart spacing",
            variable=self.smart_spaces_var,
        ).pack(side="left")

        self.between_enabled = tk.BooleanVar(value=self.active_rules.remove_between_enabled)
        self.between_enabled.trace_add("write", lambda *_args: self.recompute_proposed_names())
        ttk.Checkbutton(
            options,
            text="Remove text between delimiters",
            variable=self.between_enabled,
        ).pack(side="left", padx=(16, 0))

        ttk.Label(options, text="Pair:").pack(side="left", padx=(8, 4))
        self.between_pair = ttk.Entry(options, width=6)
        self.between_pair.config(
            validate="key",
            validatecommand=(self.register(lambda value: len(value) <= 2), "%P"),
        )
        self.between_pair.insert(0, self.active_rules.delimiter_pair)
        self.between_pair.bind("<KeyRelease>", lambda _event: self.recompute_proposed_names())
        self.between_pair.pack(side="left")

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
        ttk.Button(
            self.tags_tab,
            text="Extract Title from Filename",
            command=self.extract_titles_from_filenames,
        ).grid(row=3, column=0, columnspan=2, pady=(8, 0), sticky="w")

        separator = ttk.Separator(self.tags_tab)
        separator.grid(row=4, column=0, columnspan=4, sticky="ew", pady=12)
        ttk.Label(self.tags_tab, text="Extract selected field from filename").grid(
            row=5, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(self.tags_tab, text="Text before:").grid(row=6, column=0, sticky="e", pady=(6, 0))
        self.tag_extract_before_entry = ttk.Entry(self.tags_tab, width=16)
        self.tag_extract_before_entry.insert(0, self.active_rules.tag_extract_before)
        self.tag_extract_before_entry.grid(row=6, column=1, sticky="w", padx=6, pady=(6, 0))
        ttk.Label(self.tags_tab, text="Text after:").grid(row=6, column=2, sticky="e", pady=(6, 0))
        self.tag_extract_after_entry = ttk.Entry(self.tags_tab, width=16)
        self.tag_extract_after_entry.insert(0, self.active_rules.tag_extract_after)
        self.tag_extract_after_entry.grid(row=6, column=3, sticky="w", padx=6, pady=(6, 0))
        ttk.Button(
            self.tags_tab,
            text="Extract for Selected",
            command=self.extract_tag_from_selected_filenames,
        ).grid(row=7, column=0, sticky="w", pady=(8, 0))
        ttk.Button(
            self.tags_tab,
            text="Extract for All",
            command=self.extract_tag_from_all_filenames,
        ).grid(row=7, column=1, sticky="w", padx=6, pady=(8, 0))
        ttk.Label(
            self.tags_tab,
            text="Example: before '[' and after ']' extracts Artist from Song [Artist] 2026.",
        ).grid(row=8, column=0, columnspan=4, sticky="w", pady=(8, 0))

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
        self.track_pair.insert(0, self.active_rules.track_markers)
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
            row=3, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )
        ttk.Button(self.track_tab, text="Reset All Track Edits", command=self.clear_track_all).grid(
            row=3, column=2, columnspan=2, sticky="w", padx=6, pady=(12, 0)
        )

    def _build_album_art_tab(self):
        ttk.Label(
            self.album_art_tab,
            text="Choose a JPG or PNG. Artwork edits remain pending until Apply Changes.",
        ).grid(row=0, column=0, columnspan=4, sticky="w")
        self.artwork_file_label = ttk.Label(self.album_art_tab, text="No image selected")
        self.artwork_file_label.grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 10))

        ttk.Button(
            self.album_art_tab,
            text="Choose Image File",
            command=self._choose_artwork,
        ).grid(row=2, column=0, sticky="w")
        ttk.Button(
            self.album_art_tab,
            text="Use Artwork from Selected Track",
            command=self.use_artwork_from_selected_track,
        ).grid(row=2, column=1, columnspan=2, sticky="w", padx=6)

        ttk.Button(
            self.album_art_tab,
            text="Set Artwork for Selected",
            command=self.set_artwork_for_selected,
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Button(
            self.album_art_tab,
            text="Set Artwork for All",
            command=self.set_artwork_for_all,
        ).grid(row=3, column=1, sticky="w", padx=6, pady=(8, 0))
        ttk.Button(
            self.album_art_tab,
            text="Remove from Selected",
            command=self.remove_artwork_from_selected,
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Button(
            self.album_art_tab,
            text="Remove from All",
            command=self.remove_artwork_from_all,
        ).grid(row=4, column=1, sticky="w", padx=6, pady=(8, 0))
        ttk.Button(
            self.album_art_tab,
            text="Reset Selected Artwork Edit",
            command=self.reset_artwork_for_selected,
        ).grid(row=5, column=0, sticky="w", pady=(8, 0))
        ttk.Button(
            self.album_art_tab,
            text="Reset All Artwork Edits",
            command=self.reset_artwork_for_all,
        ).grid(row=5, column=1, sticky="w", padx=6, pady=(8, 0))

    def _build_settings_tab(self):
        ttk.Label(self.settings_tab, text="Theme:").grid(row=0, column=0, sticky="w")
        self.theme_var = tk.StringVar(value=self.settings.theme)
        theme_combo = ttk.Combobox(
            self.settings_tab,
            textvariable=self.theme_var,
            values=["Light", "Dark"],
            state="readonly",
            width=12,
        )
        theme_combo.grid(row=0, column=1, sticky="w", padx=6)
        theme_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_theme(self.theme_var.get()))
        ttk.Button(self.settings_tab, text="Save Theme", command=self.save_theme_setting).grid(
            row=0, column=2, sticky="w", padx=6
        )

        ttk.Label(self.settings_tab, text="Rule set:").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.preset_name_var = tk.StringVar(value=self.settings.active_preset)
        self.preset_combo = ttk.Combobox(
            self.settings_tab,
            textvariable=self.preset_name_var,
            values=sorted(self.settings.rule_presets),
            state="readonly",
            width=24,
        )
        self.preset_combo.grid(row=1, column=1, sticky="w", padx=6, pady=(10, 0))
        self.preset_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_rule_preset())
        ttk.Button(self.settings_tab, text="New Rule Set", command=self.create_rule_preset).grid(
            row=1, column=2, sticky="w", padx=6, pady=(10, 0)
        )

        ttk.Label(self.settings_tab, text="Save categories:").grid(row=2, column=0, sticky="nw", pady=(10, 0))
        categories = ttk.Frame(self.settings_tab)
        categories.grid(row=2, column=1, columnspan=3, sticky="w", pady=(10, 0))
        self.save_cleanup_var = tk.BooleanVar(value=True)
        self.save_track_var = tk.BooleanVar(value=True)
        self.save_tag_extract_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(categories, text="Filename Cleanup", variable=self.save_cleanup_var).pack(
            side="left"
        )
        ttk.Checkbutton(categories, text="Track Markers", variable=self.save_track_var).pack(
            side="left", padx=(12, 0)
        )
        ttk.Checkbutton(categories, text="Tag Extraction", variable=self.save_tag_extract_var).pack(
            side="left", padx=(12, 0)
        )

        ttk.Button(self.settings_tab, text="Save Rule Set", command=self.save_current_settings).grid(
            row=3, column=0, sticky="w", pady=(10, 0)
        )
        ttk.Button(self.settings_tab, text="Reset Defaults", command=self.reset_settings_defaults).grid(
            row=3, column=1, sticky="w", padx=6, pady=(10, 0)
        )
        ttk.Button(self.settings_tab, text="Delete Rule Set", command=self.delete_rule_preset).grid(
            row=4, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Label(
            self.settings_tab,
            text="Only checked categories overwrite their previously saved values.",
        ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(10, 0))
        ttk.Label(
            self.settings_tab,
            text="Theme is saved separately and never changes when loading a rule set.",
        ).grid(row=6, column=0, columnspan=4, sticky="w", pady=(4, 0))

    def apply_theme(self, theme_name: str, force_titlebar_refresh: bool = True):
        dark = theme_name == "Dark"
        self.style.theme_use("clam")

        background = "#202124" if dark else "#f0f0f0"
        panel = "#292a2d" if dark else "#f0f0f0"
        field = "#303134" if dark else "#ffffff"
        foreground = "#f1f3f4" if dark else "#000000"
        muted = "#bdc1c6" if dark else "#404040"
        accent = "#4c8bf5" if dark else "#0b65c2"
        selected_tab = "#3c4043" if dark else "#ffffff"
        border = "#8ab4f8" if dark else "#6f7782"

        self.configure(background=background)
        self.style.configure("TFrame", background=panel)
        self.style.configure("TLabel", background=panel, foreground=foreground)
        self.style.configure("DialogTitle.TLabel", background=panel, foreground=foreground, font=("TkDefaultFont", 10, "bold"))
        self.style.configure(
            "TButton",
            background=panel,
            foreground=foreground,
            bordercolor=border,
            lightcolor=border,
            darkcolor=border,
            borderwidth=1,
            padding=(6, 3),
        )
        self.style.map(
            "TButton",
            background=[("active", accent)],
            foreground=[("active", "#ffffff")],
        )
        self.style.configure("TCheckbutton", background=panel, foreground=foreground, padding=2)
        self.style.map("TCheckbutton", background=[("active", panel)])
        self.style.configure("TEntry", fieldbackground=field, foreground=foreground, padding=3)
        self.style.configure("TCombobox", fieldbackground=field, foreground=foreground, padding=2)
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", field)],
            foreground=[("readonly", foreground)],
            selectbackground=[("readonly", field)],
            selectforeground=[("readonly", foreground)],
        )
        self.style.configure(
            "Treeview",
            background=field,
            fieldbackground=field,
            foreground=foreground,
            rowheight=22,
            borderwidth=1,
        )
        self.style.configure(
            "Treeview.Heading",
            background=panel,
            foreground=foreground,
            padding=(4, 3),
            borderwidth=1,
        )
        self.style.map(
            "Treeview",
            background=[("selected", accent)],
            foreground=[("selected", "#ffffff")],
        )
        self.style.configure("TNotebook", background=background, borderwidth=1)
        self.style.configure(
            "TNotebook.Tab",
            background=panel,
            foreground=foreground,
            padding=(12, 4),
            borderwidth=1,
            expand=(0, 0, 0, 0),
            shiftrelief=0,
        )
        # Clam changes selected-tab padding and relief by default. Clearing those
        # inherited maps keeps the tab strip stationary when selection changes.
        self.style.map("TNotebook.Tab", padding=[], expand=[], relief=[])
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", selected_tab), ("active", accent)],
            foreground=[("selected", foreground), ("active", "#ffffff"), ("disabled", muted)],
        )
        self.style.configure("TSeparator", background=muted)
        scrollbar_thumb = "#6f7378" if dark else "#8a8f96"
        scrollbar_active = "#8ab4f8" if dark else "#4d5661"
        scrollbar_trough = "#17181a" if dark else "#d7d9dc"
        for scrollbar_style in ("App.Horizontal.TScrollbar", "App.Vertical.TScrollbar"):
            self.style.configure(
                scrollbar_style,
                background=scrollbar_thumb,
                troughcolor=scrollbar_trough,
                bordercolor=border,
                lightcolor=scrollbar_thumb,
                darkcolor=scrollbar_thumb,
                arrowcolor=foreground,
                borderwidth=1,
            )
            self.style.map(
                scrollbar_style,
                background=[("active", scrollbar_active), ("pressed", accent)],
                lightcolor=[("active", scrollbar_active), ("pressed", accent)],
                darkcolor=[("active", scrollbar_active), ("pressed", accent)],
            )
        self.remove_text.configure(
            background=field,
            foreground=foreground,
            insertbackground=foreground,
            selectbackground=accent,
            selectforeground="#ffffff",
        )
        self.update_idletasks()
        self._apply_windows_window_theme(self, dark)

        if force_titlebar_refresh and sys.platform == "win32":
            self.after(50, self._force_titlebar_refresh)

        
        
    def _apply_windows_window_theme(self, window: tk.Misc, dark: bool):
        if sys.platform != "win32":
            return

        _set_windows_app_mode(dark)

        try:
            window.update_idletasks()

            child_hwnd = window.winfo_id()

            user32 = ctypes.WinDLL("user32")
            user32.GetParent.argtypes = [ctypes.c_void_p]
            user32.GetParent.restype = ctypes.c_void_p

            hwnd = user32.GetParent(ctypes.c_void_p(child_hwnd)) or child_hwnd

            enabled = ctypes.c_int(1 if dark else 0)

            dwmapi = ctypes.WinDLL("dwmapi")
            dwmapi.DwmSetWindowAttribute.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_void_p,
                ctypes.c_uint,
            ]
            dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long

            for attribute in (20, 19):
                result = dwmapi.DwmSetWindowAttribute(
                    ctypes.c_void_p(hwnd),
                    attribute,
                    ctypes.byref(enabled),
                    ctypes.sizeof(enabled),
                )

                if result == 0:
                    SWP_NOSIZE = 0x0001
                    SWP_NOMOVE = 0x0002
                    SWP_NOZORDER = 0x0004
                    SWP_NOACTIVATE = 0x0010
                    SWP_FRAMECHANGED = 0x0020

                    user32.SetWindowPos.argtypes = [
                        ctypes.c_void_p,
                        ctypes.c_void_p,
                        ctypes.c_int,
                        ctypes.c_int,
                        ctypes.c_int,
                        ctypes.c_int,
                        ctypes.c_uint,
                    ]
                    user32.SetWindowPos.restype = ctypes.c_int

                    user32.SetWindowPos(
                        ctypes.c_void_p(hwnd),
                        None,
                        0,
                        0,
                        0,
                        0,
                        SWP_NOMOVE
                        | SWP_NOSIZE
                        | SWP_NOZORDER
                        | SWP_NOACTIVATE
                        | SWP_FRAMECHANGED,
                    )

                    RDW_INVALIDATE = 0x0001
                    RDW_UPDATENOW = 0x0100
                    RDW_FRAME = 0x0400
                    RDW_ALLCHILDREN = 0x0080

                    user32.RedrawWindow.argtypes = [
                        ctypes.c_void_p,
                        ctypes.c_void_p,
                        ctypes.c_void_p,
                        ctypes.c_uint,
                    ]
                    user32.RedrawWindow.restype = ctypes.c_int

                    user32.RedrawWindow(
                        ctypes.c_void_p(hwnd),
                        None,
                        None,
                        RDW_INVALIDATE | RDW_UPDATENOW | RDW_FRAME | RDW_ALLCHILDREN,
                    )

                    break

        except (AttributeError, OSError):
            pass

    def _force_titlebar_refresh(self):
        if sys.platform != "win32":
            return

        try:
            was_zoomed = self.state() == "zoomed"
            geometry = self.geometry()

            self.withdraw()
            self.update_idletasks()
            self.deiconify()

            if was_zoomed:
                self.state("zoomed")
            else:
                self.geometry(geometry)

            self.lift()
            self.focus_force()
        except tk.TclError:
            pass
    

    def save_current_settings(self):
        if not any(
            (
                self.save_cleanup_var.get(),
                self.save_track_var.get(),
                self.save_tag_extract_var.get(),
            )
        ):
            messagebox.showinfo("Rule set", "Choose at least one rule category to save.")
            return

        preset_name = self.preset_name_var.get()
        preset = self.settings.rule_presets[preset_name]
        current = self._current_rule_preset()
        if self.save_cleanup_var.get():
            preset.remove_rules = current.remove_rules
            preset.smart_spaces = current.smart_spaces
            preset.remove_between_enabled = current.remove_between_enabled
            preset.delimiter_pair = current.delimiter_pair
        if self.save_track_var.get():
            preset.track_markers = current.track_markers
        if self.save_tag_extract_var.get():
            preset.tag_extract_before = current.tag_extract_before
            preset.tag_extract_after = current.tag_extract_after
        self.settings.active_preset = preset_name
        self.active_rules = preset
        try:
            save_settings(self.settings)
        except OSError as error:
            messagebox.showerror("Settings error", f"Could not save the rule set.\n\n{error}")
            return
        messagebox.showinfo("Rule set", f'Rule set "{preset_name}" saved.')

    def save_theme_setting(self):
        self.settings.theme = self.theme_var.get()
        try:
            save_settings(self.settings)
        except OSError as error:
            messagebox.showerror("Settings error", f"Could not save the theme.\n\n{error}")
            return
        messagebox.showinfo("Theme", f'{self.settings.theme} theme saved.')

    def create_rule_preset(self):
        preset_name = messagebox.askstring(
            "New rule set",
            "Name the new rule set:",
            parent=self,
        )
        if preset_name is None:
            return
        preset_name = preset_name.strip()
        if not preset_name:
            messagebox.showinfo("Rule set", "Enter a name for the new rule set.")
            return
        if preset_name in self.settings.rule_presets:
            messagebox.showinfo("Rule set", f'A rule set named "{preset_name}" already exists.')
            return

        previous_name = self.settings.active_preset
        previous_rules = self.active_rules
        preset = self._current_rule_preset()
        self.settings.rule_presets[preset_name] = preset
        self.settings.active_preset = preset_name
        self.active_rules = preset
        self.preset_name_var.set(preset_name)
        self._refresh_preset_names()
        try:
            save_settings(self.settings)
        except OSError as error:
            del self.settings.rule_presets[preset_name]
            self.settings.active_preset = previous_name
            self.active_rules = previous_rules
            self.preset_name_var.set(previous_name)
            self._refresh_preset_names()
            messagebox.showerror("Settings error", f"Could not create the rule set.\n\n{error}")
            return
        messagebox.showinfo("Rule set", f'Rule set "{preset_name}" created from the current rules.')

    def load_rule_preset(self):
        preset_name = self.preset_name_var.get().strip()
        preset = self.settings.rule_presets.get(preset_name)
        if preset is None:
            messagebox.showinfo("Rule set", f'No saved rule set named "{preset_name}" was found.')
            return

        self._apply_rule_preset(preset)
        self.settings.active_preset = preset_name
        self.active_rules = preset
        try:
            save_settings(self.settings)
        except OSError as error:
            messagebox.showerror("Settings error", f"Could not save the active rule set.\n\n{error}")
            return
        self.recompute_proposed_names()

    def delete_rule_preset(self):
        preset_name = self.preset_name_var.get().strip()
        if preset_name == "Default":
            messagebox.showinfo("Rule set", "Default cannot be deleted.")
            return
        if preset_name not in self.settings.rule_presets:
            messagebox.showinfo("Rule set", "Choose a saved rule set to delete.")
            return
        if not messagebox.askyesno("Delete rule set", f'Delete the rule set "{preset_name}"?'):
            return

        del self.settings.rule_presets[preset_name]
        if self.settings.active_preset == preset_name:
            self.settings.active_preset = "Default"
            self.active_rules = self.settings.rule_presets["Default"]
            self._apply_rule_preset(self.active_rules)
        self.preset_name_var.set(self.settings.active_preset)
        self._refresh_preset_names()
        try:
            save_settings(self.settings)
        except OSError as error:
            messagebox.showerror("Settings error", f"Could not delete the rule set.\n\n{error}")
            return
        self.recompute_proposed_names()

    def _refresh_preset_names(self):
        self.preset_combo.configure(values=sorted(self.settings.rule_presets))

    def _current_rule_preset(self) -> RulePreset:
        return RulePreset(
            remove_rules=self.remove_text.get("1.0", "end").splitlines(),
            smart_spaces=bool(self.smart_spaces_var.get()),
            remove_between_enabled=bool(self.between_enabled.get()),
            delimiter_pair=self.between_pair.get(),
            track_markers=self.track_pair.get(),
            tag_extract_before=self.tag_extract_before_entry.get(),
            tag_extract_after=self.tag_extract_after_entry.get(),
        )

    def _apply_rule_preset(self, preset: RulePreset):
        self.remove_text.delete("1.0", "end")
        rules = "\n".join(preset.remove_rules)
        self.remove_text.insert("1.0", rules + ("\n" if rules else ""))
        self.smart_spaces_var.set(preset.smart_spaces)
        self.between_enabled.set(preset.remove_between_enabled)
        self.between_pair.delete(0, "end")
        self.between_pair.insert(0, preset.delimiter_pair)
        self.track_pair.delete(0, "end")
        self.track_pair.insert(0, preset.track_markers)
        self.tag_extract_before_entry.delete(0, "end")
        self.tag_extract_before_entry.insert(0, preset.tag_extract_before)
        self.tag_extract_after_entry.delete(0, "end")
        self.tag_extract_after_entry.insert(0, preset.tag_extract_after)

    def reset_settings_defaults(self):
        defaults = AppSettings()
        self.theme_var.set(defaults.theme)
        self.preset_name_var.set("Default")
        self._apply_rule_preset(defaults.active_rules())
        self.apply_theme(defaults.theme)
        self.recompute_proposed_names()

    def choose_folder(self):
        path = filedialog.askdirectory()
        if not path:
            return
        self.folder = Path(path)
        self.folder_label.config(text=str(self.folder))
        self.selected_artwork = None
        self.scan_folder()

    def scan_folder(self):
        if not self.folder:
            messagebox.showwarning("No folder", "Choose a folder first.")
            return

        self.items = scan_audio_folder(self.folder, self._scan_options())

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
                    item.effective_tag("title"),
                    item.effective_tag("artist"),
                    item.effective_tag("albumartist"),
                    item.effective_tag("album"),
                    item.effective_tag("date"),
                    item.effective_tag("genre"),
                    item.effective_tag("tracknumber"),
                    item.effective_artwork_status(),
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

    def extract_titles_from_filenames(self):
        for item in self.items:
            item.set_pending_tag("title", title_from_filename(item.proposed_filename))
        self._refresh_tree()
        messagebox.showinfo(
            "Extract Title",
            f"Set titles from the proposed filenames for {len(self.items)} file(s).",
        )

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
            title = Path(item.proposed_filename).stem
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
            item.reset_pending_artwork()
        self.recompute_proposed_names()

    def _choose_artwork(self):
        path = filedialog.askopenfilename(
            title="Choose Album Artwork",
            filetypes=[("Image files", "*.jpg *.jpeg *.png"), ("All files", "*.*")],
        )
        if not path:
            return None
        try:
            artwork = load_artwork_file(Path(path))
        except (ArtworkError, OSError) as error:
            messagebox.showerror("Artwork error", str(error))
            return None
        self.artwork_file_label.config(text=f"Selected image: {artwork.source_name}")
        self.selected_artwork = artwork
        return artwork

    def use_artwork_from_selected_track(self):
        items = self._selected_items()
        if not items:
            return
        if len(items) != 1:
            messagebox.showinfo("Choose one track", "Select exactly one track to use as the artwork source.")
            return

        source = items[0]
        artwork = source.pending_artwork if source.artwork_change_pending else extract_embedded_artwork(source.path)
        if artwork is None:
            messagebox.showinfo("No artwork", "The selected track does not contain embedded artwork.")
            return

        self.selected_artwork = artwork
        self.artwork_file_label.config(text=f"Selected image: embedded artwork from {source.filename}")

    def _get_selected_artwork(self):
        if self.selected_artwork is not None:
            return self.selected_artwork
        return self._choose_artwork()

    def set_artwork_for_selected(self):
        items = self._selected_items()
        if not items:
            return
        artwork = self._get_selected_artwork()
        if artwork is None:
            return
        for item in items:
            item.set_pending_artwork(artwork)
        self._refresh_tree()

    def set_artwork_for_all(self):
        if not self.items:
            return
        artwork = self._get_selected_artwork()
        if artwork is None:
            return
        for item in self.items:
            item.set_pending_artwork(artwork)
        self._refresh_tree()

    def remove_artwork_from_selected(self):
        for item in self._selected_items():
            item.erase_artwork()
        self._refresh_tree()

    def remove_artwork_from_all(self):
        for item in self.items:
            item.erase_artwork()
        self._refresh_tree()

    def reset_artwork_for_selected(self):
        for item in self._selected_items():
            item.reset_pending_artwork()
        self._refresh_tree()

    def reset_artwork_for_all(self):
        for item in self.items:
            item.reset_pending_artwork()
        self._refresh_tree()

    def _scan_options(self):
        return ScanOptions(
            remove_rules=self.remove_text.get("1.0", "end").splitlines(),
            smart_spaces=bool(self.smart_spaces_var.get()),
            remove_between_enabled=bool(self.between_enabled.get()),
            delimiter_pair=self.between_pair.get(),
        )

    def recompute_proposed_names(self):
        options = self._scan_options()
        for item in self.items:
            item.proposed_filename, item.validation_warnings = propose_filename(item.filename, options)
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

        try:
            result = apply_item_changes(self.folder, self.items)
        except ApplyError as error:
            detail = f"\n\nTechnical detail: {error.technical_detail}" if error.technical_detail else ""
            messagebox.showerror("Apply failed", error.message + detail)
            return

        self.scan_folder()
        message = (
            f"Changes applied.\n\nRenamed: {result.renamed_files}\n"
            f"Tags saved: {result.tagged_files}"
        )
        if result.skipped_files:
            message += f"\n\n{len(result.skipped_files)} file(s) could not be opened for tag editing."
        if result.tag_errors:
            message += f"\n\n{len(result.tag_errors)} file(s) failed while saving tags."
        if result.artwork_files:
            message += f"\nArtwork updated: {result.artwork_files}"
        if result.artwork_errors:
            message += f"\n\n{len(result.artwork_errors)} file(s) failed while saving artwork."
        messagebox.showinfo("Apply Changes", message)

    def show_remove_rules_help(self):
        messagebox.showinfo(
            "Filename Cleanup Help",
            "Enter one piece of text to remove per line. Rules are applied in order.\n\n"
            "Smart spacing tolerates extra spaces around hyphens.\n\n"
            "Enable delimiter removal and enter a two-character pair such as [], (), or && "
            "to remove the delimiters and the text between them.",
        )
