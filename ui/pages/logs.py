"""
BulkWave Pro - Logs Page
Displays and filters persisted application logs.
"""

import tkinter.filedialog as fd
import tkinter.messagebox as mb
from datetime import datetime

import customtkinter as ctk

from ui.theme import C, FONT, PAD, R, LOG_COLOR
from utils.database import Database


class LogsPage(ctk.CTkFrame):
    def __init__(self, parent, db: Database = None, **kwargs):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0, **kwargs)
        self.db = db
        self._build()
        self.refresh()

    # ─── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=PAD["xl"], pady=(PAD["xl"], PAD["md"]))
        ctk.CTkLabel(hdr, text="Logs", font=FONT["h1"], text_color=C["txt"]).pack(side="left")
        ctk.CTkLabel(
            hdr, text="Application & campaign event log", font=FONT["sm"], text_color=C["txt2"]
        ).pack(side="left", padx=PAD["lg"])

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))

        # Filter buttons
        self._filter_var = ctk.StringVar(value="ALL")
        for level in ("ALL", "SUCCESS", "INFO", "WARNING", "ERROR"):
            color = LOG_COLOR.get(level, C["txt2"]) if level != "ALL" else C["accent"]
            is_active = level == "ALL"
            btn = ctk.CTkButton(
                toolbar,
                text=level,
                font=FONT["btn"],
                fg_color=C["accent_m"] if is_active else C["input"],
                hover_color=C["hover"],
                text_color=C["accent"] if is_active else C["txt2"],
                height=32,
                width=90,
                corner_radius=R["sm"],
                command=lambda lv=level: self._set_filter(lv),
            )
            btn.pack(side="left", padx=(0, PAD["xs"]))

        # Right-side actions
        ctk.CTkButton(
            toolbar,
            text="↻  Refresh",
            font=FONT["btn"],
            fg_color=C["input"],
            hover_color=C["hover"],
            text_color=C["txt2"],
            height=32,
            width=100,
            corner_radius=R["sm"],
            command=self.refresh,
        ).pack(side="right", padx=(PAD["xs"], 0))

        ctk.CTkButton(
            toolbar,
            text="↗  Export",
            font=FONT["btn"],
            fg_color=C["input"],
            hover_color=C["hover"],
            text_color=C["txt2"],
            height=32,
            width=90,
            corner_radius=R["sm"],
            command=self._export_logs,
        ).pack(side="right", padx=(0, PAD["xs"]))

        ctk.CTkButton(
            toolbar,
            text="🗑  Clear All",
            font=FONT["btn"],
            fg_color=C["err_bg"],
            hover_color=C["border"],
            text_color=C["err"],
            height=32,
            width=100,
            corner_radius=R["sm"],
            command=self._clear_logs,
        ).pack(side="right", padx=(0, PAD["xs"]))

        # Log display
        log_card = ctk.CTkFrame(
            self, fg_color=C["card"], corner_radius=R["lg"],
            border_width=1, border_color=C["border"]
        )
        log_card.pack(fill="both", expand=True, padx=PAD["xl"], pady=(0, PAD["xl"]))

        # Column headers
        col_hdr = ctk.CTkFrame(log_card, fg_color=C["input"], corner_radius=0, height=32)
        col_hdr.pack(fill="x")
        col_hdr.pack_propagate(False)
        for txt, w in [("Timestamp", 160), ("Level", 90), ("Message", 500)]:
            ctk.CTkLabel(
                col_hdr, text=txt, font=FONT["sm"], text_color=C["txt2"], width=w, anchor="w"
            ).pack(side="left", padx=PAD["sm"])

        self._log_scroll = ctk.CTkScrollableFrame(
            log_card, fg_color="transparent", scrollbar_button_color=C["border"]
        )
        self._log_scroll.pack(fill="both", expand=True)

        self._current_filter = "ALL"
        self._all_logs: list[dict] = []

    # ─── Data ─────────────────────────────────────────────────────────────────

    def refresh(self):
        if not self.db:
            return
        self._all_logs = self.db.get_logs(limit=500)
        self._render()

    def _set_filter(self, level: str):
        self._current_filter = level
        self._render()

    def _render(self):
        for w in self._log_scroll.winfo_children():
            w.destroy()

        logs = self._all_logs
        if self._current_filter != "ALL":
            logs = [l for l in logs if l.get("level") == self._current_filter]

        if not logs:
            ctk.CTkLabel(
                self._log_scroll,
                text="No log entries found.",
                font=FONT["body"],
                text_color=C["txt3"],
            ).pack(pady=PAD["xl"])
            return

        for entry in logs:
            self._add_log_row(entry)

    def _add_log_row(self, entry: dict):
        level = entry.get("level", "INFO")
        color = LOG_COLOR.get(level, C["txt2"])

        row = ctk.CTkFrame(self._log_scroll, fg_color="transparent", height=28)
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        ctk.CTkLabel(
            row,
            text=(entry.get("timestamp") or "")[:19],
            font=FONT["mono_sm"],
            text_color=C["txt3"],
            width=160,
            anchor="w",
        ).pack(side="left", padx=(PAD["sm"], 0))

        ctk.CTkLabel(
            row,
            text=level,
            font=FONT["mono_sm"],
            text_color=color,
            width=90,
            anchor="w",
        ).pack(side="left")

        ctk.CTkLabel(
            row,
            text=entry.get("message", ""),
            font=FONT["mono_sm"],
            text_color=C["txt"],
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        # Row separator
        ctk.CTkFrame(
            self._log_scroll, fg_color=C["border_s"], height=1, corner_radius=0
        ).pack(fill="x")

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _clear_logs(self):
        if not mb.askyesno("Clear Logs", "Clear all log entries? This cannot be undone."):
            return
        if self.db:
            self.db.clear_logs()
        self._all_logs = []
        self._render()

    def _export_logs(self):
        path = fd.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt"), ("All Files", "*.*")],
            initialfile=f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if not path:
            return
        logs = self._all_logs
        if self._current_filter != "ALL":
            logs = [l for l in logs if l.get("level") == self._current_filter]
        try:
            with open(path, "w", encoding="utf-8") as f:
                for entry in logs:
                    f.write(
                        f"[{entry.get('timestamp','')[:19]}]  "
                        f"{entry.get('level',''):8}  "
                        f"{entry.get('message','')}\n"
                    )
            mb.showinfo("Exported", f"Logs saved to:\n{path}")
        except Exception as e:
            mb.showerror("Export Error", str(e))
