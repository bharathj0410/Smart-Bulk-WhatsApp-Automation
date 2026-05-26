"""
BulkWave Pro - Settings Page
"""

import tkinter as tk
import tkinter.messagebox as mb
import tkinter.filedialog as fd

import customtkinter as ctk

from ui.theme import C, FONT, PAD, R
from utils.helpers import get_chrome_data_dir
from utils.database import Database, DEFAULT_SETTINGS


class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, db: Database = None, **kwargs):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0, **kwargs)
        self.db = db
        self._entries: dict[str, ctk.StringVar | ctk.BooleanVar] = {}
        self._build()
        self._load()

    # ─── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=C["bg"], scrollbar_button_color=C["border"]
        )
        scroll.pack(fill="both", expand=True)

        # Header
        hdr = ctk.CTkFrame(scroll, fg_color="transparent")
        hdr.pack(fill="x", padx=PAD["xl"], pady=(PAD["xl"], PAD["lg"]))
        ctk.CTkLabel(hdr, text="Settings", font=FONT["h1"], text_color=C["txt"]).pack(side="left")

        ctk.CTkButton(
            hdr,
            text="💾  Save Settings",
            font=FONT["btn"],
            fg_color=C["accent"],
            hover_color=C["accent_h"],
            text_color="#000000",
            height=38,
            corner_radius=R["md"],
            command=self._save,
        ).pack(side="right", padx=(PAD["sm"], 0))

        ctk.CTkButton(
            hdr,
            text="↺  Reset Defaults",
            font=FONT["btn"],
            fg_color=C["input"],
            hover_color=C["hover"],
            text_color=C["txt2"],
            height=38,
            corner_radius=R["md"],
            command=self._reset,
        ).pack(side="right")

        # ── General ──────────────────────────────────────────────────────────
        self._section(scroll, "🌐  General")
        gen = self._card(scroll)

        self._field(gen, "Default Country Code", "country_code",
                    "Country code prefixed to 10-digit numbers (e.g. 91 for India)")
        self._toggle(gen, "Dark Mode (restart required)", "theme",
                     true_val="dark", false_val="light")

        # ── WhatsApp ─────────────────────────────────────────────────────────
        self._section(scroll, "💬  WhatsApp")
        wa = self._card(scroll)

        self._field_browse(wa, "Chrome Session Path", "session_path",
                           "Directory where Chrome saves the WhatsApp session cookies",
                           fd.askdirectory)
        self._field_browse(wa, "Chrome Executable Path", "browser_path",
                           "Leave blank or 'auto' to let webdriver-manager handle it",
                           lambda: fd.askopenfilename(filetypes=[("Executable", "*.exe")]))

        # ── Sending ───────────────────────────────────────────────────────────
        self._section(scroll, "⏱  Sending")
        snd = self._card(scroll)

        self._field(snd, "Default Min Delay (seconds)", "min_delay",
                    "Minimum pause between messages")
        self._field(snd, "Default Max Delay (seconds)", "max_delay",
                    "Maximum pause between messages")
        self._toggle(snd, "Turbo Mode (fastest sending)", "turbo_mode")
        self._toggle(snd, "Auto-Retry Failed Messages", "auto_retry")
        self._field(snd, "Max Retry Attempts", "max_retries",
                    "Number of times to retry a failed message")
        self._field(snd, "Earliest Sending Hour (0-23)", "sending_hour_start",
                    "Do not send before this hour")
        self._field(snd, "Latest Sending Hour (0-23)", "sending_hour_end",
                    "Do not send after this hour")

        # ── About ─────────────────────────────────────────────────────────────
        self._section(scroll, "ℹ  About")
        about = self._card(scroll)

        info_text = (
            "BulkWave Pro  v1.0.0\n"
            "Smart Bulk WhatsApp Automation\n\n"
            "Built with Python, CustomTkinter, and Selenium.\n\n"
            "⚠  WARNING: Use responsibly. Sending unsolicited bulk messages\n"
            "may violate WhatsApp's Terms of Service. Always obtain consent\n"
            "from recipients before messaging them."
        )
        ctk.CTkLabel(
            about,
            text=info_text,
            font=FONT["body"],
            text_color=C["txt2"],
            justify="left",
            wraplength=700,
        ).pack(anchor="w", padx=PAD["lg"], pady=PAD["md"])

        ctk.CTkFrame(scroll, fg_color="transparent", height=PAD["xl"]).pack()

    # ─── Widget helpers ───────────────────────────────────────────────────────

    def _section(self, parent, title: str):
        ctk.CTkLabel(
            parent, text=title, font=FONT["h4"], text_color=C["txt"]
        ).pack(anchor="w", padx=PAD["xl"], pady=(PAD["md"], 2))

    def _card(self, parent) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent, fg_color=C["card"], corner_radius=R["lg"],
            border_width=1, border_color=C["border"]
        )
        card.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))
        return card

    def _field(self, parent, label: str, key: str, hint: str = ""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=PAD["lg"], pady=PAD["sm"])

        lbl_col = ctk.CTkFrame(row, fg_color="transparent", width=260)
        lbl_col.pack(side="left", fill="y")
        lbl_col.pack_propagate(False)
        ctk.CTkLabel(lbl_col, text=label, font=FONT["body"], text_color=C["txt"], anchor="w").pack(anchor="w")
        if hint:
            ctk.CTkLabel(lbl_col, text=hint, font=FONT["xs"], text_color=C["txt3"], anchor="w",
                         wraplength=240).pack(anchor="w")

        var = ctk.StringVar()
        ctk.CTkEntry(
            row,
            textvariable=var,
            fg_color=C["input"],
            border_color=C["border"],
            text_color=C["txt"],
            font=FONT["body"],
            height=36,
        ).pack(side="left", fill="x", expand=True, padx=(PAD["md"], 0))
        self._entries[key] = var

    def _field_browse(self, parent, label: str, key: str, hint: str, browse_fn):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=PAD["lg"], pady=PAD["sm"])

        lbl_col = ctk.CTkFrame(row, fg_color="transparent", width=260)
        lbl_col.pack(side="left", fill="y")
        lbl_col.pack_propagate(False)
        ctk.CTkLabel(lbl_col, text=label, font=FONT["body"], text_color=C["txt"], anchor="w").pack(anchor="w")
        if hint:
            ctk.CTkLabel(lbl_col, text=hint, font=FONT["xs"], text_color=C["txt3"], anchor="w",
                         wraplength=240).pack(anchor="w")

        var = ctk.StringVar()
        entry_row = ctk.CTkFrame(row, fg_color="transparent")
        entry_row.pack(side="left", fill="x", expand=True, padx=(PAD["md"], 0))

        ctk.CTkEntry(
            entry_row,
            textvariable=var,
            fg_color=C["input"],
            border_color=C["border"],
            text_color=C["txt"],
            font=FONT["body"],
            height=36,
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            entry_row,
            text="Browse",
            font=FONT["btn"],
            fg_color=C["accent_m"],
            hover_color=C["accent_d"],
            text_color=C["accent"],
            width=80,
            height=36,
            corner_radius=R["sm"],
            command=lambda v=var, fn=browse_fn: self._do_browse(v, fn),
        ).pack(side="left", padx=(PAD["xs"], 0))

        self._entries[key] = var

    def _do_browse(self, var: ctk.StringVar, browse_fn):
        result = browse_fn()
        if result:
            var.set(result)

    def _toggle(self, parent, label: str, key: str, true_val="true", false_val="false"):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=PAD["lg"], pady=PAD["sm"])
        ctk.CTkLabel(row, text=label, font=FONT["body"], text_color=C["txt"]).pack(side="left")

        bool_var = tk.BooleanVar(value=True)

        def _on_toggle():
            pass  # BooleanVar updates automatically

        switch = ctk.CTkSwitch(
            row,
            text="",
            variable=bool_var,
            onvalue=True,
            offvalue=False,
            progress_color=C["accent"],
            button_color=C["accent_h"],
            fg_color=C["input"],
            command=_on_toggle,
        )
        switch.pack(side="right")

        # Store a thin adapter that maps bool <-> string values
        adapter = _BoolAdapter(bool_var, true_val, false_val)
        self._entries[key] = adapter

    # ─── Load / Save ──────────────────────────────────────────────────────────

    def _load(self):
        if not self.db:
            return
        settings = self.db.get_all_settings()
        for key, widget in self._entries.items():
            val = settings.get(key, DEFAULT_SETTINGS.get(key, ""))
            widget.set(val)

    def _save(self):
        if not self.db:
            mb.showerror("Error", "Database not available.")
            return
        data = {key: widget.get() for key, widget in self._entries.items()}
        self.db.save_settings(data)
        mb.showinfo("Saved", "Settings saved successfully!")

    def _reset(self):
        if not mb.askyesno("Reset", "Reset all settings to defaults?"):
            return
        for key, widget in self._entries.items():
            widget.set(DEFAULT_SETTINGS.get(key, ""))
        if self.db:
            self.db.save_settings(
                {k: DEFAULT_SETTINGS.get(k, "") for k in self._entries}
            )
        mb.showinfo("Reset", "Settings have been reset to defaults.")


class _BoolAdapter:
    """Adapts a ctk.BooleanVar to the string-based get/set interface."""

    def __init__(self, var: tk.BooleanVar, true_val: str, false_val: str):
        self._var = var
        self._true = true_val
        self._false = false_val

    def get(self) -> str:
        return self._true if self._var.get() else self._false

    def set(self, value: str):
        self._var.set(value == self._true)
