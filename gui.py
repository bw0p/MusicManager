import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from audio_utils import ensure_id3_header


from rename_rules import (
    clean_spaces,
    safe_filename,
    apply_remove_rules,
    remove_between_delims,
    extract_leading_index,
    extract_index_with_pair,
)
from audio_utils import first_contributing_artist, get_tag, set_tag, load_audio


#All supported audio extensions (case-insensitive)
AUDIO_EXTS = {".mp3", ".m4a", ".flac", ".ogg", ".opus", ".wav", ".aiff", ".aac"}


class MusicFixGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Music File Manager (Filename + Tags)")
        self.geometry("1100x650")

        self.folder = None
        self.items = []  # list[dict] in current UI order

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Button(top, text="Choose Folder", command=self.choose_folder).pack(side="left")
        self.folder_label = ttk.Label(top, text="No folder selected")
        self.folder_label.pack(side="left", padx=10)

        ttk.Separator(self).pack(fill="x", padx=10, pady=5)

        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=10)

        ttk.Button(controls, text="Clear All Changes", command=self.clear_all_changes).pack(side="left")
        ttk.Button(controls, text="Apply Changes (Rename + Tags)", command=self.apply_changes).pack(side="right")
        
        # Album artist override
        aa_frame = ttk.Frame(self)
        aa_frame.pack(fill="x", padx=10, pady=8)

        ttk.Label(aa_frame, text="Set Album Artist:").pack(side="left")
        self.album_artist_entry = ttk.Entry(aa_frame, width=40)
        self.album_artist_entry.pack(side="left", padx=8)

        ttk.Button(aa_frame, text="Change to Selected", command=self.set_album_artist_for_selected).pack(side="left", padx=(0, 6))
        ttk.Button(aa_frame, text="Change to All", command=self.set_album_artist_for_all).pack(side="left", padx=(0, 6))
        ttk.Separator(aa_frame, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(aa_frame, text="Clear (Selected)", command=self.clear_album_artist_selected).pack(side="left", padx=(0, 6))
        ttk.Button(aa_frame, text="Clear (All)", command=self.clear_album_artist_all).pack(side="left")

        # --- Rename removal rules ---
        rr = ttk.Frame(self)
        rr.pack(fill="x", padx=10, pady=6)

        header = ttk.Frame(rr)
        header.pack(fill="x")

        ttk.Button(header, text="?", width=3, command=self.show_remove_rules_help).pack(side="left")
        ttk.Label(header, text="Remove text from filename (one per line):").pack(side="left", anchor="w")

        self.remove_text = tk.Text(rr, height=4)
        self.remove_text.pack(fill="x", pady=4)
        self.remove_text.bind("<KeyRelease>", lambda e: self.recompute_proposed_names())

        self.remove_text.insert("1.0", "SpotiDownloader.com - \n")

        opt = ttk.Frame(rr)
        opt.pack(fill="x")

        self.smart_spaces_var = tk.BooleanVar(value=True)
        self.smart_spaces_var.trace_add("write", lambda *args: self.recompute_proposed_names())

        ttk.Checkbutton(
            opt,
            text="Smart spacing (ignore extra spaces around hyphens/spaces)",
            variable=self.smart_spaces_var
        ).pack(side="left")

        # --- Remove between delimiters section ---
        between = ttk.Frame(self)
        between.pack(fill="x", padx=10, pady=6)

        self.between_enabled = tk.BooleanVar(value=False)
        self.between_enabled.trace_add("write", lambda *args: self.recompute_proposed_names())

        ttk.Checkbutton(
            between,
            text="Also remove text between delimiters (including delimiters)",
            variable=self.between_enabled
        ).pack(side="left")

        ttk.Label(between, text="Pair:").pack(side="left", padx=(12, 4))
        self.between_pair = ttk.Entry(between, width=6)
        self.between_pair.bind("<KeyRelease>", lambda e: self.recompute_proposed_names())
        vcmd = (self.register(lambda s: len(s) <= 2), "%P")
        self.between_pair.config(validate="key", validatecommand=vcmd)
        self.between_pair.insert(0, "[]")
        self.between_pair.pack(side="left")

        ttk.Label(between, text="(Example: [] removes [anything])").pack(side="left", padx=8)

        # --- Table action bar ---
        table_bar = ttk.Frame(self)
        table_bar.pack(fill="x", padx=10, pady=(0, 4))

        ttk.Button(table_bar, text="Preview File Changes", command=self.recompute_proposed_names).pack(side="left")

        ttk.Separator(table_bar, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(table_bar, text="Move Up", command=lambda: self.move_selected(-1)).pack(side="left")
        ttk.Button(table_bar, text="Move Down", command=lambda: self.move_selected(1)).pack(side="left", padx=5)

        ttk.Separator(table_bar, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(table_bar, text="Use table order as Track #", command=self.apply_order_as_track_numbers).pack(side="left")
        ttk.Button(table_bar, text="Extract Track # from Title", command=self.extract_track_from_titles).pack(side="left", padx=5)
        ttk.Label(table_bar, text="Extract markers:").pack(side="left", padx=(1, 4))
        self.track_pair = ttk.Entry(table_bar, width=6)
        vcmd2 = (self.register(lambda s: len(s) <= 2), "%P")
        self.track_pair.config(validate="key", validatecommand=vcmd2)
        self.track_pair.insert(0, "[]")
        self.track_pair.pack(side="left")

        ttk.Button(table_bar, text="Clear Track # (Selected)", command=self.clear_track_selected).pack(side="left", padx=(10, 0))
        ttk.Button(table_bar, text="Clear Track # (All)", command=self.clear_track_all).pack(side="left", padx=5)


        # Treeview table
        cols = ("current", "proposed", "artist_used", "albumartist", "track", "warnings")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("current", text="Current Filename")
        self.tree.heading("proposed", text="Proposed Filename")
        self.tree.heading("artist_used", text="First Contributing Artist")
        self.tree.heading("albumartist", text="Album Artist (tag)")
        self.tree.heading("track", text="Track # (tag)")
        self.tree.heading("warnings", text="Warnings")

        self.tree.column("current", width=300)
        self.tree.column("proposed", width=300)
        self.tree.column("artist_used", width=170)
        self.tree.column("albumartist", width=170)
        self.tree.column("track", width=90, anchor="center")
        self.tree.column("warnings", width=250)

        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        bottom = ttk.Label(self, text="Tip: Use Up/Down to reorder. Then 'Use order as Track #' to write track numbers.")
        bottom.pack(fill="x", padx=10, pady=(0, 10))

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
        #print("[scan_folder] scanning:", self.folder)
        self.items.clear()
        for row in self.tree.get_children():
            self.tree.delete(row)

        rules = self.remove_text.get("1.0", "end").splitlines() if hasattr(self, "remove_text") else []
        smart = bool(self.smart_spaces_var.get()) if hasattr(self, "smart_spaces_var") else True
        use_between = bool(self.between_enabled.get()) if hasattr(self, "between_enabled") else False
        pair = self.between_pair.get() if hasattr(self, "between_pair") else ""

        for filename in sorted(os.listdir(self.folder)):
            if filename.lower().endswith(".py"):
                continue
            src = os.path.join(self.folder, filename)
            if not os.path.isfile(src):
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext not in AUDIO_EXTS:
                continue

            audio, err = load_audio(src)
            warnings = []
            artist_first = None
            album_artist = None
            track = None

            if audio is None:
                warnings.append("Failed to read as audio file/Could not read tags")
                warnings.append(err or "(no error provided)")
                print(f"[load_audio] {filename}: {repr(err)}")



            else:
                artist_first = first_contributing_artist(audio)
                album_artist = get_tag(audio, "albumartist")
                track = get_tag(audio, "tracknumber")

                if not album_artist:
                    if artist_first:
                        warnings.append("AlbumArtist missing (can auto-fill)")
                    else:
                        warnings.append("AlbumArtist missing + no artist found")

                if not track:
                    warnings.append("Track# missing")

            base_no_ext = os.path.splitext(filename)[0]
            proposed_base = apply_remove_rules(base_no_ext, rules, smart_spaces=smart)

            if use_between:
                if len(pair) == 2:
                    left, right = pair[0], pair[1]
                    proposed_base = remove_between_delims(proposed_base, left, right)
                else:
                    warnings.append("Delimiter pair must be exactly 2 characters (e.g. [] or &&).")

            proposed_base = safe_filename(clean_spaces(proposed_base))
            proposed_filename = proposed_base + ext

            item = {
                "src": src,
                "filename": filename,
                "ext": ext,
                "audio_ok": (audio is not None),
                "artist_first": artist_first or "",
                "album_artist": album_artist or "",
                "track": track or "",
                "proposed_filename": proposed_filename,
                "base_warnings": list(warnings),
                "warnings": "; ".join(warnings),
                "set_album_artist": None,
                "set_track": None,
            }
            self.items.append(item)

        self._refresh_tree()

    def _refresh_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for idx, it in enumerate(self.items):
            display_albumartist = it["set_album_artist"] if it["set_album_artist"] is not None else it["album_artist"]
            display_track = it["set_track"] if it["set_track"] is not None else it["track"]

            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    it["filename"],
                    it["proposed_filename"],
                    it["artist_first"],
                    display_albumartist,
                    display_track,
                    it["warnings"],
                )
            )

    def move_selected(self, direction: int):
        sel = self.tree.selection()
        if not sel:
            return

        indices = sorted([int(i) for i in sel])
        if direction < 0:
            for i in indices:
                if i <= 0:
                    continue
                self.items[i - 1], self.items[i] = self.items[i], self.items[i - 1]
        else:
            for i in reversed(indices):
                if i >= len(self.items) - 1:
                    continue
                self.items[i + 1], self.items[i] = self.items[i], self.items[i + 1]

        self._refresh_tree()

        new_sel = [str(max(0, min(len(self.items) - 1, i + direction))) for i in indices]
        for iid in new_sel:
            self.tree.selection_add(iid)

    def set_album_artist_for_selected(self):
        value = self.album_artist_entry.get().strip()
        if not value:
            messagebox.showwarning("Empty", "Enter an Album Artist value first.")
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select one or more rows first.")
            return
        for iid in sel:
            self.items[int(iid)]["set_album_artist"] = value
        self._refresh_tree()

    def apply_order_as_track_numbers(self):
        for i, it in enumerate(self.items, start=1):
            it["set_track"] = f"{i:02d}"
        self._refresh_tree()

    def extract_track_from_titles(self):
        changed = 0
        pair = self.track_pair.get().strip() if hasattr(self, "track_pair") else "[]"

        for it in self.items:
            current_track = it["set_track"] if it["set_track"] is not None else it["track"]
            if current_track:
                continue

            title_no_ext = os.path.splitext(it["proposed_filename"])[0]

            # 1) try custom markers first
            maybe = extract_index_with_pair(title_no_ext, pair)

            # 2) fallback to your existing generic patterns
            if maybe is None:
                maybe = extract_leading_index(title_no_ext)

            if maybe is not None:
                it["set_track"] = f"{maybe:02d}"
                changed += 1

        self._refresh_tree()
        messagebox.showinfo("Extract Track #", f"Set track numbers for {changed} file(s) where index was detectable.")


    def apply_changes(self):
        if not self.folder or not self.items:
            return

        if not messagebox.askyesno("Apply", "This will rename files and write tags. Continue?"):
            return

        existing = set(os.listdir(self.folder))
        rename_ops = []

        for it in self.items:
            src = it["src"]
            old = it["filename"]
            new = it["proposed_filename"]

            if old == new:
                continue

            base, ext = os.path.splitext(new)
            candidate = new
            n = 1
            while candidate in existing and candidate != old:
                candidate = f"{base} ({n}){ext}"
                n += 1

            existing.discard(old)
            existing.add(candidate)

            rename_ops.append((old, candidate, src))
            it["proposed_filename"] = candidate

        for old, candidate, src in rename_ops:
            dst = os.path.join(self.folder, candidate)
            try:
                os.rename(src, dst)
            except Exception as e:
                messagebox.showerror("Rename failed", f"Failed renaming:\n{old}\n→ {candidate}\n\n{e}")
                return

            for it in self.items:
                if it["filename"] == old and it["src"] == src:
                    it["filename"] = candidate
                    it["src"] = dst

        tag_errors = 0
        tag_skipped = 0
        
        # ensure MP3 tag container exists before saving
        for it in self.items:
            if it["src"].lower().endswith(".mp3"):
                ensure_id3_header(it["src"])

            audio, err = load_audio(it["src"])
            if audio is None:
                tag_skipped += 1
                if err:
                    print(f"[apply load_audio] {it['filename']}: {err}")
                continue

            current_albumartist = get_tag(audio, "albumartist")
            artist_first = first_contributing_artist(audio)
            desired_albumartist = it["set_album_artist"]
            if desired_albumartist is None:
                if not current_albumartist and artist_first:
                    desired_albumartist = artist_first

            try:
                if desired_albumartist:
                    set_tag(audio, "albumartist", desired_albumartist)

                if it["set_track"]:
                    set_tag(audio, "tracknumber", it["set_track"])

                audio.save()
            except Exception as e:
                tag_errors += 1
                print(f"[tag save failed] {it['filename']}: {type(e).__name__}: {e}")


        self.scan_folder()
        msg = "Done."
        if tag_skipped:
            msg += f"\n\nNote: {tag_skipped} file(s) did not support tag editing (Mutagen couldn't open tags)."
        if tag_errors:
            msg += f"\n\nNote: {tag_errors} file(s) failed tag writing (format limitations or locked files)."
        messagebox.showinfo("Apply", msg)


    def recompute_proposed_names(self):
        rules = self.remove_text.get("1.0", "end").splitlines()
        smart = bool(self.smart_spaces_var.get())

        use_between = bool(self.between_enabled.get()) if hasattr(self, "between_enabled") else False
        pair = self.between_pair.get() if hasattr(self, "between_pair") else ""

        left, right = (pair[0], pair[1]) if len(pair) == 2 else (None, None)

        for it in self.items:
            base = it.get("base_warnings", [])
            it["warnings"] = "; ".join(base)

            base_no_ext = os.path.splitext(it["filename"])[0]
            proposed_base = apply_remove_rules(base_no_ext, rules, smart_spaces=smart)

            if use_between:
                if left and right:
                    proposed_base = remove_between_delims(proposed_base, left, right)
                else:
                    w = list(base)
                    w.append("Delimiter pair must be exactly 2 characters (e.g. [] or &&).")
                    it["warnings"] = "; ".join(w)

            proposed_base = safe_filename(clean_spaces(proposed_base))
            it["proposed_filename"] = proposed_base + it["ext"]

        self._refresh_tree()

    def show_remove_rules_help(self):
        messagebox.showinfo(
            "How to use: Remove Rules",
            "Remove Rules (one per line)\n"
            "--------------------------\n"
            "Type pieces of text you want removed from filenames.\n"
            "Each line is applied in order.\n\n"
            "Example filename:\n"
            "  SpotiDownloader.com - The Glory - Kanye West - Copy\n\n"
            "Recommended rules:\n"
            "  SpotiDownloader.com -\n"
            "  - Kanye West\n"
            "  - Copy\n\n"
            "This would produce:\n"
            "The Glory\n\n"
            "Also, you can remove text between delimiters:\n"
            "  Example: [] removes [anything]\n\n"
            "Tips:\n"
            "• Press Enter for the next rule (one per line).\n"
            "• Smart spacing is ON by default, so spacing around '-' is flexible.\n"
            "• If you remove text without including the '-', you might keep extra separators.\n"
            "  If you remove text WITH '-', you may also remove spacing around it.\n"
            "  (This is expected and helps produce clean titles.)\n\n"
            "Avoid overly generic rules like just '-' because it can remove too much."
        )

    def clear_all_changes(self):
        for it in self.items:
            it["set_album_artist"] = None
            it["set_track"] = None

            base = it.get("base_warnings", [])
            it["warnings"] = "; ".join(base)

        self.recompute_proposed_names()

    def clear_track_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        for iid in sel:
            self.items[int(iid)]["set_track"] = None
        self._refresh_tree()

    def clear_track_all(self):
        for it in self.items:
            it["set_track"] = None
        self._refresh_tree()

    def set_album_artist_for_all(self):
        value = self.album_artist_entry.get().strip()
        if not value:
            messagebox.showwarning("Empty", "Enter an Album Artist value first.")
            return
        for it in self.items:
            it["set_album_artist"] = value
        self._refresh_tree()

    def clear_album_artist_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        for iid in sel:
            self.items[int(iid)]["set_album_artist"] = None
        self._refresh_tree()

    def clear_album_artist_all(self):
        for it in self.items:
            it["set_album_artist"] = None
        self._refresh_tree()

