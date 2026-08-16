"""Shared colors for dark map and chart cards."""

SURFACE = "#1a1a19"
INK_PRIMARY = "#ffffff"
INK_SECONDARY = "#c3c2b7"
INK_MUTED = "#898781"
GRIDLINE = "#2c2c2a"
BASELINE = "#383835"

# categorical, dark-surface steps, fixed order (never cycled/reassigned)
CAT_BLUE = "#3987e5"
CAT_ORANGE = "#d95926"
CAT_AQUA = "#199e70"
CAT_YELLOW = "#c98500"
CAT_MAGENTA = "#d55181"
CAT_GREEN = "#008300"
CAT_VIOLET = "#9085e9"
CAT_RED = "#e66767"

# emphasis form: one accent + de-emphasis gray, for "one series is the point"
ACCENT = CAT_RED
DEEMPHASIS = "#4a4a47"  # muted step between gridline and secondary ink

# diverging pair (route maps: new/good vs old/bad path)
DIVERGING_GOOD = CAT_BLUE
DIVERGING_BAD = CAT_RED
