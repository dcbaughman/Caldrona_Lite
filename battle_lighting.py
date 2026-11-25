"""Derive a muted battlefield from the original pixel art."""

import tkinter as tk


def muted_battlefield(canvas, backdrop, cache):
    key = str(backdrop)
    if key not in cache:
        width, height = backdrop.width(), backdrop.height()
        rgb = backdrop.tk.call(backdrop, "data", "-format", "ppm")[-width * height * 3:]
        ramp = [bytes((8 + i*54//100, 9 + i*56//100, 13 + i*60//100)) for i in range(256)]
        gray = b"".join(ramp[(54*r + 183*g + 19*b) >> 8] for r, g, b in zip(rgb[::3], rgb[1::3], rgb[2::3]))
        header = f"P6\n{width} {height}\n255\n".encode()
        cache[key] = tk.PhotoImage(master=canvas, data=header + gray, format="ppm")
    return cache[key]
