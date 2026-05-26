"""
BulkWave Pro
==============
Smart Bulk WhatsApp Automation

Entry point. Run this file to launch the application:
    python main.py
"""

import sys
import os

# Ensure the project root is on sys.path when running as a script or frozen EXE
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
from ui.app import App


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
