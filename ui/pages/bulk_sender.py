"""
BulkWave Pro - Bulk Sender Page
The primary interface for uploading contacts, composing messages, and running campaigns.
"""

import os
import tkinter as tk
import tkinter.filedialog as fd
import tkinter.messagebox as mb
import threading
import queue
from datetime import datetime

import customtkinter as ctk
from PIL import Image

from ui.theme import C, FONT, PAD, R, LOG_COLOR
from services.excel_service import ExcelService
from services.whatsapp_service import WhatsAppService
from services.campaign_service import CampaignService
from utils.database import Database
from utils.helpers import get_chrome_data_dir, get_exports_dir, now_str


class BulkSenderPage(ctk.CTkFrame):
    def __init__(self, parent, db: Database = None, sidebar=None, **kwargs):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0, **kwargs)
        self.db = db
        self.sidebar = sidebar

        self.excel_svc = ExcelService()
        self.wa_svc: WhatsAppService | None = None
        self.campaign_svc: CampaignService | None = None

        self._contacts: list[dict] = []
        self._image_path: str = ""
        self._preview_img = None        # keep reference to prevent GC

        self._wa_connected = False
        self._sending = False
        self._paused = False

        self._build()
        self._poll_queues()
        # Start in idle state: only the Start button is active
        self.after(100, lambda: self._set_controls_state("idle"))

    # ═══════════════════════════════════════════════════════════════════════════
    # Build
    # ═══════════════════════════════════════════════════════════════════════════

    def _build(self):
        # Page-level scroll container
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=C["bg"], scrollbar_button_color=C["border"]
        )
        scroll.pack(fill="both", expand=True)

        # Page header
        self._build_header(scroll)

        # Top two-column layout
        top = ctk.CTkFrame(scroll, fg_color="transparent")
        top.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)

        self._build_contacts_card(top)
        self._build_message_card(top)

        # Delay settings
        self._build_delay_card(scroll)

        # Control buttons
        self._build_controls(scroll)

        # Progress
        self._build_progress(scroll)

        # Live logs
        self._build_logs(scroll)

    # ─── Header ───────────────────────────────────────────────────────────────

    def _build_header(self, parent):
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.pack(fill="x", padx=PAD["xl"], pady=(PAD["xl"], PAD["md"]))

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(left, text="Bulk Sender", font=FONT["h1"], text_color=C["txt"]).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Upload contacts · Compose message · Send at scale",
            font=FONT["sm"],
            text_color=C["txt2"],
        ).pack(anchor="w")

        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right")

        self._wa_dot = ctk.CTkLabel(right, text="●", font=FONT["body"], text_color=C["txt3"])
        self._wa_dot.pack(side="left", padx=(0, 4))
        self._wa_lbl = ctk.CTkLabel(right, text="WhatsApp: Offline", font=FONT["sm"], text_color=C["txt3"])
        self._wa_lbl.pack(side="left", padx=(0, PAD["md"]))

        ctk.CTkButton(
            right,
            text="Open WhatsApp Web",
            font=FONT["btn"],
            fg_color=C["accent"],
            hover_color=C["accent_h"],
            text_color="#000000",
            height=36,
            corner_radius=R["md"],
            command=self._open_whatsapp,
        ).pack(side="left")

    # ─── Contacts Card ────────────────────────────────────────────────────────

    def _build_contacts_card(self, parent):
        card = ctk.CTkFrame(
            parent, fg_color=C["card"], corner_radius=R["lg"],
            border_width=1, border_color=C["border"]
        )
        card.grid(row=0, column=0, padx=(0, PAD["sm"]), sticky="nsew", pady=0)

        ctk.CTkLabel(card, text="📁  Contacts", font=FONT["h4"], text_color=C["txt"]).pack(
            anchor="w", padx=PAD["lg"], pady=(PAD["lg"], PAD["sm"])
        )

        # Drop zone
        drop_zone = ctk.CTkFrame(
            card, fg_color=C["input"], corner_radius=R["md"],
            border_width=2, border_color=C["border"], height=90
        )
        drop_zone.pack(fill="x", padx=PAD["lg"])
        drop_zone.pack_propagate(False)
        ctk.CTkLabel(
            drop_zone,
            text="📊  Click to Upload Excel / CSV",
            font=FONT["body"],
            text_color=C["txt2"],
        ).pack(expand=True)
        drop_zone.bind("<Button-1>", lambda e: self._browse_file())
        for child in drop_zone.winfo_children():
            child.bind("<Button-1>", lambda e: self._browse_file())

        self._file_lbl = ctk.CTkLabel(
            card, text="No file selected", font=FONT["sm"], text_color=C["txt3"]
        )
        self._file_lbl.pack(anchor="w", padx=PAD["lg"], pady=(4, PAD["sm"]))

        # Column selectors
        cols_frame = ctk.CTkFrame(card, fg_color="transparent")
        cols_frame.pack(fill="x", padx=PAD["lg"])
        cols_frame.columnconfigure(0, weight=1)
        cols_frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(cols_frame, text="Phone Column", font=FONT["sm"], text_color=C["txt2"]).grid(
            row=0, column=0, sticky="w", pady=(0, 2)
        )
        ctk.CTkLabel(cols_frame, text="Name Column", font=FONT["sm"], text_color=C["txt2"]).grid(
            row=0, column=1, sticky="w", pady=(0, 2), padx=(PAD["sm"], 0)
        )
        self._phone_col_var = ctk.StringVar(value="Select column")
        self._name_col_var = ctk.StringVar(value="None")
        self._phone_col_menu = ctk.CTkOptionMenu(
            cols_frame,
            variable=self._phone_col_var,
            values=["Select column"],
            fg_color=C["input"],
            button_color=C["accent_m"],
            button_hover_color=C["accent_d"],
            text_color=C["txt"],
            font=FONT["sm"],
            dynamic_resizing=False,
            command=lambda _: self._refresh_preview(),
        )
        self._phone_col_menu.grid(row=1, column=0, sticky="ew")
        self._name_col_menu = ctk.CTkOptionMenu(
            cols_frame,
            variable=self._name_col_var,
            values=["None"],
            fg_color=C["input"],
            button_color=C["accent_m"],
            button_hover_color=C["accent_d"],
            text_color=C["txt"],
            font=FONT["sm"],
            dynamic_resizing=False,
            command=lambda _: self._refresh_preview(),
        )
        self._name_col_menu.grid(row=1, column=1, sticky="ew", padx=(PAD["sm"], 0))

        # Start row
        row_frame = ctk.CTkFrame(card, fg_color="transparent")
        row_frame.pack(fill="x", padx=PAD["lg"], pady=(PAD["sm"], 0))
        ctk.CTkLabel(row_frame, text="Start Sending From Row:", font=FONT["sm"], text_color=C["txt2"]).pack(
            side="left"
        )
        self._start_row_var = ctk.StringVar(value="1")
        ctk.CTkEntry(
            row_frame,
            textvariable=self._start_row_var,
            width=70,
            fg_color=C["input"],
            border_color=C["border"],
            text_color=C["txt"],
            font=FONT["sm"],
        ).pack(side="left", padx=PAD["sm"])
        ctk.CTkButton(
            row_frame,
            text="Preview",
            font=FONT["btn"],
            fg_color=C["accent_m"],
            hover_color=C["accent_d"],
            text_color=C["accent"],
            height=30,
            width=80,
            corner_radius=R["sm"],
            command=self._refresh_preview,
        ).pack(side="left")

        # Stats box
        stats_frame = ctk.CTkFrame(card, fg_color=C["input"], corner_radius=R["md"])
        stats_frame.pack(fill="x", padx=PAD["lg"], pady=PAD["sm"])
        for row_i, (icon, label, key) in enumerate([
            ("◉", "Total Contacts:", "total"),
            ("✓", "Valid Numbers:", "valid"),
            ("✗", "Invalid Numbers:", "invalid"),
        ]):
            r = ctk.CTkFrame(stats_frame, fg_color="transparent")
            r.pack(fill="x", padx=PAD["sm"], pady=2)
            color = C["txt2"] if row_i == 0 else (C["ok"] if row_i == 1 else C["err"])
            ctk.CTkLabel(r, text=icon, font=FONT["body"], text_color=color, width=20).pack(side="left")
            ctk.CTkLabel(r, text=label, font=FONT["sm"], text_color=C["txt2"]).pack(side="left", padx=4)
            lbl = ctk.CTkLabel(r, text="0", font=FONT["h4"], text_color=color)
            lbl.pack(side="right", padx=PAD["sm"])
            setattr(self, f"_{key}_lbl", lbl)

        ctk.CTkFrame(card, fg_color="transparent", height=PAD["md"]).pack()

    # ─── Message Card ─────────────────────────────────────────────────────────

    def _build_message_card(self, parent):
        card = ctk.CTkFrame(
            parent, fg_color=C["card"], corner_radius=R["lg"],
            border_width=1, border_color=C["border"]
        )
        card.grid(row=0, column=1, padx=(PAD["sm"], 0), sticky="nsew")

        ctk.CTkLabel(card, text="✉  Message", font=FONT["h4"], text_color=C["txt"]).pack(
            anchor="w", padx=PAD["lg"], pady=(PAD["lg"], PAD["sm"])
        )

        self._msg_box = ctk.CTkTextbox(
            card,
            fg_color=C["input"],
            text_color=C["txt"],
            font=FONT["mono"],
            border_color=C["border"],
            border_width=1,
            corner_radius=R["md"],
            height=160,
            wrap="word",
        )
        self._msg_box.pack(fill="x", padx=PAD["lg"])
        self._msg_box.insert("0.0", "Hello {name}, your message here.")
        self._msg_box.bind("<KeyRelease>", self._update_char_count)

        # Placeholders + char count row
        ph_row = ctk.CTkFrame(card, fg_color="transparent")
        ph_row.pack(fill="x", padx=PAD["lg"], pady=(4, 0))
        ctk.CTkLabel(ph_row, text="Placeholders:", font=FONT["sm"], text_color=C["txt3"]).pack(side="left")
        for ph in ["{name}", "{number}"]:
            ctk.CTkButton(
                ph_row,
                text=ph,
                font=FONT["mono_sm"],
                fg_color=C["accent_m"],
                hover_color=C["accent_d"],
                text_color=C["accent"],
                height=24,
                width=80,
                corner_radius=R["sm"],
                command=lambda p=ph: self._insert_placeholder(p),
            ).pack(side="left", padx=2)
        self._char_lbl = ctk.CTkLabel(ph_row, text="28 chars", font=FONT["sm"], text_color=C["txt3"])
        self._char_lbl.pack(side="right")

        # Template buttons
        tmpl_row = ctk.CTkFrame(card, fg_color="transparent")
        tmpl_row.pack(fill="x", padx=PAD["lg"], pady=(PAD["sm"], 0))
        ctk.CTkButton(
            tmpl_row,
            text="💾  Save Template",
            font=FONT["btn"],
            fg_color=C["input"],
            hover_color=C["hover"],
            text_color=C["txt2"],
            height=30,
            corner_radius=R["sm"],
            command=self._save_template,
        ).pack(side="left", padx=(0, PAD["xs"]))
        ctk.CTkButton(
            tmpl_row,
            text="📂  Load Template",
            font=FONT["btn"],
            fg_color=C["input"],
            hover_color=C["hover"],
            text_color=C["txt2"],
            height=30,
            corner_radius=R["sm"],
            command=self._load_template,
        ).pack(side="left")

        # Divider
        ctk.CTkFrame(card, fg_color=C["border"], height=1).pack(fill="x", padx=PAD["lg"], pady=PAD["sm"])

        # ── Attachment section ────────────────────────────────────────────────
        ctk.CTkLabel(card, text="🖼  Attachment (optional)", font=FONT["h4"], text_color=C["txt"]).pack(
            anchor="w", padx=PAD["lg"], pady=(0, PAD["sm"])
        )

        att_row = ctk.CTkFrame(card, fg_color="transparent")
        att_row.pack(fill="x", padx=PAD["lg"])

        self._img_preview_frame = ctk.CTkFrame(
            att_row, fg_color=C["input"], corner_radius=R["md"],
            width=90, height=90
        )
        self._img_preview_frame.pack(side="left")
        self._img_preview_frame.pack_propagate(False)
        self._img_preview_lbl = ctk.CTkLabel(
            self._img_preview_frame, text="No\nImage", font=FONT["sm"], text_color=C["txt3"]
        )
        self._img_preview_lbl.pack(expand=True)

        btn_col = ctk.CTkFrame(att_row, fg_color="transparent")
        btn_col.pack(side="left", padx=PAD["md"], fill="y")
        ctk.CTkButton(
            btn_col,
            text="Browse Image",
            font=FONT["btn"],
            fg_color=C["accent_m"],
            hover_color=C["accent_d"],
            text_color=C["accent"],
            height=34,
            corner_radius=R["md"],
            command=self._browse_image,
        ).pack(fill="x")
        self._img_name_lbl = ctk.CTkLabel(
            btn_col, text="JPG, PNG or JPEG", font=FONT["sm"], text_color=C["txt3"]
        )
        self._img_name_lbl.pack(anchor="w", pady=(4, 0))
        ctk.CTkButton(
            btn_col,
            text="✕  Clear Image",
            font=FONT["btn"],
            fg_color=C["err_bg"],
            hover_color=C["border"],
            text_color=C["err"],
            height=28,
            corner_radius=R["sm"],
            command=self._clear_image,
        ).pack(anchor="w", pady=(4, 0))

        ctk.CTkFrame(card, fg_color="transparent", height=PAD["md"]).pack()

    # ─── Delay Settings ───────────────────────────────────────────────────────

    def _default_delay(self, key: str, fallback: str) -> str:
        if self.db and self.db.get_setting("turbo_mode", "false").lower() == "true":
            return "0" if key == "min_delay" else "0.5"
        if self.db:
            return self.db.get_setting(key, fallback)
        return fallback

    def _default_turbo(self) -> bool:
        if self.db:
            return self.db.get_setting("turbo_mode", "false").lower() == "true"
        return False

    def _on_turbo_toggle(self):
        if self._turbo_var.get():
            self._min_delay_var.set("0")
            self._max_delay_var.set("0.5")
        else:
            self._min_delay_var.set(self.db.get_setting("min_delay", "3") if self.db else "3")
            self._max_delay_var.set(self.db.get_setting("max_delay", "7") if self.db else "7")
        if self.db:
            self.db.set_setting("turbo_mode", "true" if self._turbo_var.get() else "false")
        if self.wa_svc:
            self.wa_svc.set_fast_mode(self._turbo_var.get())

    def _build_delay_card(self, parent):
        card = ctk.CTkFrame(
            parent, fg_color=C["card"], corner_radius=R["lg"],
            border_width=1, border_color=C["border"]
        )
        card.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=PAD["lg"], pady=PAD["md"])

        ctk.CTkLabel(row, text="⚙  Sending Settings", font=FONT["h4"], text_color=C["txt"]).pack(
            side="left", padx=(0, PAD["xl"])
        )

        for label, attr, default in [
            ("Min Delay (s):", "_min_delay_var", self._default_delay("min_delay", "3")),
            ("Max Delay (s):", "_max_delay_var", self._default_delay("max_delay", "7")),
        ]:
            ctk.CTkLabel(row, text=label, font=FONT["sm"], text_color=C["txt2"]).pack(side="left", padx=(0, 4))
            var = ctk.StringVar(value=default)
            setattr(self, attr, var)
            ctk.CTkEntry(
                row, textvariable=var, width=60,
                fg_color=C["input"], border_color=C["border"],
                text_color=C["txt"], font=FONT["sm"]
            ).pack(side="left", padx=(0, PAD["md"]))

        self._turbo_var = ctk.BooleanVar(
            value=self._default_turbo()
        )
        ctk.CTkCheckBox(
            row,
            text="⚡ Turbo Mode",
            variable=self._turbo_var,
            font=FONT["sm"],
            text_color=C["txt2"],
            fg_color=C["accent"],
            hover_color=C["accent_h"],
            command=self._on_turbo_toggle,
        ).pack(side="left", padx=(0, PAD["md"]))

        ctk.CTkLabel(row, text="Campaign Name:", font=FONT["sm"], text_color=C["txt2"]).pack(
            side="left", padx=(0, 4)
        )
        self._campaign_name_var = ctk.StringVar(
            value=f"Campaign {datetime.now().strftime('%d %b %Y')}"
        )
        ctk.CTkEntry(
            row,
            textvariable=self._campaign_name_var,
            width=200,
            fg_color=C["input"],
            border_color=C["border"],
            text_color=C["txt"],
            font=FONT["sm"],
        ).pack(side="left")

    # ─── Controls ─────────────────────────────────────────────────────────────

    def _build_controls(self, parent):
        card = ctk.CTkFrame(
            parent, fg_color=C["card"], corner_radius=R["lg"],
            border_width=1, border_color=C["border"]
        )
        card.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=PAD["lg"], pady=PAD["md"])

        btn_defs = [
            ("▶  Start Sending", C["accent"],    C["accent_h"], "#000000",  self._start),
            ("⏸  Pause",        C["warn_bg"],   C["border"],   C["warn"],  self._pause),
            ("▶  Resume",       C["ok_bg"],     C["border"],   C["ok"],    self._resume),
            ("⏹  Stop",         C["err_bg"],    C["border"],   C["err"],   self._stop),
        ]
        self._ctrl_btns = {}
        for label, fg, hov, tc, cmd in btn_defs:
            btn = ctk.CTkButton(
                row, text=label, font=FONT["btn"],
                fg_color=fg, hover_color=hov, text_color=tc,
                height=40, corner_radius=R["md"], command=cmd
            )
            btn.pack(side="left", padx=(0, PAD["sm"]))
            self._ctrl_btns[label] = btn

        # Export failed button
        ctk.CTkButton(
            row,
            text="↗  Export Failed",
            font=FONT["btn"],
            fg_color=C["input"],
            hover_color=C["hover"],
            text_color=C["txt2"],
            height=40,
            corner_radius=R["md"],
            command=self._export_failed,
        ).pack(side="right")

    # ─── Progress ─────────────────────────────────────────────────────────────

    def _build_progress(self, parent):
        card = ctk.CTkFrame(
            parent, fg_color=C["card"], corner_radius=R["lg"],
            border_width=1, border_color=C["border"]
        )
        card.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))

        ctk.CTkLabel(card, text="📊  Progress", font=FONT["h4"], text_color=C["txt"]).pack(
            anchor="w", padx=PAD["lg"], pady=(PAD["md"], PAD["sm"])
        )

        self._progress_bar = ctk.CTkProgressBar(
            card,
            fg_color=C["input"],
            progress_color=C["accent"],
            height=14,
            corner_radius=R["sm"],
        )
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", padx=PAD["lg"], pady=(0, PAD["sm"]))

        stats_row = ctk.CTkFrame(card, fg_color="transparent")
        stats_row.pack(fill="x", padx=PAD["lg"], pady=(0, PAD["md"]))

        self._prog_labels: dict[str, ctk.CTkLabel] = {}
        for icon, key, color in [
            ("Total:", "total", C["txt"]),
            ("✅ Sent:", "sent", C["ok"]),
            ("❌ Failed:", "failed", C["err"]),
            ("⏳ Remaining:", "remaining", C["info"]),
            ("ETA:", "eta", C["txt2"]),
        ]:
            ctk.CTkLabel(stats_row, text=icon, font=FONT["sm"], text_color=C["txt3"]).pack(side="left")
            lbl = ctk.CTkLabel(stats_row, text="0", font=FONT["h4"], text_color=color)
            lbl.pack(side="left", padx=(2, PAD["md"]))
            self._prog_labels[key] = lbl

    # ─── Live Logs ────────────────────────────────────────────────────────────

    def _build_logs(self, parent):
        card = ctk.CTkFrame(
            parent, fg_color=C["card"], corner_radius=R["lg"],
            border_width=1, border_color=C["border"]
        )
        card.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["xl"]))

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=PAD["lg"], pady=(PAD["md"], PAD["sm"]))
        ctk.CTkLabel(hdr, text="📋  Live Logs", font=FONT["h4"], text_color=C["txt"]).pack(side="left")
        ctk.CTkButton(
            hdr,
            text="Clear",
            font=FONT["sm"],
            fg_color=C["input"],
            hover_color=C["hover"],
            text_color=C["txt2"],
            height=26,
            width=60,
            corner_radius=R["sm"],
            command=self._clear_logs,
        ).pack(side="right")

        self._log_box = ctk.CTkTextbox(
            card,
            fg_color=C["input"],
            text_color=C["txt2"],
            font=FONT["mono_sm"],
            height=180,
            state="disabled",
            corner_radius=R["md"],
        )
        self._log_box.pack(fill="x", padx=PAD["lg"], pady=(0, PAD["md"]))

    # ═══════════════════════════════════════════════════════════════════════════
    # Queue polling (runs every 100 ms in the main thread)
    # ═══════════════════════════════════════════════════════════════════════════

    def _poll_queues(self):
        if self.campaign_svc:
            # Drain log queue
            try:
                while True:
                    entry = self.campaign_svc.log_queue.get_nowait()
                    self._append_log(entry["level"], entry["time"], entry["message"])
            except queue.Empty:
                pass

            # Drain progress queue
            try:
                while True:
                    p = self.campaign_svc.progress_queue.get_nowait()
                    self._update_progress(p)
                    if p.get("done"):
                        # Campaign has fully finished — reset all state so the
                        # user cannot accidentally re-trigger it and so the UI
                        # clearly shows the campaign is over.
                        self._sending = False
                        self._paused = False
                        self._set_controls_state("idle")
                        self._log_entry("SUCCESS", "Campaign complete. Ready for next send.")
            except queue.Empty:
                pass

        self.after(100, self._poll_queues)

    # ─── Button state machine ─────────────────────────────────────────────────

    def _set_controls_state(self, state: str):
        """
        Update every control button to match the current campaign state.
        state values: 'idle' | 'running' | 'paused'
        """
        cfg = {
            # (fg_color, text_color, state)
            "idle": {
                "▶  Start Sending": (C["accent"],   "#000000", "normal"),
                "⏸  Pause":         (C["warn_bg"],  C["warn"], "disabled"),
                "▶  Resume":        (C["ok_bg"],    C["ok"],   "disabled"),
                "⏹  Stop":          (C["err_bg"],   C["err"],  "disabled"),
            },
            "running": {
                "▶  Start Sending": (C["input"],    C["txt3"], "disabled"),
                "⏸  Pause":         (C["warn_bg"],  C["warn"], "normal"),
                "▶  Resume":        (C["ok_bg"],    C["ok"],   "disabled"),
                "⏹  Stop":          (C["err_bg"],   C["err"],  "normal"),
            },
            "paused": {
                "▶  Start Sending": (C["input"],    C["txt3"], "disabled"),
                "⏸  Pause":         (C["warn_bg"],  C["warn"], "disabled"),
                "▶  Resume":        (C["ok_bg"],    C["ok"],   "normal"),
                "⏹  Stop":          (C["err_bg"],   C["err"],  "normal"),
            },
        }
        settings = cfg.get(state, cfg["idle"])
        for label, (fg, tc, btn_state) in settings.items():
            btn = self._ctrl_btns.get(label)
            if btn:
                btn.configure(fg_color=fg, text_color=tc, state=btn_state)

    # ═══════════════════════════════════════════════════════════════════════════
    # Actions
    # ═══════════════════════════════════════════════════════════════════════════

    def _browse_file(self):
        path = fd.askopenfilename(
            title="Select Contacts File",
            filetypes=[("Excel / CSV", "*.xlsx *.xls *.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        ok, err = self.excel_svc.load_file(path)
        if not ok:
            mb.showerror("File Error", err)
            return

        short = os.path.basename(path)
        self._file_lbl.configure(text=f"📄 {short}  ({self.excel_svc.get_total_rows()} rows)")

        columns = self.excel_svc.get_columns()
        phone_col = self.excel_svc.auto_detect_phone_column() or columns[0]
        name_col = self.excel_svc.auto_detect_name_column()

        self._phone_col_menu.configure(values=columns)
        self._phone_col_var.set(phone_col)

        name_opts = ["None"] + columns
        self._name_col_menu.configure(values=name_opts)
        self._name_col_var.set(name_col if name_col else "None")

        self._refresh_preview()

    def _refresh_preview(self):
        if self.excel_svc.df is None:
            return
        phone_col = self._phone_col_var.get()
        name_col_raw = self._name_col_var.get()
        name_col = None if name_col_raw == "None" else name_col_raw
        try:
            start_row = int(self._start_row_var.get())
        except ValueError:
            start_row = 1

        country_code = ""
        if self.db:
            country_code = self.db.get_setting("country_code", "")

        preview = self.excel_svc.get_preview(phone_col, name_col, start_row, country_code)
        self._contacts = preview.get("valid", [])
        self._total_lbl.configure(text=str(preview.get("total", 0)))
        self._valid_lbl.configure(text=str(len(preview.get("valid", []))))
        self._invalid_lbl.configure(text=str(len(preview.get("invalid", []))))

    def _browse_image(self):
        path = fd.askopenfilename(
            title="Select Image",
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("All files", "*.*")],
        )
        if not path:
            return
        self._image_path = path
        self._img_name_lbl.configure(text=os.path.basename(path))
        self._show_image_preview(path)

    def _show_image_preview(self, path: str):
        try:
            img = Image.open(path)
            img.thumbnail((80, 80))
            # CTkImage avoids the HiDPI warning and scales correctly
            self._preview_img = ctk.CTkImage(light_image=img, dark_image=img, size=(80, 80))
            self._img_preview_lbl.configure(image=self._preview_img, text="")
        except Exception:
            self._img_preview_lbl.configure(text="Preview\nError", image=None)

    def _clear_image(self):
        self._image_path = ""
        self._preview_img = None
        self._img_preview_lbl.configure(text="No\nImage", image=None)
        self._img_name_lbl.configure(text="JPG, PNG or JPEG")

    def _insert_placeholder(self, placeholder: str):
        self._msg_box.insert("insert", placeholder)
        self._update_char_count()

    def _update_char_count(self, event=None):
        count = len(self._msg_box.get("0.0", "end").strip())
        self._char_lbl.configure(text=f"{count} chars")

    def _open_whatsapp(self):
        if self._wa_connected:
            mb.showinfo("WhatsApp", "Already connected to WhatsApp Web.")
            return

        self._set_wa_status("connecting")
        self._log_entry("INFO", "Opening WhatsApp Web… Please scan the QR code.")

        def _init():
            try:
                session_path = str(get_chrome_data_dir())
                if self.db:
                    saved = self.db.get_setting("session_path", "")
                    if saved:
                        session_path = saved
                turbo = self.db.get_setting("turbo_mode", "false").lower() == "true" if self.db else False
                self.wa_svc = WhatsAppService(session_path=session_path, fast_mode=turbo)
                ok, err = self.wa_svc.initialize_browser()
                if not ok:
                    _err = str(err)
                    self.after(0, lambda: self._set_wa_status("offline"))
                    self.after(0, lambda m=_err: self._log_entry("ERROR", f"Browser error: {m}"))
                    return

                def _status_cb(msg):
                    self.after(0, lambda m=msg: self._log_entry("INFO", m))

                logged_in = self.wa_svc.wait_for_login(timeout=120, callback=_status_cb)
                if logged_in:
                    self._wa_connected = True
                    self.after(0, lambda: self._set_wa_status("connected"))
                    self.after(0, lambda: self._log_entry("SUCCESS", "WhatsApp Web connected!"))
                    if self.sidebar:
                        self.after(0, lambda: self.sidebar.set_wa_status(True, "Connected"))
                else:
                    self.after(0, lambda: self._set_wa_status("offline"))
                    self.after(0, lambda: self._log_entry("ERROR", "QR scan timed out. Try again."))
            except Exception as e:
                _msg = str(e)
                self.after(0, lambda: self._set_wa_status("offline"))
                self.after(0, lambda m=_msg: self._log_entry("ERROR", f"Failed to open WhatsApp: {m}"))

        threading.Thread(target=_init, daemon=True).start()

    def _start(self):
        # ── Guard: block double-starts ────────────────────────────────────────
        # Without this guard, clicking Start while a campaign is running creates
        # a second CampaignService thread and the two race each other forever.
        if self._sending:
            mb.showwarning(
                "Already Running",
                "A campaign is already in progress.\n"
                "Click Stop first, then Start a new one.",
            )
            return

        if not self._contacts:
            mb.showwarning("No Contacts", "Please upload a file and ensure there are valid contacts.")
            return
        msg = self._msg_box.get("0.0", "end").strip()
        if not msg:
            mb.showwarning("No Message", "Please type a message before sending.")
            return
        if not self._wa_connected or not self.wa_svc:
            mb.showwarning("Not Connected", "Please open WhatsApp Web and scan the QR code first.")
            return

        try:
            min_d = float(self._min_delay_var.get())
            max_d = float(self._max_delay_var.get())
        except ValueError:
            mb.showerror("Invalid Delay", "Min/Max delay must be numbers.")
            return

        auto_retry = True
        max_retries = 2
        turbo_mode = self._turbo_var.get()
        if self.db:
            auto_retry = self.db.get_setting("auto_retry", "true").lower() == "true"
            max_retries = int(self.db.get_setting("max_retries", "2"))
            self.db.set_setting("turbo_mode", "true" if turbo_mode else "false")

        self.campaign_svc = CampaignService(self.wa_svc, self.db)
        self.campaign_svc.start(
            contacts=self._contacts,
            message=msg,
            image_path=self._image_path or None,
            min_delay=min_d,
            max_delay=max_d,
            campaign_name=self._campaign_name_var.get(),
            auto_retry=auto_retry,
            max_retries=max_retries,
            turbo_mode=turbo_mode,
        )
        self._sending = True
        self._paused = False
        self._set_controls_state("running")
        self._log_entry("SUCCESS", "Campaign started!")

    def _pause(self):
        if self.campaign_svc and self.campaign_svc.is_running:
            self.campaign_svc.pause()
            self._paused = True
            self._set_controls_state("paused")

    def _resume(self):
        if self.campaign_svc and self.campaign_svc.is_paused:
            self.campaign_svc.resume()
            self._paused = False
            self._set_controls_state("running")

    def _stop(self):
        if self.campaign_svc:
            self.campaign_svc.stop()
        self._sending = False
        self._paused = False
        self._set_controls_state("idle")

    def _export_failed(self):
        if not self.campaign_svc:
            mb.showinfo("No Campaign", "No campaign has been run yet.")
            return
        out_dir = get_exports_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = str(out_dir / f"failed_{ts}.xlsx")
        ok, result = self.campaign_svc.export_failed(out_path)
        if ok:
            mb.showinfo("Exported", f"Failed contacts saved to:\n{result}")
        else:
            mb.showerror("Export Error", result)

    def _save_template(self):
        msg = self._msg_box.get("0.0", "end").strip()
        if not msg:
            mb.showwarning("Empty", "Nothing to save.")
            return
        if not self.db:
            return
        name = f"Template {datetime.now().strftime('%d %b %H:%M')}"
        self.db.save_template(name, msg)
        mb.showinfo("Saved", f"Template saved as '{name}'.")

    def _load_template(self):
        if not self.db:
            return
        templates = self.db.get_templates()
        if not templates:
            mb.showinfo("No Templates", "No saved templates found.")
            return
        # Simple popup to pick a template
        win = ctk.CTkToplevel(self)
        win.title("Load Template")
        win.geometry("400x300")
        win.configure(fg_color=C["card"])
        win.grab_set()
        ctk.CTkLabel(win, text="Select a template:", font=FONT["h4"], text_color=C["txt"]).pack(
            padx=PAD["lg"], pady=(PAD["lg"], PAD["sm"]), anchor="w"
        )
        lbox = ctk.CTkScrollableFrame(win, fg_color=C["input"], corner_radius=R["md"])
        lbox.pack(fill="both", expand=True, padx=PAD["lg"], pady=(0, PAD["sm"]))

        def _select(content):
            self._msg_box.delete("0.0", "end")
            self._msg_box.insert("0.0", content)
            self._update_char_count()
            win.destroy()

        for tmpl in templates:
            btn = ctk.CTkButton(
                lbox,
                text=tmpl["name"],
                font=FONT["body"],
                fg_color="transparent",
                hover_color=C["hover"],
                text_color=C["txt"],
                anchor="w",
                command=lambda c=tmpl["content"]: _select(c),
            )
            btn.pack(fill="x", pady=2)

        ctk.CTkButton(
            win, text="Cancel", font=FONT["btn"],
            fg_color=C["err_bg"], hover_color=C["border"], text_color=C["err"],
            command=win.destroy
        ).pack(pady=(0, PAD["md"]))

    def _clear_logs(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("0.0", "end")
        self._log_box.configure(state="disabled")

    # ═══════════════════════════════════════════════════════════════════════════
    # UI update helpers (always called from the main thread via .after())
    # ═══════════════════════════════════════════════════════════════════════════

    def _set_wa_status(self, state: str):
        if state == "connected":
            color, text = C["accent"], "WhatsApp: Connected"
        elif state == "connecting":
            color, text = C["warn"], "WhatsApp: Connecting…"
        else:
            color, text = C["txt3"], "WhatsApp: Offline"
        self._wa_dot.configure(text_color=color)
        self._wa_lbl.configure(text=text, text_color=color)

    def _append_log(self, level: str, ts: str, msg: str):
        color = LOG_COLOR.get(level, C["txt2"])
        self._log_box.configure(state="normal")
        self._log_box.insert("end", f"[{ts}] {msg}\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _log_entry(self, level: str, msg: str):
        self._append_log(level, now_str(), msg)

    def _update_progress(self, p: dict):
        total = p.get("total", 1) or 1
        current = p.get("current", 0)
        frac = current / total
        self._progress_bar.set(frac)
        self._prog_labels["total"].configure(text=str(p.get("total", 0)))
        self._prog_labels["sent"].configure(text=str(p.get("sent", 0)))
        self._prog_labels["failed"].configure(text=str(p.get("failed", 0)))
        self._prog_labels["remaining"].configure(text=str(p.get("remaining", 0)))
        self._prog_labels["eta"].configure(text=p.get("eta", "—"))
