"""Persisted display choices and nearest-neighbor scaling for Caldrona Lite."""
from __future__ import annotations

import json
from math import gcd
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

LOGICAL_WIDTH = 960
LOGICAL_HEIGHT = 540
WINDOW_SIZES = (
    (640, 480), (800, 600), (960, 720), (1024, 768),
    (1152, 864), (1280, 960), (1600, 1200), (1920, 1440),
)
DEFAULT_WINDOW = (960, 720)


@dataclass(frozen=True)
class DisplayConfig:
    mode: str = "windowed"
    width: int = DEFAULT_WINDOW[0]
    height: int = DEFAULT_WINDOW[1]


def available_sizes(screen_width: int, screen_height: int) -> tuple[tuple[int, int], ...]:
    # Leave room for a window border and the desktop taskbar.
    sizes = tuple(size for size in WINDOW_SIZES
                  if size[0] <= screen_width - 32 and size[1] <= screen_height - 72)
    return sizes or (WINDOW_SIZES[0],)


def load_display(path: Path, sizes: tuple[tuple[int, int], ...]) -> DisplayConfig:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        mode = data["mode"]
        size = (data["width"], data["height"])
        if mode in ("windowed", "fullscreen") and size in sizes:
            return DisplayConfig(mode, *size)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    preferred = DEFAULT_WINDOW if DEFAULT_WINDOW in sizes else sizes[-1]
    return DisplayConfig("windowed", *preferred)


def save_display(path: Path, config: DisplayConfig) -> None:
    payload = {"mode": config.mode, "width": config.width, "height": config.height}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def pixel_scale(outer_width: int, outer_height: int) -> int:
    """Return the largest 1/12 step that fits the internal 16:9 picture."""
    return max(1, min(outer_width * 12 // LOGICAL_WIDTH,
                      outer_height * 12 // LOGICAL_HEIGHT))


class ScaledCanvas(tk.Canvas):
    """Canvas accepting 960×540 logical coordinates, including pixel images."""

    def __init__(self, master: tk.Misc, scale_units: int, **kwargs: object) -> None:
        self.scale_units = scale_units
        self._images: dict[str, tk.PhotoImage] = {}
        kwargs["width"] = LOGICAL_WIDTH * scale_units // 12
        kwargs["height"] = LOGICAL_HEIGHT * scale_units // 12
        super().__init__(master, **kwargs)

    def logical_x(self, physical: float) -> float:
        return physical * 12 / self.scale_units

    def logical_y(self, physical: float) -> float:
        return physical * 12 / self.scale_units

    def _value(self, number: float) -> int:
        return round(number * self.scale_units / 12)

    def _image(self, source: tk.PhotoImage) -> tk.PhotoImage:
        if self.scale_units == 12:
            return source
        key = str(source)
        if key not in self._images:
            divisor = gcd(self.scale_units, 12)
            numerator, denominator = self.scale_units // divisor, 12 // divisor
            # Tk combines -subsample and -zoom by sampling FIRST, which loses
            # detail even for a 2x enlargement. Enlarge before sampling, using
            # the reduced fraction so integer fullscreen scales need no sampling.
            enlarged = source.zoom(numerator, numerator) if numerator != 1 else source
            resized = enlarged.subsample(denominator, denominator) if denominator != 1 else enlarged
            image = tk.PhotoImage(
                master=self.master,
                width=self._value(source.width()),
                height=self._value(source.height()),
            )
            image.tk.call(image, "copy", resized, "-from", 0, 0,
                          image.width(), image.height())
            self._images[key] = image
        return self._images[key]

    def delete(self, *items):
        result = super().delete(*items)
        if items == ("all",):
            self._images.clear()
        return result

    def _scale_options(self, options: dict[str, object]) -> dict[str, object]:
        scaled = options.copy()
        if "image" in scaled and isinstance(scaled["image"], tk.PhotoImage):
            scaled["image"] = self._image(scaled["image"])
        if "font" in scaled and isinstance(scaled["font"], tuple):
            family, size, *rest = scaled["font"]
            scaled["font"] = (family, max(8, self._value(size)), *rest)
        if "width" in scaled and isinstance(scaled["width"], (int, float)):
            scaled["width"] = max(1, self._value(scaled["width"]))
        return scaled

    def create_rectangle(self, x1, y1, x2, y2, **kwargs):
        return super().create_rectangle(*(self._value(v) for v in (x1, y1, x2, y2)),
                                        **self._scale_options(kwargs))

    def create_oval(self, x1, y1, x2, y2, **kwargs):
        return super().create_oval(*(self._value(v) for v in (x1, y1, x2, y2)),
                                   **self._scale_options(kwargs))

    def create_line(self, *coords, **kwargs):
        return super().create_line(*(self._value(v) for v in coords),
                                   **self._scale_options(kwargs))

    def create_text(self, x, y, **kwargs):
        return super().create_text(self._value(x), self._value(y),
                                   **self._scale_options(kwargs))

    def create_image(self, x, y, **kwargs):
        return super().create_image(self._value(x), self._value(y),
                                    **self._scale_options(kwargs))

    def coords(self, item, *coords):
        if coords:
            return super().coords(item, *(self._value(v) for v in coords))
        return super().coords(item)

    def move(self, item, dx, dy):
        return super().move(item, self._value(dx), self._value(dy))

    def itemconfigure(self, item, cnf=None, **kwargs):
        return super().itemconfigure(item, cnf, **self._scale_options(kwargs))
