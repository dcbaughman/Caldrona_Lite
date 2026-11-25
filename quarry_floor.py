"""Sample the existing quarry backdrop for Shalehorn's ground animation."""
from math import atan2, ceil, hypot, pi, sin


class QuarryFloor:
    FPS = 24
    SETTLED = FPS

    def __init__(self, backdrop, center):
        self.center = center
        self.width, self.height = backdrop.width(), backdrop.height()
        self.stride = self.width * 3
        self.header = f"P6\n{self.width} {self.height}\n255\n".encode()
        self.sources = {}
        self.ripple_distances = None
        self.select_backdrop(backdrop)

    def select_backdrop(self, backdrop):
        key = str(backdrop)
        if key not in self.sources:
            ppm = backdrop.tk.call(backdrop, "data", "-format", "ppm")
            self.sources[key] = ppm[-self.stride * self.height:]
        self.pixels = self.sources[key]

    def paint(self, image, move, frame):
        t = frame / self.FPS
        pixels = self.ripple(t) if move == "tremor" else self.burrow(t)
        image.configure(data=self.header + pixels, format="ppm")

    def actor_shift(self, x, feet, t):
        cx, cy = self.center
        distance = round(hypot(x - cx, (feet - cy) / .24))
        return -self._wave(t - .29, distance, feet)

    @staticmethod
    def _wave_height(age, distance):
        if age <= 0:
            return 0
        # Each pulse has a leading lift and a trough. Attenuate at the horizon.
        wave = 0.0
        for delay, amplitude in ((0, 21), (.12, 8)):
            elapsed = age - delay
            offset = (distance - elapsed * 1050) / 90
            if elapsed > 0 and -1 < offset < 1:
                wave += amplitude * sin(pi * offset) * (1 - abs(offset)) * max(0, 1 - distance / 1000)
        return wave

    @staticmethod
    def _floor_fade(row):
        return min(1, max(0, (row - 112) / 30), max(0, (319 - row) / 18))

    def _wave(self, age, distance, row):
        return 2 * round(self._wave_height(age, distance) * self._floor_fade(row) / 2)

    def ripple(self, t):
        age = t - .29
        if age <= 0 or age >= .66:
            return self.pixels
        x0, y0 = self.center
        strip = 6
        if self.ripple_distances is None:
            self.ripple_distances = tuple(
                (y, tuple(round(hypot(x + strip / 2 - x0, (y - y0) / .24))
                          for x in range(0, self.width, strip)))
                for y in range(112, self.height)
            )
        # The warp reads vertically shifted strips of the original floor. Sampling
        # in whole pixels keeps the existing texture sharp and fills the troughs.
        out = bytearray(self.pixels)
        front = age * 1050
        near, far = max(0, int(front - 216)), ceil(front + 90)
        heights = [self._wave_height(age, distance) for distance in range(near, far + 1)]
        offsets_by_fade = {}
        for y, distances in self.ripple_distances:
            start = y * self.stride
            fade = self._floor_fade(y)
            if fade not in offsets_by_fade:
                offsets_by_fade[fade] = [2 * round(wave * fade / 2) * self.stride for wave in heights]
            offsets = offsets_by_fade[fade]
            for i, distance in enumerate(distances):
                if not near <= distance <= far:
                    continue
                shift = offsets[distance - near]
                if shift:
                    dst = start + i * strip * 3
                    src = dst + shift
                    end = min(dst + strip * 3, start + self.stride)
                    out[dst:end] = self.pixels[src:src + end - dst]
        return out

    def burrow(self, t):
        progress = min(1, max(0, (t - .17) / .44))
        if not progress:
            return self.pixels
        cx, cy = self.center
        rx, ry = 62 * progress, 16 * progress
        out = bytearray(self.pixels)
        # An irregular inner lip deepens toward the center. Round sampling to
        # two-pixel blocks so the borrowed rocks keep the backdrop's pixel grid.
        for y in range(cy - 22, cy + 23, 2):
            for x in range(cx - 76, cx + 77, 2):
                nx, ny = (x + 1 - cx) / rx, (y + 1 - cy) / ry
                angle = atan2(ny, nx)
                edge = 1 + .075 * sin(7 * angle) + .05 * sin(13 * angle + 1)
                radius = hypot(nx, ny) / edge
                if radius >= 1:
                    continue
                if radius >= .78:
                    # Shift the neighboring shale across the broken rim.
                    sx = x + (8 if nx > 0 else -8)
                    sy = y + (4 if ny > 0 else -4)
                    shade = 100 - round((1 - radius) * (90 if ny > 0 else -105))
                else:
                    sx, sy = x, y + 4
                    shade = round(20 + 46 * (radius / .78) ** 3)
                    if ny > .25:
                        shade -= 7
                src = sy * self.stride + sx * 3
                pixel = bytes(min(255, value * shade // 100) for value in self.pixels[src:src+3])
                self._stamp(out, x, y, 2, 2, pixel)
        if progress >= .85:
            for dx, dy, width in ((-56, 8, 7), (-44, 13, 9), (-27, 16, 8),
                                  (20, 17, 9), (39, 13, 10), (55, 7, 7), (-35, -14, 8)):
                x, y = cx + dx, cy + dy
                sample = (y + 8) * self.stride + (x + 2) * 3
                color = self.pixels[sample:sample+3]
                self._stamp(out, x, y + 2, width, 2, bytes(value * 66 // 100 for value in color))
                self._stamp(out, x + 1, y, width - 2, 2,
                            bytes(min(255, value * 131 // 100) for value in color))
        if t < .81:
            for i in range(10):
                flight = (t - .19 - i * .024) / .36
                if 0 < flight < 1:
                    dx = (24 + 54 * flight) * (-1 if i % 2 else 1)
                    x = round(cx + dx)
                    y = round(cy - sin(flight * pi) * (16 + 5 * (i % 4)) + i % 3)
                    sample = (cy + 14 + i) * self.stride + (cx + 30 + i * 3) * 3
                    self._stamp(out, x, y, 2 + i % 4, 2, self.pixels[sample:sample+3])
        return out

    def _stamp(self, pixels, x, y, width, height, color):
        patch = color * width
        for row in range(y, y + height):
            start = row * self.stride + x * 3
            pixels[start:start + len(patch)] = patch

