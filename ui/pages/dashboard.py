"""
BulkWave Pro - Dashboard Page
Shows overall campaign statistics and recent activity.
"""

import customtkinter as ctk
from ui.theme import C, FONT, PAD, R, STATUS_COLOR
from utils.helpers import now_timestamp


def _stat_card(
    parent, title: str, value: str, sub: str, color: str
) -> tuple["ctk.CTkFrame", "ctk.CTkLabel"]:
    """Reusable metric card. Returns (card_frame, value_label)."""
    card = ctk.CTkFrame(
        parent,
        fg_color=C["card"],
        corner_radius=R["lg"],
        border_width=1,
        border_color=C["border"],
    )
    ctk.CTkLabel(card, text=title, font=FONT["sm"], text_color=C["txt2"]).pack(
        anchor="w", padx=PAD["md"], pady=(PAD["md"], 2)
    )
    value_lbl = ctk.CTkLabel(card, text=value, font=FONT["h1"], text_color=color)
    value_lbl.pack(anchor="w", padx=PAD["md"])
    ctk.CTkLabel(card, text=sub, font=FONT["xs"], text_color=C["txt3"]).pack(
        anchor="w", padx=PAD["md"], pady=(2, PAD["md"])
    )
    return card, value_lbl


class DashboardPage(ctk.CTkFrame):
    def __init__(self, parent, db=None, on_navigate=None, **kwargs):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0, **kwargs)
        self.db = db
        self.on_navigate = on_navigate

        self._stat_labels: dict = {}
        self._campaign_rows: list = []

        self._build()

    # ─── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        # Scrollable container
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=C["bg"], scrollbar_button_color=C["border"]
        )
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        # Header
        hdr = ctk.CTkFrame(scroll, fg_color="transparent")
        hdr.pack(fill="x", padx=PAD["xl"], pady=(PAD["xl"], PAD["md"]))
        ctk.CTkLabel(hdr, text="Dashboard", font=FONT["h1"], text_color=C["txt"]).pack(
            side="left"
        )
        ctk.CTkLabel(
            hdr,
            text="Overview of your WhatsApp campaigns",
            font=FONT["sm"],
            text_color=C["txt2"],
        ).pack(side="left", padx=PAD["lg"])

        refresh_btn = ctk.CTkButton(
            hdr,
            text="↻  Refresh",
            font=FONT["btn"],
            fg_color=C["input"],
            hover_color=C["hover"],
            text_color=C["txt2"],
            width=110,
            height=34,
            corner_radius=R["md"],
            command=self.refresh,
        )
        refresh_btn.pack(side="right")

        # ── Stats row ─────────────────────────────────────────────────────────
        stats_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        stats_frame.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["lg"]))
        for i in range(4):
            stats_frame.columnconfigure(i, weight=1, uniform="stat")

        stat_defs = [
            ("total_campaigns", "Total Campaigns",   "0", "All time",            C["info"]),
            ("total_sent",      "Messages Sent",      "0", "All time",            C["ok"]),
            ("total_failed",    "Failed Messages",    "0", "All time",            C["err"]),
            ("success_rate",    "Success Rate",       "0%","Sent / Total × 100", C["accent"]),
        ]
        for col, (key, title, val, sub, clr) in enumerate(stat_defs):
            card, value_lbl = _stat_card(stats_frame, title, val, sub, clr)
            card.grid(row=0, column=col, padx=PAD["sm"], sticky="nsew")
            self._stat_labels[key] = value_lbl

        # ── Quick actions ─────────────────────────────────────────────────────
        qa_frame = ctk.CTkFrame(scroll, fg_color=C["card"], corner_radius=R["lg"],
                                border_width=1, border_color=C["border"])
        qa_frame.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["lg"]))

        ctk.CTkLabel(
            qa_frame, text="Quick Actions", font=FONT["h4"], text_color=C["txt"]
        ).pack(anchor="w", padx=PAD["lg"], pady=(PAD["md"], PAD["sm"]))

        btn_row = ctk.CTkFrame(qa_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=PAD["lg"], pady=(0, PAD["md"]))

        actions = [
            ("◎  Start New Campaign", self._go_bulk),
            ("◷  View History",       self._go_history),
            ("≡   View Logs",          self._go_logs),
            ("◈  Settings",           self._go_settings),
        ]
        for label, cmd in actions:
            ctk.CTkButton(
                btn_row,
                text=label,
                font=FONT["btn"],
                fg_color=C["accent_m"],
                hover_color=C["accent_d"],
                text_color=C["accent"],
                height=38,
                corner_radius=R["md"],
                command=cmd,
            ).pack(side="left", padx=(0, PAD["sm"]))

        # ── Recent campaigns ──────────────────────────────────────────────────
        rc_frame = ctk.CTkFrame(scroll, fg_color=C["card"], corner_radius=R["lg"],
                                border_width=1, border_color=C["border"])
        rc_frame.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["xl"]))

        rc_hdr = ctk.CTkFrame(rc_frame, fg_color="transparent")
        rc_hdr.pack(fill="x", padx=PAD["lg"], pady=(PAD["md"], PAD["sm"]))
        ctk.CTkLabel(
            rc_hdr, text="Recent Campaigns", font=FONT["h4"], text_color=C["txt"]
        ).pack(side="left")

        # Column headers
        cols_frame = ctk.CTkFrame(
            rc_frame, fg_color=C["input"], corner_radius=R["sm"], height=34
        )
        cols_frame.pack(fill="x", padx=PAD["lg"], pady=(0, PAD["xs"]))
        cols_frame.pack_propagate(False)
        for txt, w in [("Campaign Name", 240), ("Status", 100), ("Sent", 80),
                       ("Failed", 80), ("Total", 80), ("Date", 160)]:
            ctk.CTkLabel(
                cols_frame, text=txt, font=FONT["sm"], text_color=C["txt2"], width=w, anchor="w"
            ).pack(side="left", padx=PAD["sm"])

        # Row container (populated by refresh)
        self._rows_frame = ctk.CTkFrame(rc_frame, fg_color="transparent")
        self._rows_frame.pack(fill="x", padx=PAD["lg"], pady=(0, PAD["md"]))

        # Warning banner
        warn = ctk.CTkFrame(
            scroll, fg_color=C["warn_bg"], corner_radius=R["md"],
            border_width=1, border_color=C["warn"]
        )
        warn.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["xl"]))
        ctk.CTkLabel(
            warn,
            text="⚠  Use BulkWave Pro responsibly. Sending unsolicited bulk messages may "
                 "violate WhatsApp's Terms of Service and result in account restrictions.",
            font=FONT["sm"],
            text_color=C["warn"],
            wraplength=900,
            justify="left",
        ).pack(padx=PAD["lg"], pady=PAD["sm"])

    # ─── Data ─────────────────────────────────────────────────────────────────

    def refresh(self):
        """Reload stats and campaign list from the database."""
        if not self.db:
            return
        stats = self.db.get_overall_stats()
        updates = {
            "total_campaigns": str(stats["total_campaigns"]),
            "total_sent":      str(stats["total_sent"]),
            "total_failed":    str(stats["total_failed"]),
            "success_rate":    f"{stats['success_rate']}%",
        }
        for key, val in updates.items():
            if key in self._stat_labels:
                self._stat_labels[key].configure(text=val)

        # Rebuild campaign rows
        for w in self._rows_frame.winfo_children():
            w.destroy()

        campaigns = self.db.get_campaigns(limit=10)
        if not campaigns:
            ctk.CTkLabel(
                self._rows_frame,
                text="No campaigns yet. Start your first campaign in Bulk Sender!",
                font=FONT["body"],
                text_color=C["txt3"],
            ).pack(pady=PAD["lg"])
            return

        for c in campaigns:
            row = ctk.CTkFrame(self._rows_frame, fg_color="transparent", height=38)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            status_color = STATUS_COLOR.get(c["status"], C["txt2"])
            for txt, w in [
                (c["name"][:32], 240),
                (c["status"].title(), 100),
                (str(c["sent_count"]), 80),
                (str(c["failed_count"]), 80),
                (str(c["total_contacts"]), 80),
                ((c["created_at"] or "")[:16], 160),
            ]:
                color = status_color if txt == c["status"].title() else C["txt"]
                ctk.CTkLabel(
                    row, text=txt, font=FONT["sm"], text_color=color, width=w, anchor="w"
                ).pack(side="left", padx=PAD["sm"])

            # Separator
            ctk.CTkFrame(
                self._rows_frame, fg_color=C["border_s"], height=1, corner_radius=0
            ).pack(fill="x")

    # ─── Navigation helpers ───────────────────────────────────────────────────

    def _go_bulk(self):
        if self.on_navigate:
            self.on_navigate("bulk_sender")

    def _go_history(self):
        if self.on_navigate:
            self.on_navigate("history")

    def _go_logs(self):
        if self.on_navigate:
            self.on_navigate("logs")

    def _go_settings(self):
        if self.on_navigate:
            self.on_navigate("settings")
