import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from mutagen import File  # pip install mutagen

AUDIO_EXTS = {".mp3", ".m4a", ".flac", ".ogg", ".opus", ".wav", ".aiff", ".aac"}


#====Helper functions for filename/tag processing ====

def clean_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def safe_filename(name: str) -> str:
    name = "".join(c for c in name if c not in r'\/:*?"<>|')
    name = name.rstrip(". ").strip()
    return name

def first_contributing_artist(audio) -> str | None:
    """
    Best-effort across common tag names. Returns first entry, split on ';' (or other separators).
    """
    if not audio:
        return None

    candidate_keys = [
        "contributingartists",
        "contributing artists",
        "artists",
        "artist",       # most common
        "albumartist",
    ]

    for key in candidate_keys:
        val = audio.get(key)
        if not val:
            continue
        text = val[0] if isinstance(val, list) and val else str(val)
        text = text.strip()
        if not text:
            continue

        # primary split on semicolon
        first = re.split(r"\s*;\s*", text, maxsplit=1)[0]
        if first == text:
            # optional fallback split for multi-artist strings
            first = re.split(r"\s*/\s*|\s*,\s*|\s*&\s*", text, maxsplit=1)[0]

        first = first.strip()
        return first if first else None

    return None

def get_tag(audio, key: str) -> str | None:
    val = audio.get(key)
    if not val:
        return None
    if isinstance(val, list) and val:
        s = str(val[0]).strip()
        return s if s else None
    s = str(val).strip()
    return s if s else None

def set_tag(audio, key: str, value: str):
    # mutagen easy tags expect list values
    audio[key] = [value]

def remove_prefix(name: str, prefix: str) -> str:
    return name[len(prefix):] if name.startswith(prefix) else name

def remove_trailing_artist(name_no_ext: str, artist: str) -> str:
    if not artist:
        return name_no_ext

    def norm(x: str) -> str:
        return clean_spaces(x).lower()

    m = re.search(r"\s*-\s*(.+)\s*$", name_no_ext)
    if not m:
        return name_no_ext

    tail = m.group(1)
    if norm(tail) == norm(artist):
        return clean_spaces(name_no_ext[:m.start()])

    return name_no_ext

def extract_leading_index(title: str) -> int | None:
    """
    Try to parse track index from title prefix:
    "01 - Song", "1. Song", "[03] Song", "03 Song"
    """
    s = title.strip()

    patterns = [
        r"^\[(\d{1,3})\]\s+",
        r"^(\d{1,3})\s*[-.]\s+",
        r"^(\d{1,3})\s+",
    ]
    for pat in patterns:
        m = re.match(pat, s)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
    return None

def build_fuzzy_pattern(literal: str) -> re.Pattern:
    """
    Turn a literal removal string into a regex that is tolerant to whitespace.
    - Any run of whitespace becomes r"\s+"
    - Any " - " / "-" sequence becomes r"\s*-\s*"
    """
    s = literal.strip()
    if not s:
        return re.compile(r"$^")  # matches nothing

    # Escape everything first (treat user input as literal)
    esc = re.escape(s)

    # Make escaped spaces flexible: "\ " -> "\s+"
    esc = re.sub(r"(\\\s)+", r"\\s+", esc)

    # Make hyphen separators flexible: allow optional spaces around "-"
    # Replace escaped "-" with "\s*-\s*"
    esc = esc.replace(r"\-", r"\s*-\s*")

    return re.compile(esc, flags=re.IGNORECASE)

def apply_remove_rules(name_no_ext: str, rules: list[str], smart_spaces: bool) -> str:
    s = name_no_ext
    for rule in rules:
        rule = rule.strip()
        if not rule:
            continue
        if smart_spaces:
            pat = build_fuzzy_pattern(rule)
            s = pat.sub("", s)
        else:
            s = s.replace(rule, "")
        s = clean_spaces(s)
    return s




class MusicFixGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Music Fixer (Filename + Tags)")
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

        ttk.Button(controls, text="Refresh / Preview", command=self.scan_folder).pack(side="left")
        ttk.Button(controls, text="Move Up", command=lambda: self.move_selected(-1)).pack(side="left", padx=5)
        ttk.Button(controls, text="Move Down", command=lambda: self.move_selected(1)).pack(side="left", padx=5)

        ttk.Button(controls, text="Use order as Track #", command=self.apply_order_as_track_numbers).pack(side="left", padx=12)

        ttk.Button(controls, text="Extract Track # from Title", command=self.extract_track_from_titles).pack(side="left", padx=5)

        ttk.Button(controls, text="Apply Changes (Rename + Tags)", command=self.apply_changes).pack(side="right")

        # Album artist override
        aa_frame = ttk.Frame(self)
        aa_frame.pack(fill="x", padx=10, pady=8)

        ttk.Label(aa_frame, text="Album Artist input (for selected rows):").pack(side="left")
        self.album_artist_entry = ttk.Entry(aa_frame, width=40)
        self.album_artist_entry.pack(side="left", padx=8)

        ttk.Button(aa_frame, text="Set Album Artist for Selected", command=self.set_album_artist_for_selected).pack(side="left")

        # --- Rename removal rules ---
        rr = ttk.Frame(self)
        rr.pack(fill="x", padx=10, pady=6)

        #Button to show help for remove rules, and label
        header = ttk.Frame(rr)
        header.pack(fill="x")

        ttk.Label(header, text="Remove text from filename (one per line):").pack(side="left", anchor="w")

        ttk.Button(header, text="?", width=3, command=self.show_remove_rules_help).pack(side="right")


        self.remove_text = tk.Text(rr, height=4)
        self.remove_text.pack(fill="x", pady=4)

        # sensible default
        self.remove_text.insert("1.0", "SpotiDownloader.com - \n")

        opt = ttk.Frame(rr)
        opt.pack(fill="x")

        self.smart_spaces_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt, text="Smart spacing (ignore extra spaces around hyphens/spaces)", variable=self.smart_spaces_var).pack(side="left")

        ttk.Button(opt, text="Recompute Proposed Names", command=self.recompute_proposed_names).pack(side="right")


        # Treeview table
        cols = ("current", "proposed", "artist_used", "albumartist", "track", "warnings")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("current", text="Current Filename")
        self.tree.heading("proposed", text="Proposed Filename")
        self.tree.heading("artist_used", text="Artist Used (first)")
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
        bottom.pack(fill="x", padx=10, pady=(0,10))

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
        for row in self.tree.get_children():
            self.tree.delete(row)

        for filename in sorted(os.listdir(self.folder)):
            if filename.lower().endswith(".py"):
                continue
            src = os.path.join(self.folder, filename)
            if not os.path.isfile(src):
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext not in AUDIO_EXTS:
                continue

            audio = File(src, easy=True)
            warnings = []
            artist_first = None
            album_artist = None
            track = None

            if not audio:
                warnings.append("Unsupported tags")
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

            rules = self.remove_text.get("1.0", "end").splitlines() if hasattr(self, "remove_text") else []
            smart = bool(self.smart_spaces_var.get()) if hasattr(self, "smart_spaces_var") else True
            base_no_ext = os.path.splitext(filename)[0]
            proposed_base = apply_remove_rules(base_no_ext, rules, smart_spaces=smart)
            proposed_base = safe_filename(clean_spaces(proposed_base))
            proposed_filename = proposed_base + ext

            item = {
                "src": src,
                "filename": filename,
                "ext": ext,
                "audio_ok": bool(audio),
                "artist_first": artist_first or "",
                "album_artist": album_artist or "",
                "track": track or "",
                "proposed_filename": proposed_filename,
                "warnings": "; ".join(warnings),
                "set_album_artist": None,   # pending override
                "set_track": None,          # pending override
            }
            self.items.append(item)

        self._refresh_tree()

    def _refresh_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for idx, it in enumerate(self.items):
            # show pending changes if set
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
            # move up: process lowest first
            for i in indices:
                if i <= 0:
                    continue
                self.items[i-1], self.items[i] = self.items[i], self.items[i-1]
        else:
            # move down: process highest first
            for i in reversed(indices):
                if i >= len(self.items) - 1:
                    continue
                self.items[i+1], self.items[i] = self.items[i], self.items[i+1]

        self._refresh_tree()
        # reselect moved items
        new_sel = [str(max(0, min(len(self.items)-1, i + direction))) for i in indices]
        for iid in new_sel:
            self.tree.selection_add(iid)

    def set_album_artist_for_selected(self):
        value = self.album_artist_entry.get().strip()
        if not value:
            messagebox.showwarning("Empty", "Enter an Album Artist value first.")
            return
        sel = self.tree.selection()
        if not sel:
            return
        for iid in sel:
            self.items[int(iid)]["set_album_artist"] = value
        self._refresh_tree()

    def apply_order_as_track_numbers(self):
        # sets pending track numbers based on UI order
        for i, it in enumerate(self.items, start=1):
            it["set_track"] = f"{i:02d}"
        self._refresh_tree()

    def extract_track_from_titles(self):
        """
        If track# is missing, try infer it from the proposed filename (or current).
        """
        changed = 0
        for it in self.items:
            # only set if missing and not already pending
            current_track = it["set_track"] if it["set_track"] is not None else it["track"]
            if current_track:
                continue

            title_no_ext = os.path.splitext(it["proposed_filename"])[0]
            maybe = extract_leading_index(title_no_ext)
            if maybe is not None:
                it["set_track"] = f"{maybe:02d}"
                changed += 1

        self._refresh_tree()
        messagebox.showinfo("Extract Track #", f"Set track numbers for {changed} file(s) where index was detectable.")

    def apply_changes(self):
        if not self.folder or not self.items:
            return

        # Confirm
        if not messagebox.askyesno("Apply", "This will rename files and write tags. Continue?"):
            return

        # First pass: rename (handle collisions)
        # We'll do renames carefully: build mapping, ensure uniqueness
        existing = set(os.listdir(self.folder))
        rename_ops = []
        for it in self.items:
            src = it["src"]
            old = it["filename"]
            new = it["proposed_filename"]

            if old == new:
                continue

            # ensure unique in folder (taking into account already-existing files)
            base, ext = os.path.splitext(new)
            candidate = new
            n = 1
            while candidate in existing and candidate != old:
                candidate = f"{base} ({n}){ext}"
                n += 1

            existing.discard(old)
            existing.add(candidate)

            rename_ops.append((old, candidate, src))
            it["proposed_filename"] = candidate  # keep in sync

        # Execute renames
        for old, candidate, src in rename_ops:
            dst = os.path.join(self.folder, candidate)
            try:
                os.rename(src, dst)
            except Exception as e:
                messagebox.showerror("Rename failed", f"Failed renaming:\n{old}\n→ {candidate}\n\n{e}")
                return

            # update internal paths
            for it in self.items:
                if it["filename"] == old and it["src"] == src:
                    it["filename"] = candidate
                    it["src"] = dst

        # Second pass: write tags
        tag_errors = 0
        for it in self.items:
            audio = File(it["src"], easy=True)
            if not audio:
                continue

            # Album artist auto-fill rule: if missing and artist exists, and no manual override
            current_albumartist = get_tag(audio, "albumartist")
            artist_first = first_contributing_artist(audio)

            desired_albumartist = it["set_album_artist"]
            if desired_albumartist is None:
                if not current_albumartist and artist_first:
                    desired_albumartist = artist_first  # your rule

            try:
                if desired_albumartist:
                    set_tag(audio, "albumartist", desired_albumartist)

                if it["set_track"]:
                    set_tag(audio, "tracknumber", it["set_track"])

                audio.save()
            except Exception:
                tag_errors += 1

        self.scan_folder()
        msg = "Done."
        if tag_errors:
            msg += f"\n\nNote: {tag_errors} file(s) failed tag writing (format limitations or locked files)."
        messagebox.showinfo("Apply", msg)

    def recompute_proposed_names(self):
        rules = self.remove_text.get("1.0", "end").splitlines()
        smart = bool(self.smart_spaces_var.get())

        for it in self.items:
            base_no_ext = os.path.splitext(it["filename"])[0]
            proposed_base = apply_remove_rules(base_no_ext, rules, smart_spaces=smart)
            proposed_base = safe_filename(clean_spaces(proposed_base))
            it["proposed_filename"] = proposed_base + it["ext"]
    #Tutorial for Remove Rules
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
            "Tips:\n"
            "• Press Enter for the next rule (one rule per line).\n"
            "• Smart spacing is ON by default, so spacing around '-' is flexible.\n"
            "• If you remove text without including the '-', you might keep extra separators.\n"
            "  If you remove text WITH '-', you may also remove spacing around it.\n"
            "  (This is expected and helps produce clean titles.)\n\n"
            "Avoid overly generic rules like just '-' because it can remove too much."
        )


        self._refresh_tree()







if __name__ == "__main__":
    app = MusicFixGUI()
    app.mainloop()
