"""Pixel-level regression for display scaling (requires a Tk display)."""
import tkinter as tk
import unittest

from display_settings import ScaledCanvas


class DisplayScalingTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.source = tk.PhotoImage(master=self.root, width=24, height=24)
        for y in range(24):
            for x in range(24):
                self.source.put("#%02x%02x%02x" % (x * 10, y * 10, (x + y) * 5), (x, y))
                if (x + y) % 7 == 0:
                    self.source.transparency_set(x, y, True)

    def tearDown(self):
        self.root.destroy()

    def test_scaling_preserves_pixel_samples_and_transparency(self):
        # Includes all windowed scale factors, 1366x768, and 1080p/1440p fullscreen.
        for units in (8, 10, 12, 14, 16, 17, 20, 24, 32):
            with self.subTest(scale_units=units):
                canvas = ScaledCanvas(self.root, units)
                image = canvas._image(self.source)
                self.assertEqual((image.width(), image.height()), (2 * units, 2 * units))
                for y in range(image.height()):
                    for x in range(image.width()):
                        sx, sy = x * 12 // units, y * 12 // units
                        transparent = self.source.transparency_get(sx, sy)
                        self.assertEqual(image.transparency_get(x, y), transparent)
                        if not transparent:
                            self.assertEqual(image.get(x, y), self.source.get(sx, sy))
                self.assertIs(canvas._image(self.source), image)
                canvas.destroy()

    def test_refresh_updates_the_displayed_image_after_its_pixels_change(self):
        canvas = ScaledCanvas(self.root, 24)
        item = canvas.create_image(0, 0, anchor="nw", image=self.source)
        display = canvas._image(self.source)
        self.assertTrue(display.transparency_get(0, 0))
        self.source.put("#afa766", (0, 0))
        canvas.refresh_image(self.source)
        self.assertEqual(display.get(1, 1), (175, 167, 102))
        self.assertEqual(canvas.itemcget(item, "image"), str(display))
        self.source.transparency_set(0, 0, True)
        canvas.refresh_image(self.source)
        self.assertTrue(display.transparency_get(1, 1))


if __name__ == "__main__":
    unittest.main()
