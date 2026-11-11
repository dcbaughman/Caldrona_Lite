"""Offline preparation of Retri's updated art and Temur's readable world face."""
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

ASSETS = Path(__file__).resolve().parent / "assets"


def sprite(source_path, target_path, cell_size, height, baseline, sample_offset=0.0):
    source = pygame.image.load(str(source_path))
    crop = source.subsurface(source.get_bounding_rect(min_alpha=128))
    width = min(cell_size-2, round(crop.get_width() * height / crop.get_height()))
    image = pygame.transform.scale(crop, (width, height))
    for y in range(height):
        for x in range(width):
            if sample_offset:
                # A fixed sample phase keeps small face features on the same
                # native pixel grid without blending neighboring colors.
                sx = min(crop.get_width()-1, int((x+sample_offset)*crop.get_width()/width))
                sy = min(crop.get_height()-1, int((y+sample_offset)*crop.get_height()/height))
                color = crop.get_at((sx, sy))
            else:
                color = image.get_at((x, y))
            image.set_at((x, y), (color.r, color.g, color.b, 255 if color.a >= 128 else 0))
    result = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
    result.blit(image, ((cell_size-width)//2, baseline-height))
    pygame.image.save(result, str(target_path))


def prepare():
    reference = pygame.image.load(str(ASSETS / "battle" / "temur-v2.png"))
    bounds = reference.get_bounding_rect(min_alpha=128)
    sprite(ASSETS / "battle" / "retri-v2-source.png", ASSETS / "battle" / "retri-v2.png",
           32, bounds.height, bounds.bottom)
    # Prepare at the actual world resolution, so eye whites survive sampling.
    sprite(ASSETS / "temur-world-v4-source.png", ASSETS / "temur-world-v4.png",
           16, bounds.height//2, bounds.bottom//2, sample_offset=0.25)
    portrait = pygame.image.load(str(ASSETS / "portraits" / "retri-v2-source.png"))
    pygame.image.save(pygame.transform.scale(portrait, (128, 128)),
                      str(ASSETS / "portraits" / "retri-v2.png"))


if __name__ == "__main__":
    prepare()
