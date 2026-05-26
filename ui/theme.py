"""
BulkWave Pro - Design System
Centralised colours, fonts, and spacing used across all UI modules.
"""

# ─── Colour Palette ───────────────────────────────────────────────────────────

C = {
    # Backgrounds
    "bg":           "#0D1117",   # main window
    "card":         "#161B22",   # card / panel background
    "card2":        "#1C2128",   # slightly elevated card
    "sidebar":      "#010409",   # left sidebar
    "input":        "#21262D",   # entry / textbox background
    "hover":        "#21262D",   # generic hover

    # WhatsApp green accent family
    "accent":       "#25D366",
    "accent_h":     "#1DAA56",   # hover
    "accent_d":     "#128C7E",   # dark
    "accent_m":     "#0D3B2E",   # muted / active sidebar bg

    # Text
    "txt":          "#E6EDF3",   # primary
    "txt2":         "#8B949E",   # secondary
    "txt3":         "#6E7681",   # muted / placeholder

    # Status colours
    "err":          "#F85149",
    "err_bg":       "#3D1614",
    "warn":         "#D29922",
    "warn_bg":      "#3D2F0B",
    "ok":           "#3FB950",
    "ok_bg":        "#0D2818",
    "info":         "#58A6FF",
    "info_bg":      "#0D1F3C",

    # Borders
    "border":       "#30363D",
    "border_a":     "#25D366",   # active / focused
    "border_s":     "#21262D",   # subtle
}

# ─── Fonts ────────────────────────────────────────────────────────────────────

FONT = {
    "h1":       ("Segoe UI", 26, "bold"),
    "h2":       ("Segoe UI", 20, "bold"),
    "h3":       ("Segoe UI", 16, "bold"),
    "h4":       ("Segoe UI", 13, "bold"),
    "body":     ("Segoe UI", 13),
    "sm":       ("Segoe UI", 11),
    "xs":       ("Segoe UI", 10),
    "mono":     ("Consolas", 12),
    "mono_sm":  ("Consolas", 11),
    "btn":      ("Segoe UI", 12, "bold"),
    "nav":      ("Segoe UI", 12, "bold"),
    "logo":     ("Segoe UI", 15, "bold"),
    "tag":      ("Segoe UI", 30, "bold"),
}

# ─── Spacing ──────────────────────────────────────────────────────────────────

PAD = {"xs": 4, "sm": 8, "md": 14, "lg": 20, "xl": 28}

# ─── Radii ────────────────────────────────────────────────────────────────────

R = {"sm": 6, "md": 10, "lg": 14, "xl": 20}

# ─── Status tag colours ───────────────────────────────────────────────────────

STATUS_COLOR = {
    "running":   C["info"],
    "completed": C["ok"],
    "stopped":   C["warn"],
    "failed":    C["err"],
    "pending":   C["txt2"],
    "paused":    C["warn"],
}

LOG_COLOR = {
    "SUCCESS": C["ok"],
    "ERROR":   C["err"],
    "WARNING": C["warn"],
    "INFO":    C["txt2"],
}
