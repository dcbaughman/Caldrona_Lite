"""Offline nearest-neighbor sprite preparation; never runs in the game loop."""
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

ROOT = Path(__file__).resolve().parent / "assets"


def prepare():
    sheet = pygame.image.load(str(ROOT / "battle" / "enemy-source.png"))
    cell_width = sheet.get_width() // 3
    for index, name in enumerate(("spider", "bat", "crawler")):
        cell = sheet.subsurface((index * cell_width, 0, cell_width, sheet.get_height()))
        bounds = cell.get_bounding_rect(min_alpha=128)
        crop = cell.subsurface(bounds)
        factor = min(30 / crop.get_width(), 30 / crop.get_height())
        sprite = pygame.transform.scale(crop, (max(1, round(crop.get_width()*factor)),
                                                max(1, round(crop.get_height()*factor))))
        # Binary alpha and a small color palette keep the native 32px art crisp.
        for y in range(sprite.get_height()):
            for x in range(sprite.get_width()):
                color = sprite.get_at((x, y))
                sprite.set_at((x, y), (*[min(255, round(v / 24) * 24) for v in color[:3]],
                                      255 if color.a >= 128 else 0))
        result = pygame.Surface((32, 32), pygame.SRCALPHA)
        result.blit(sprite, ((32-sprite.get_width())//2, (32-sprite.get_height())//2))
        pygame.image.save(result, str(ROOT / "battle" / f"{name}.png"))
    # Reuse the established Retri identity, at its original pixel density.
    atlas = pygame.image.load(str(ROOT / "retri-overworld.png"))
    pygame.image.save(atlas.subsurface((32, 32, 32, 32)), str(ROOT / "battle" / "retri.png"))


if __name__ == "__main__":
    prepare()
