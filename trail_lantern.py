"""Animated trail lanterns: frame timing for the opening trail's lamps.

The timing and file lists come from assets/trail-lanterns/manifest.json.  The
sprites are 16x16 and the glow overlays 32x32, drawn under the sprite at (-8,-8)
in sprite pixels.  This module has no Tk code so the timing can be tested alone.
"""
import json
from bisect import bisect_right
from itertools import accumulate
from pathlib import Path

PHASE_FRAMES = 3     # each lamp's loop starts this many frames later than the one before


class LanternTimeline:
    def __init__(self, loop_ms, light_ms, phase_ms=0):
        self.loop_ms, self.light_ms = tuple(loop_ms), tuple(light_ms)
        self.phase_ms = phase_ms
        self._light_ends = tuple(accumulate(self.light_ms))
        self._loop_ends = tuple(accumulate(self.loop_ms))
        self.light_total = self._light_ends[-1]
        self.period = self._loop_ends[-1]

    def frame(self, elapsed_ms):
        """('unlit', 0) before the lamp is lit; then ('light', i) once; then ('lit', i) forever.

        The loop starts at lit_00 after the one-shot, and holds that resting frame for
        phase_ms first, so a phased lamp never jumps mid-flame."""
        if elapsed_ms is None or elapsed_ms < 0:
            return ("unlit", 0)
        if elapsed_ms < self.light_total:
            return ("light", bisect_right(self._light_ends, elapsed_ms))
        loop_time = elapsed_ms - self.light_total - self.phase_ms
        if loop_time < 0:
            return ("lit", 0)
        return ("lit", bisect_right(self._loop_ends, loop_time % self.period))


def load_manifest(folder):
    return json.loads((Path(folder) / "manifest.json").read_text(encoding="utf-8"))


def timeline_for(manifest, index):
    """Timeline for the index-th lamp; lamp i's loop trails lamp 0 by i*PHASE_FRAMES frames."""
    loop = manifest["loop"]["durations_ms"]
    phase = sum(loop[:PHASE_FRAMES]) * index % sum(loop)
    return LanternTimeline(loop, manifest["lighting_transition"]["durations_ms"], phase)


def frame_paths(manifest):
    """(unlit, light sprites, light glows, loop sprites, loop glows) paths relative to the folder."""
    files = manifest["files"]
    glow = lambda path: path.replace(".png", "_glow.png")
    return (files["unlit"], files["transition_sprites"], [glow(p) for p in files["transition_sprites"]],
            files["loop_sprites"], files["loop_glows"])
