"""
BulkWave Pro - Main Application Window
Owns the sidebar and content area and wires all pages together.
"""

import customtkinter as ctk

from ui.theme import C, FONT
from ui.components.sidebar import Sidebar
from ui.pages.dashboard import DashboardPage
from ui.pages.bulk_sender import BulkSenderPage
from ui.pages.history import HistoryPage
from ui.pages.settings import SettingsPage
from ui.pages.logs import LogsPage
from utils.database import Database


class App(ctk.CTk):
    """Root window of BulkWave Pro."""

    MIN_W = 1100
    MIN_H = 720

    def __init__(self):
        super().__init__()

        self.db = Database()
        self.db.initialize()

        self._setup_window()
        self._build_layout()
        self._navigate("dashboard")

        # Graceful shutdown
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─── Window ───────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.title("BulkWave Pro — Smart Bulk WhatsApp Automation")
        self.geometry("1280x820")
        self.minsize(self.MIN_W, self.MIN_H)
        self.configure(fg_color=C["bg"])

        # Center on screen
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - 1280) // 2
        y = (sh - 820) // 2
        self.geometry(f"1280x820+{x}+{y}")

    # ─── Layout ───────────────────────────────────────────────────────────────

    def _build_layout(self):
        # Sidebar (left, fixed width)
        self.sidebar = Sidebar(self, on_navigate=self._navigate)
        self.sidebar.pack(side="left", fill="y")

        # Thin separator line between sidebar and content
        ctk.CTkFrame(self, fg_color=C["border"], width=1, corner_radius=0).pack(
            side="left", fill="y"
        )

        # Content area (right, expands)
        self._content = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self._content.pack(side="right", fill="both", expand=True)

        # Instantiate all pages (hidden by default)
        self._pages: dict[str, ctk.CTkFrame] = {
            "dashboard": DashboardPage(
                self._content, db=self.db, on_navigate=self._navigate
            ),
            "bulk_sender": BulkSenderPage(
                self._content, db=self.db, sidebar=self.sidebar
            ),
            "history": HistoryPage(self._content, db=self.db),
            "settings": SettingsPage(self._content, db=self.db),
            "logs": LogsPage(self._content, db=self.db),
        }
        self._current_page: str = ""

    # ─── Navigation ───────────────────────────────────────────────────────────

    def _navigate(self, page_id: str):
        if page_id == self._current_page:
            return

        # Hide current
        if self._current_page and self._current_page in self._pages:
            self._pages[self._current_page].pack_forget()

        # Show new
        if page_id in self._pages:
            page = self._pages[page_id]
            page.pack(fill="both", expand=True)

            # Refresh data-driven pages on every visit
            if hasattr(page, "refresh"):
                try:
                    page.refresh()
                except Exception:
                    pass

        self._current_page = page_id
        self.sidebar.set_active(page_id)

    # ─── Shutdown ─────────────────────────────────────────────────────────────

    def _on_close(self):
        """Stop any running campaign and close the browser before quitting."""
        try:
            bulk = self._pages.get("bulk_sender")
            if bulk and bulk.campaign_svc and bulk.campaign_svc.is_running:
                bulk.campaign_svc.stop()
            if bulk and bulk.wa_svc:
                bulk.wa_svc.close()
        except Exception:
            pass
        self.destroy()
