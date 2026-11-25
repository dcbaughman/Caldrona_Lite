import hashlib
import struct
import unittest
from pathlib import Path

from trail_lantern import PHASE_FRAMES, LanternTimeline, frame_paths, load_manifest, timeline_for

FOLDER = Path(__file__).parent / "assets" / "trail-lanterns"
LOOP = (110, 100, 90, 110, 120, 130)
LIGHT = (90, 90, 100, 110)


def png_size(path):
    data = path.read_bytes()[:24]
    return struct.unpack(">II", data[16:24])


class TrailLanternTimingTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest(FOLDER)

    def test_manifest_timings(self):
        self.assertEqual(tuple(self.manifest["loop"]["durations_ms"]), LOOP)
        self.assertEqual(tuple(self.manifest["lighting_transition"]["durations_ms"]), LIGHT)
        self.assertEqual(self.manifest["glow_offset"], [-8, -8])

    def test_unlit_has_no_animation(self):
        line = LanternTimeline(LOOP, LIGHT)
        self.assertEqual(line.frame(None), ("unlit", 0))
        self.assertEqual(line.frame(-1), ("unlit", 0))

    def test_one_shot_runs_each_frame_for_its_duration(self):
        line = LanternTimeline(LOOP, LIGHT)
        edges = (0, 90, 180, 280, 390)
        for i, (start, end) in enumerate(zip(edges, edges[1:])):
            self.assertEqual(line.frame(start), ("light", i))
            self.assertEqual(line.frame(end-1), ("light", i))
        self.assertEqual(line.frame(390), ("lit", 0))

    def test_loop_runs_each_frame_for_its_duration(self):
        line = LanternTimeline(LOOP, LIGHT)
        start = sum(LIGHT)
        edge = 0
        for i, ms in enumerate(LOOP):
            self.assertEqual(line.frame(start+edge), ("lit", i))
            self.assertEqual(line.frame(start+edge+ms-1), ("lit", i))
            edge += ms
        self.assertEqual(line.period, 660)

    def test_one_shot_never_replays(self):
        line = LanternTimeline(LOOP, LIGHT)
        seen = {line.frame(ms)[0] for ms in range(sum(LIGHT), 20000, 7)}
        self.assertEqual(seen, {"lit"})
        self.assertEqual(line.frame(sum(LIGHT)+660*5), ("lit", 0))

    def test_phase_offsets_lamps(self):
        lamps = [timeline_for(self.manifest, i) for i in range(2)]
        self.assertEqual(lamps[0].phase_ms, 0)
        self.assertEqual(lamps[1].phase_ms, sum(LOOP[:PHASE_FRAMES]))
        t = sum(LIGHT) + 1000       # both lit at the same moment
        self.assertNotEqual(lamps[0].frame(t), lamps[1].frame(t))
        in_step = sum(lamps[0].frame(t+ms)[1] == lamps[1].frame(t+ms)[1] for ms in range(0, 660, 5))
        self.assertLess(in_step, 30)    # of 132 samples

    def test_phase_never_jumps_mid_flame(self):
        late = timeline_for(self.manifest, 1)
        self.assertEqual(late.frame(sum(LIGHT)-1), ("light", 3))
        self.assertEqual(late.frame(sum(LIGHT)), ("lit", 0))      # resting frame
        self.assertEqual(late.frame(sum(LIGHT)+late.phase_ms-1), ("lit", 0))
        self.assertEqual(late.frame(sum(LIGHT)+late.phase_ms), ("lit", 0))
        self.assertEqual(late.frame(sum(LIGHT)+late.phase_ms+LOOP[0]), ("lit", 1))

    def test_art_files_exist_with_expected_sizes(self):
        unlit, light, light_glow, loop, loop_glow = frame_paths(self.manifest)
        self.assertEqual((len(light), len(loop)), (4, 6))
        for path in (unlit, *light, *loop):
            self.assertEqual(png_size(FOLDER / path), (16, 16), path)
        for path in (*light_glow, *loop_glow):
            self.assertEqual(png_size(FOLDER / path), (32, 32), path)

    def test_unlit_art_is_decorums_file(self):
        digest = hashlib.sha256((FOLDER / "frames" / "unlit.png").read_bytes()).hexdigest()
        self.assertEqual(digest, self.manifest["sha256"]["unlit"])


if __name__ == "__main__":
    unittest.main()
