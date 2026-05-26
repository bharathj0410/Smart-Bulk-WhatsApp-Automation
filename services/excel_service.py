"""
BulkWave Pro - Excel / CSV Service
Handles loading, validating, and processing contact files.
"""

import pandas as pd
from utils.validators import validate_phone_number, sanitize_phone


class ExcelService:
    """Loads an Excel/CSV file and exposes contact data for the campaign."""

    def __init__(self):
        self.df: pd.DataFrame | None = None
        self.file_path: str = ""
        self.columns: list[str] = []

    # ─── Loading ──────────────────────────────────────────────────────────────

    def load_file(self, path: str) -> tuple[bool, str]:
        """Load an Excel (.xlsx/.xls) or CSV file. Returns (success, error_msg)."""
        try:
            lower = path.lower()
            if lower.endswith(".csv"):
                self.df = pd.read_csv(path, dtype=str, keep_default_na=False)
            else:
                self.df = pd.read_excel(path, dtype=str, keep_default_na=False)

            # Strip whitespace from all string cells
            self.df = self.df.map(lambda x: x.strip() if isinstance(x, str) else x)

            self.file_path = path
            self.columns = list(self.df.columns)
            return True, ""
        except Exception as e:
            self.df = None
            self.columns = []
            return False, str(e)

    # ─── Preview / Validation ─────────────────────────────────────────────────

    def get_preview(
        self,
        phone_col: str,
        name_col: str | None,
        start_row: int,
        country_code: str = "",
    ) -> dict:
        """
        Validate contacts starting from start_row (1-indexed, inclusive).
        Returns a summary dict with lists of valid/invalid contacts.
        """
        if self.df is None:
            return {"total": 0, "valid": [], "invalid": [], "error": "No file loaded"}

        # Slice from start_row (convert to 0-based index)
        start_idx = max(0, start_row - 1)
        subset = self.df.iloc[start_idx:].copy()

        if phone_col not in subset.columns:
            return {
                "total": 0,
                "valid": [],
                "invalid": [],
                "error": f"Column '{phone_col}' not found",
            }

        valid_contacts = []
        invalid_contacts = []

        for idx, row in subset.iterrows():
            raw_phone = str(row.get(phone_col, "")).strip()
            name = str(row.get(name_col, "")).strip() if name_col and name_col in row else ""

            is_valid, normalized = validate_phone_number(raw_phone, country_code)
            contact = {
                "raw_phone": raw_phone,
                "phone": normalized,
                "name": name,
                "row": idx + 2,  # human-readable row number (1-indexed + header)
            }

            if is_valid:
                valid_contacts.append(contact)
            else:
                invalid_contacts.append(contact)

        return {
            "total": len(valid_contacts) + len(invalid_contacts),
            "valid": valid_contacts,
            "invalid": invalid_contacts,
            "error": "",
        }

    # ─── Column helpers ───────────────────────────────────────────────────────

    def get_columns(self) -> list[str]:
        return self.columns

    def auto_detect_phone_column(self) -> str | None:
        """Heuristically find the phone number column."""
        keywords = ["phone", "mobile", "number", "contact", "tel", "whatsapp", "ph", "cell"]
        for col in self.columns:
            if any(kw in col.lower() for kw in keywords):
                return col
        return self.columns[0] if self.columns else None

    def auto_detect_name_column(self) -> str | None:
        """Heuristically find the name column."""
        keywords = ["name", "customer", "client", "person", "full", "first"]
        for col in self.columns:
            if any(kw in col.lower() for kw in keywords):
                return col
        return None

    def get_total_rows(self) -> int:
        return len(self.df) if self.df is not None else 0

    # ─── Export ───────────────────────────────────────────────────────────────

    def export_contacts_to_excel(self, contacts: list[dict], output_path: str) -> bool:
        """Export a list of contact dicts to an Excel file."""
        try:
            df = pd.DataFrame(contacts)
            df.to_excel(output_path, index=False)
            return True
        except Exception:
            return False
