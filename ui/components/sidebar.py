"""
BulkWave Pro - Sidebar Navigation Component
"""

import customtkinter as ctk
from ui.theme import C, FONT, PAD, R

# Navigation item definitions
NAV_ITEMS = [
    {"id": "dashboard",   "icon": "◉", "label": "Dashboard"},
    {"id": "bulk_sender", "icon": "◎", "label": "Bulk Sender"},
    {"id": "history",     "icon": "◷", "label": "History"},
    {"id": "settings",    "icon": "◈", "label": "Settings"},
    {"id": "logs",        "icon": "≡", "label": "Logs"},
]


class Sidebar(ctk.CTkFrame):
    """
    Fixed-width left sidebar with logo, navigation buttons, and a status indicator.
    on_navigate(page_id) is called when the user clicks a nav item.
    """

    SIDEBAR_W = 220

    def __init__(self, parent, on_navigate, **kwargs):
        super().__init__(
            parent,
            width=self.SIDEBAR_W,
            fg_color=C["sidebar"],
            corner_radius=0,
            **kwargs,
        )
        self.pack_propagate(False)
        self.on_navigate = on_navigate
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._current = ""

        self._build()

    # ─── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Logo area ────────────────────────────────────────────────────────
        logo_frame = ctk.CTkFrame(
            self, fg_color=C["accent_m"], corner_radius=R["lg"],
            height=80
        )
        logo_frame.pack(fill="x", padx=PAD["md"], pady=(PAD["lg"], PAD["xs"]))
        logo_frame.pack_propagate(False)

        # WB monogram
        ctk.CTkLabel(
            logo_frame,
            text="WB",
            font=FONT["tag"],
            text_color=C["accent"],
        ).pack(side="left", padx=PAD["md"])

        name_frame = ctk.CTkFrame(logo_frame, fg_color="transparent")
        name_frame.pack(side="left", fill="y", pady=PAD["sm"])
        ctk.CTkLabel(
            name_frame,
            text="BulkWave",
            font=FONT["logo"],
            text_color=C["txt"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            name_frame,
            text="Pro",
            font=("Segoe UI", 11),
            text_color=C["accent"],
        ).pack(anchor="w")

        # ── Divider ──────────────────────────────────────────────────────────
        ctk.CTkFrame(
            self, fg_color=C["border"], height=1, corner_radius=0
        ).pack(fill="x", padx=PAD["md"], pady=(PAD["sm"], PAD["xs"]))

        # ── Section label ────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="NAVIGATION",
            font=FONT["xs"],
            text_color=C["txt3"],
        ).pack(anchor="w", padx=PAD["lg"], pady=(PAD["sm"], 2))

        # ── Nav buttons ──────────────────────────────────────────────────────
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=PAD["sm"], pady=PAD["xs"])

        for item in NAV_ITEMS:
            btn = ctk.CTkButton(
                nav_frame,
                text=f"  {item['icon']}   {item['label']}",
                font=FONT["nav"],
                fg_color="transparent",
                hover_color=C["hover"],
                text_color=C["txt2"],
                anchor="w",
                height=42,
                corner_radius=R["md"],
                command=lambda i=item["id"]: self._navigate(i),
            )
            btn.pack(fill="x", pady=2)
            self._buttons[item["id"]] = btn

        # ── Spacer ───────────────────────────────────────────────────────────
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        # ── WhatsApp status dot ──────────────────────────────────────────────
        ctk.CTkFrame(
            self, fg_color=C["border"], height=1, corner_radius=0
        ).pack(fill="x", padx=PAD["md"], pady=PAD["xs"])

        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.pack(fill="x", padx=PAD["md"], pady=(4, 2))

        self._wa_dot = ctk.CTkLabel(
            status_row,
            text="●",
            font=FONT["body"],
            text_color=C["txt3"],
            width=16,
        )
        self._wa_dot.pack(side="left")
        self._wa_status_lbl = ctk.CTkLabel(
            status_row,
            text="WhatsApp: Offline",
            font=FONT["sm"],
            text_color=C["txt3"],
        )
        self._wa_status_lbl.pack(side="left", padx=4)

        # ── Version ──────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="v1.0.0  •  Smart Bulk WhatsApp",
            font=FONT["xs"],
            text_color=C["txt3"],
        ).pack(pady=(2, PAD["md"]))

    # ─── Navigation ───────────────────────────────────────────────────────────

    def _navigate(self, page_id: str):
        self._set_active(page_id)
        self.on_navigate(page_id)

    def _set_active(self, page_id: str):
        # Reset previous
        if self._current and self._current in self._buttons:
            self._buttons[self._current].configure(
                fg_color="transparent",
                text_color=C["txt2"],
            )
        # Activate new
        if page_id in self._buttons:
            self._buttons[page_id].configure(
                fg_color=C["accent_m"],
                text_color=C["accent"],
            )
        self._current = page_id

    def set_active(self, page_id: str):
        """Public method to programmatically set the active nav item."""
        self._set_active(page_id)

    # ─── WhatsApp status ──────────────────────────────────────────────────────

    def set_wa_status(self, connected: bool, text: str = ""):
        color = C["accent"] if connected else C["txt3"]
        label = text or ("Connected" if connected else "Offline")
        self._wa_dot.configure(text_color=color)
        self._wa_status_lbl.configure(
            text=f"WhatsApp: {label}", text_color=color
        )
