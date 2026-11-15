"""Regenerate the 32×32 class battle sprites from the retained source art."""
from pathlib import Path
import pygame
from prepare_party_art import sprite


ROOT = Path(__file__).resolve().parent / "assets" / "battle"


def prepare():
    for character in ("retri", "temur"):
        reference = pygame.image.load(str(ROOT / f"{character}-v2.png"))
        bounds = reference.get_bounding_rect(min_alpha=128)
        for job in ("seer", "sollers", "saint"):
            name = f"{character}-{job}.png"
            sprite(ROOT / "classes" / "source" / name, ROOT / "classes" / name,
                   32, bounds.height, bounds.bottom)


if __name__ == "__main__":
    prepare()
