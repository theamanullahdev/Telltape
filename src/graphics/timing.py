"""Shared on-screen timing for animated graphic overlays. A graphic is a
short beat within a scene, not the scene's whole background, assembly
composites it over only the first GRAPHIC_ONSCREEN_SECONDS of the scene's
footage, then cuts back to plain b-roll for the remainder. Both the
graphics renderers and src/render/assemble.py import this so they agree.
"""

GRAPHIC_ONSCREEN_SECONDS = 8.0
REVEAL_SECONDS = 2.0
FPS = 30
