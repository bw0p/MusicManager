import tkinter as tk
from collections.abc import Callable
from tkinter import ttk


_parent: tk.Misc | None = None
_is_dark: Callable[[], bool] = lambda: False
_theme_window: Callable[[tk.Misc, bool], None] | None = None


def configure(
    parent: tk.Misc,
    is_dark: Callable[[], bool],
    theme_window: Callable[[tk.Misc, bool], None] | None = None,
) -> None:
    global _parent, _is_dark, _theme_window
    _parent = parent
    _is_dark = is_dark
    _theme_window = theme_window


def showinfo(title: str, message: str) -> None:
    _show_message(title, message, "Information")


def showwarning(title: str, message: str) -> None:
    _show_message(title, message, "Warning")


def showerror(title: str, message: str) -> None:
    _show_message(title, message, "Error")


def askyesno(title: str, message: str) -> bool:
    result = _dialog(title, message, "Confirmation", (("Yes", True), ("No", False)))
    return bool(result)


def askstring(title: str, prompt: str, parent=None) -> str | None:
    dialog = _make_dialog(title)
    ttk.Label(dialog, text=prompt, wraplength=440, justify="left").grid(
        row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(18, 10)
    )
    value_var = tk.StringVar()
    entry = ttk.Entry(dialog, textvariable=value_var, width=42)
    entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18)

    result = {"value": None}

    def finish(value):
        result["value"] = value
        dialog.destroy()

    ttk.Button(dialog, text="Create", command=lambda: finish(value_var.get())).grid(
        row=2, column=0, sticky="e", padx=(18, 4), pady=18
    )
    ttk.Button(dialog, text="Cancel", command=lambda: finish(None)).grid(
        row=2, column=1, sticky="w", padx=(4, 18), pady=18
    )
    dialog.protocol("WM_DELETE_WINDOW", lambda: finish(None))
    entry.bind("<Return>", lambda _event: finish(value_var.get()))
    entry.bind("<Escape>", lambda _event: finish(None))
    entry.focus_set()
    _show_modal(dialog)
    return result["value"]


def _show_message(title: str, message: str, kind: str) -> None:
    _dialog(title, message, kind, (("OK", True),))


def _dialog(title: str, message: str, kind: str, buttons):
    dialog = _make_dialog(title)
    ttk.Label(dialog, text=kind, style="DialogTitle.TLabel").grid(
        row=0, column=0, columnspan=len(buttons), sticky="w", padx=18, pady=(16, 6)
    )
    ttk.Label(dialog, text=message, wraplength=480, justify="left").grid(
        row=1, column=0, columnspan=len(buttons), sticky="w", padx=18, pady=(0, 12)
    )

    result = {"value": False}

    def finish(value):
        result["value"] = value
        dialog.destroy()

    for column, (label, value) in enumerate(buttons):
        ttk.Button(dialog, text=label, command=lambda selected=value: finish(selected)).grid(
            row=2, column=column, padx=6, pady=(0, 16)
        )
    dialog.protocol("WM_DELETE_WINDOW", lambda: finish(False))
    dialog.bind("<Escape>", lambda _event: finish(False))
    _show_modal(dialog)
    return result["value"]


def _make_dialog(title: str) -> tk.Toplevel:
    if _parent is None:
        raise RuntimeError("Themed dialogs must be configured before use.")
    dialog = tk.Toplevel(_parent)
    dialog.title(title)
    dialog.resizable(False, False)
    dialog.transient(_parent)
    dialog.configure(background="#202124" if _is_dark() else "#f0f0f0")
    dialog.columnconfigure(0, weight=1)
    return dialog


def _show_modal(dialog: tk.Toplevel) -> None:
    dialog.update_idletasks()
    if _theme_window is not None:
        _theme_window(dialog, _is_dark())
    _center_dialog(dialog)
    dialog.grab_set()
    dialog.wait_window()


def _center_dialog(dialog: tk.Toplevel) -> None:
    if _parent is None:
        return
    width = dialog.winfo_reqwidth()
    height = dialog.winfo_reqheight()
    x = _parent.winfo_rootx() + max(0, (_parent.winfo_width() - width) // 2)
    y = _parent.winfo_rooty() + max(0, (_parent.winfo_height() - height) // 2)
    dialog.geometry(f"+{x}+{y}")
