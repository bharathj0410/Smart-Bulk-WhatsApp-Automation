"""
BulkWave Pro - History Page
Displays all past campaigns with details and export options.
"""

import os
import tkinter.messagebox as mb
import tkinter.filedialog as fd

import customtkinter as ctk

from ui.theme import C, FONT, PAD, R, STATUS_COLOR
from utils.helpers import get_exports_dir
from utils.database import Database


class HistoryPage(ctk.CTkFrame):
    def __init__(self, parent, db: Database = None, **kwargs):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0, **kwargs)
        self.db = db
        self._selected_campaign: dict | None = None
        self._build()

    # ─── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=PAD["xl"], pady=(PAD["xl"], PAD["md"]))
        ctk.CTkLabel(hdr, text="History", font=FONT["h1"], text_color=C["txt"]).pack(side="left")
        ctk.CTkLabel(
            hdr, text="All past campaigns", font=FONT["sm"], text_color=C["txt2"]
        ).pack(side="left", padx=PAD["lg"])
        ctk.CTkButton(
            hdr,
            text="↻  Refresh",
            font=FONT["btn"],
            fg_color=C["input"],
            hover_color=C["hover"],
            text_color=C["txt2"],
            width=110, height=34,
            corner_radius=R["md"],
            command=self.refresh,
        ).pack(side="right")

        # Search bar
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=PAD["xl"], pady=(0, PAD["md"]))
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_filter())
        ctk.CTkEntry(
            search_frame,
            textvariable=self._search_var,
            placeholder_text="🔍  Search campaigns…",
            fg_color=C["input"],
            border_color=C["border"],
            text_color=C["txt"],
            font=FONT["body"],
            height=38,
        ).pack(fill="x")

        # Two-column layout: list + detail
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=PAD["xl"], pady=(0, PAD["xl"]))
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        # Campaign list
        list_card = ctk.CTkFrame(
            body, fg_color=C["card"], corner_radius=R["lg"],
            border_width=1, border_color=C["border"]
        )
        list_card.grid(row=0, column=0, sticky="nsew", padx=(0, PAD["sm"]))

        ctk.CTkLabel(
            list_card, text="Campaigns", font=FONT["h4"], text_color=C["txt"]
        ).pack(anchor="w", padx=PAD["lg"], pady=(PAD["lg"], PAD["sm"]))

        self._list_scroll = ctk.CTkScrollableFrame(
            list_card, fg_color="transparent", scrollbar_button_color=C["border"]
        )
        self._list_scroll.pack(fill="both", expand=True, padx=PAD["sm"], pady=(0, PAD["sm"]))

        # Detail panel
        detail_card = ctk.CTkFrame(
            body, fg_color=C["card"], corner_radius=R["lg"],
            border_width=1, border_color=C["border"]
        )
        detail_card.grid(row=0, column=1, sticky="nsew", padx=(PAD["sm"], 0))

        ctk.CTkLabel(
            detail_card, text="Campaign Details", font=FONT["h4"], text_color=C["txt"]
        ).pack(anchor="w", padx=PAD["lg"], pady=(PAD["lg"], PAD["sm"]))

        self._detail_frame = ctk.CTkScrollableFrame(
            detail_card, fg_color="transparent"
        )
        self._detail_frame.pack(fill="both", expand=True, padx=PAD["sm"], pady=(0, PAD["sm"]))

        self._placeholder_lbl = ctk.CTkLabel(
            self._detail_frame,
            text="Select a campaign to view details",
            font=FONT["body"],
            text_color=C["txt3"],
        )
        self._placeholder_lbl.pack(pady=PAD["xl"])

        self._all_campaigns: list[dict] = []
        self.refresh()

    # ─── Data ─────────────────────────────────────────────────────────────────

    def refresh(self):
        if not self.db:
            return
        self._all_campaigns = self.db.get_campaigns(limit=100)
        self._apply_filter()

    def _apply_filter(self):
        query = self._search_var.get().lower()
        filtered = [
            c for c in self._all_campaigns
            if query in (c.get("name") or "").lower() or not query
        ]
        self._render_list(filtered)

    def _render_list(self, campaigns: list[dict]):
        for w in self._list_scroll.winfo_children():
            w.destroy()

        if not campaigns:
            ctk.CTkLabel(
                self._list_scroll,
                text="No campaigns found",
                font=FONT["body"],
                text_color=C["txt3"],
            ).pack(pady=PAD["xl"])
            return

        for c in campaigns:
            self._add_campaign_row(c)

    def _add_campaign_row(self, campaign: dict):
        status_color = STATUS_COLOR.get(campaign.get("status", ""), C["txt2"])
        row = ctk.CTkFrame(
            self._list_scroll,
            fg_color=C["input"],
            corner_radius=R["md"],
            border_width=1,
            border_color=C["border_s"],
        )
        row.pack(fill="x", pady=3)
        row.bind("<Button-1>", lambda e, c=campaign: self._show_detail(c))

        name_lbl = ctk.CTkLabel(
            row,
            text=campaign.get("name", "Unnamed")[:30],
            font=FONT["h4"],
            text_color=C["txt"],
            anchor="w",
        )
        name_lbl.pack(anchor="w", padx=PAD["md"], pady=(PAD["sm"], 0))
        name_lbl.bind("<Button-1>", lambda e, c=campaign: self._show_detail(c))

        meta_row = ctk.CTkFrame(row, fg_color="transparent")
        meta_row.pack(fill="x", padx=PAD["md"], pady=(0, PAD["sm"]))
        meta_row.bind("<Button-1>", lambda e, c=campaign: self._show_detail(c))

        ctk.CTkLabel(
            meta_row,
            text=f"● {campaign.get('status', '').title()}",
            font=FONT["sm"],
            text_color=status_color,
        ).pack(side="left")

        date_str = (campaign.get("created_at") or "")[:10]
        ctk.CTkLabel(
            meta_row,
            text=f"  |  {date_str}  |  {campaign.get('total_contacts', 0)} contacts",
            font=FONT["sm"],
            text_color=C["txt3"],
        ).pack(side="left")

    def _show_detail(self, campaign: dict):
        self._selected_campaign = campaign
        for w in self._detail_frame.winfo_children():
            w.destroy()

        def _row(label: str, value: str, value_color=None):
            r = ctk.CTkFrame(self._detail_frame, fg_color="transparent")
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=label, font=FONT["sm"], text_color=C["txt3"], width=140, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=value, font=FONT["body"], text_color=value_color or C["txt"], anchor="w").pack(side="left")

        status_color = STATUS_COLOR.get(campaign.get("status", ""), C["txt2"])

        _row("Name:", campaign.get("name", "—"))
        _row("Status:", campaign.get("status", "—").title(), status_color)
        _row("Total Contacts:", str(campaign.get("total_contacts", 0)))
        _row("Sent:", str(campaign.get("sent_count", 0)), C["ok"])
        _row("Failed:", str(campaign.get("failed_count", 0)), C["err"])
        _row("Has Image:", "Yes" if campaign.get("has_image") else "No")
        _row("Created:", (campaign.get("created_at") or "—")[:19])
        _row("Completed:", (campaign.get("completed_at") or "—")[:19])

        # Message preview
        ctk.CTkLabel(
            self._detail_frame, text="Message:", font=FONT["sm"], text_color=C["txt3"]
        ).pack(anchor="w", pady=(PAD["sm"], 2))
        msg_box = ctk.CTkTextbox(
            self._detail_frame,
            fg_color=C["input"],
            text_color=C["txt"],
            font=FONT["mono_sm"],
            height=90,
            state="normal",
            corner_radius=R["sm"],
        )
        msg_box.insert("0.0", campaign.get("message") or "")
        msg_box.configure(state="disabled")
        msg_box.pack(fill="x", pady=(0, PAD["md"]))

        # Actions
        btn_row = ctk.CTkFrame(self._detail_frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, PAD["sm"]))

        ctk.CTkButton(
            btn_row,
            text="↗  Export Failed",
            font=FONT["btn"],
            fg_color=C["warn_bg"],
            hover_color=C["border"],
            text_color=C["warn"],
            height=34,
            corner_radius=R["md"],
            command=lambda: self._export_failed(campaign),
        ).pack(side="left", padx=(0, PAD["sm"]))

        ctk.CTkButton(
            btn_row,
            text="🗑  Delete",
            font=FONT["btn"],
            fg_color=C["err_bg"],
            hover_color=C["border"],
            text_color=C["err"],
            height=34,
            corner_radius=R["md"],
            command=lambda: self._delete_campaign(campaign),
        ).pack(side="left")

    def _export_failed(self, campaign: dict):
        if not self.db:
            return
        failed = self.db.get_failed_contacts(campaign["id"])
        if not failed:
            mb.showinfo("No Failed Contacts", "This campaign had no failed contacts.")
            return
        out_dir = get_exports_dir()
        path = fd.asksaveasfilename(
            initialdir=str(out_dir),
            initialfile=f"failed_{campaign['id']}.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        import pandas as pd
        pd.DataFrame(failed).to_excel(path, index=False)
        mb.showinfo("Exported", f"Saved to:\n{path}")

    def _delete_campaign(self, campaign: dict):
        if not mb.askyesno("Delete Campaign", f"Delete '{campaign['name']}'? This cannot be undone."):
            return
        if self.db:
            self.db.delete_campaign(campaign["id"])
        self.refresh()
        for w in self._detail_frame.winfo_children():
            w.destroy()
        self._placeholder_lbl = ctk.CTkLabel(
            self._detail_frame,
            text="Campaign deleted.",
            font=FONT["body"],
            text_color=C["txt3"],
        )
        self._placeholder_lbl.pack(pady=PAD["xl"])
