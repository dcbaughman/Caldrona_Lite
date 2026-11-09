"""Prepare the generated Temur art once, using Retri's native sprite scale."""
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

ASSETS = Path(__file__).resolve().parent / "assets"


def prepare():
    source = pygame.image.load(str(ASSETS / "temur-v2-source.png"))
    width = source.get_width() // 2
    retri = pygame.image.load(str(ASSETS / "battle" / "retri.png"))
    reference = retri.get_bounding_rect(min_alpha=128)
    for index, path in enumerate((ASSETS / "temur-world-v2.png", ASSETS / "battle" / "temur-v2.png")):
        cell = source.subsurface((index * width, 0, width, source.get_height()))
        bounds = cell.get_bounding_rect(min_alpha=128)
        crop = cell.subsurface(bounds)
        height = reference.height
        size = (min(20, round(crop.get_width() * height / crop.get_height())), height)
        sprite = pygame.transform.scale(crop, size)
        # Transparent pixels remain empty; visible pixels use a solid pixel edge.
        for y in range(sprite.get_height()):
            for x in range(sprite.get_width()):
                color = sprite.get_at((x, y))
                sprite.set_at((x, y), (color.r, color.g, color.b, 255 if color.a >= 128 else 0))
        result = pygame.Surface(retri.get_size(), pygame.SRCALPHA)
        result.blit(sprite, ((result.get_width() - size[0]) // 2, reference.bottom - height))
        pygame.image.save(result, str(path))
    portrait = pygame.image.load(str(ASSETS / "portraits" / "temur-source.png"))
    pygame.image.save(pygame.transform.scale(portrait, (128, 128)),
                      str(ASSETS / "portraits" / "temur.png"))


if __name__ == "__main__":
    prepare()
