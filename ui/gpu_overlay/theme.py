"""Design tokens for the Blender Copilot HUD. Every colour, spacing and type value lives here.

Principles (shibui / sade-tasarim): one calm graphite palette, ONE accent (glacier teal),
semantic green / amber / red only for status, generous even spacing, short labels.
No bpy import, so the values are unit-testable.
"""

# Accent: the only hue that decorates. Used for the primary action, the caret and active states.
ACCENT = (0.45, 0.76, 0.82, 1.0)
ACCENT_HOVER = (0.56, 0.83, 0.89, 1.0)
ACCENT_INK = (0.04, 0.08, 0.09, 1.0)  # text on an accent fill

# Surfaces, from the bar outwards.
SURFACE = (0.090, 0.098, 0.113, 0.96)   # bar and drawers
SURFACE_2 = (0.070, 0.077, 0.092, 0.96)  # inset cards and input boxes
BORDER = (0.19, 0.21, 0.24, 0.9)
CTRL = (0.150, 0.165, 0.190, 1.0)        # buttons at rest
CTRL_HOVER = (0.205, 0.228, 0.262, 1.0)

# Text.
TEXT = (0.93, 0.94, 0.96, 1.0)
TEXT_DIM = (0.67, 0.70, 0.75, 1.0)
TEXT_FAINT = (0.47, 0.50, 0.55, 1.0)

# Status only (never decoration).
OK = (0.45, 0.80, 0.55, 1.0)
WARN = (0.93, 0.72, 0.35, 1.0)
DANGER = (0.90, 0.42, 0.42, 1.0)
DANGER_FILL = (0.30, 0.12, 0.13, 0.95)
OK_FILL = (0.11, 0.25, 0.16, 0.95)

# Spacing scale (px): 4 / 8 / 16 / 24 only.
SPACE_1, SPACE_2, SPACE_3, SPACE_4 = 4.0, 8.0, 16.0, 24.0
PAD = SPACE_3
GAP = SPACE_2

# Corner radii.
RADIUS_BAR = 18.0
RADIUS_CARD = 16.0
RADIUS_CTRL = 8.0
RADIUS_PILL = 6.0

# Type scale (px): title / body / small.
T_INPUT = 14
T_TITLE = 12
T_BODY = 11
T_SMALL = 10
