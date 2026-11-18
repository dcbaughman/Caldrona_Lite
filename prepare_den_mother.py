"""Prepare the approved Den Mother artwork at the game's native pixel density."""
from pathlib import Path
import pygame

ROOT = Path(__file__).resolve().parent / "assets" / "battle"
source = pygame.image.load(str(ROOT / "den-mother-source.png"))
bounds = source.get_bounding_rect(min_alpha=128)
crop = source.subsurface(bounds)
factor = min(90 / crop.get_width(), 90 / crop.get_height())
sprite = pygame.transform.scale(crop, (round(crop.get_width() * factor),
                                       round(crop.get_height() * factor)))
for y in range(sprite.get_height()):
    for x in range(sprite.get_width()):
        color = sprite.get_at((x, y))
        sprite.set_at((x, y), (*[min(255, round(v / 24) * 24) for v in color[:3]],
                              255 if color.a >= 128 else 0))
result = pygame.Surface((96, 96), pygame.SRCALPHA)
result.blit(sprite, ((96 - sprite.get_width()) // 2, (96 - sprite.get_height()) // 2))
result = pygame.transform.flip(result, True, False)
pygame.image.save(result, str(ROOT / "den-mother.png"))
