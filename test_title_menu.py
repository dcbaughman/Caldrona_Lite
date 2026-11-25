"""Title-menu behavior stays on PLAY, LOAD GAME, and SETTINGS."""
import json
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import Caldrona_Lite as game
from display_settings import DisplayConfig


def _texts(canvas):
    return [canvas.itemcget(item, "text") for item in canvas.find_all()
            if canvas.type(item) == "text"]


class TitleMenuTests(unittest.TestCase):
    def setUp(self):
        def no_controller(app):
            app.pygame = app.controller_api = None

        self._display = tempfile.TemporaryDirectory()
        self.display_path = Path(self._display.name) / "display_settings.json"
        patcher = patch.object(game, "DISPLAY_FILE", self.display_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._display.cleanup)
        with patch.object(tk.Tk, "mainloop"), patch.object(game.CaldronaLite, "_init_controller", no_controller), patch.object(game, "load_display", return_value=DisplayConfig()):
            self.app = game.CaldronaLite()
        self.addCleanup(self.app._close)
        self.app.root.withdraw()

    def test_menu_items_load_game_and_settings_are_unchanged(self):
        app = self.app
        self.assertEqual(app.menu_items, ("PLAY", "LOAD GAME", "SETTINGS"))
        labels = _texts(app.canvas)
        self.assertIn("NEW JOURNEY", labels)
        self.assertIn("CONTINUE", labels)
        self.assertIn("SETTINGS", labels)
        self.assertNotIn("PLAY", labels)
        self.assertNotIn("LOAD GAME", labels)

        app.keys.add("down")
        app.menu_nav_after = 0
        app._tick()
        self.assertEqual(app.selection, 1)
        self.assertEqual(app.screen, "menu")
        app.keys.clear()

        app._activate()
        self.assertEqual(app.screen, "save_slots")
        self.assertIn("CONTINUE JOURNEY", _texts(app.canvas))
        app._back()
        self.assertEqual(app.screen, "menu")

        app.selection = 2
        app._activate()
        self.assertEqual(app.screen, "settings")
        labels = _texts(app.canvas)
        self.assertIn("DISPLAY SETTINGS", labels)
        self.assertIn("MODE", labels)
        self.assertIn("WINDOW SIZE", labels)
        self.assertIn("APPLY", labels)
        self.assertIn("WINDOWED", labels)

        app._navigate_settings("right", time.monotonic())
        self.assertEqual(app.pending_display.mode, "fullscreen")
        self.assertIn("FULLSCREEN", _texts(app.canvas))
        self.assertIn("DESKTOP", _texts(app.canvas))
        app.settings_selection = 2
        app._activate()
        self.assertEqual(app.saved_display.mode, "fullscreen")
        self.assertIn("SAVED · RESTART GAME TO APPLY", _texts(app.canvas))
        saved = json.loads(self.display_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["mode"], "fullscreen")
        self.assertEqual((saved["width"], saved["height"]), (app.pending_display.width, app.pending_display.height))

        app._back()
        self.assertEqual(app.screen, "menu")
        self.assertIn("RESTART TO APPLY DISPLAY CHANGE", _texts(app.canvas))

        event = type("E", (), {"x": 480, "y": game._menu_row_y(0)})()
        app._click(event)
        self.assertEqual(app.screen, "game")
        self.assertEqual(app.root.title(), "Caldrona Lite · Cavern")

    def test_title_fades_out_before_the_cavern_theme_fades_in(self):
        app = self.app
        app.pygame = Mock(error=RuntimeError)
        music = app.pygame.mixer.music
        music.get_busy.return_value = True
        app._music_track = game.TITLE_MUSIC
        app._music_gain = game.MUSIC_VOLUME
        with patch.object(game.time, "monotonic", return_value=10):
            app._begin_gameplay_music()
        app._flush_pending_music(10.35)
        music.load.assert_not_called()
        self.assertAlmostEqual(app._music_gain, game.MUSIC_VOLUME / 2)
        app._flush_pending_music(10.71)
        music.load.assert_called_once_with(str(game.CAVERN_MUSIC))
        self.assertEqual(app._music_gain, 0)
        app._flush_pending_music(11.5)
        self.assertEqual(app._music_gain, game.MUSIC_VOLUME)

    def test_quick_area_changes_keep_the_latest_music_request(self):
        app = self.app
        app.pygame = Mock(error=RuntimeError)
        music = app.pygame.mixer.music
        music.get_busy.return_value = True
        app._music_track = game.CAVERN_MUSIC
        app._music_gain = game.MUSIC_VOLUME
        with patch.object(game.time, "monotonic", return_value=10):
            app._play_music(game.DEN_MUSIC)
        app._flush_pending_music(10.2)
        with patch.object(game.time, "monotonic", return_value=10.2):
            app._play_music(game.GOLDENLANDS_MUSIC)
        app._flush_pending_music(10.41)
        music.load.assert_called_once_with(str(game.GOLDENLANDS_MUSIC))

        app._flush_pending_music(11.2)
        with patch.object(game.time, "monotonic", return_value=12):
            app._play_music(game.DEN_MUSIC)
        app._flush_pending_music(12.2)
        with patch.object(game.time, "monotonic", return_value=12.2):
            app._play_music(game.GOLDENLANDS_MUSIC)
        app._flush_pending_music(12.5)
        self.assertEqual(app._music_gain, game.MUSIC_VOLUME)
        music.load.assert_called_once()


if __name__ == "__main__":
    unittest.main()
