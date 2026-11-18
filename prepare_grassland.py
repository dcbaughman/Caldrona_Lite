"""Convert the grassland concept art to native 16-pixel game tiles."""
from pathlib import Path
import pygame

root = Path(__file__).resolve().parent / 'assets' / 'grassland'
sheet = pygame.image.load(str(root / 'tiles-source.png'))
width, height = sheet.get_width() // 4, sheet.get_height() // 2
for row, names in enumerate((('grass0','grass1','grass2','grass3'),
                             ('path0','path1','cliff0','cliff1'))):
    for col, name in enumerate(names):
        cell = sheet.subsurface((col*width, row*height, width, height))
        pygame.image.save(pygame.transform.scale(cell, (16, 16)), str(root / (name + '.png')))
source = pygame.image.load(str(root / 'merren-source.png'))
crop = source.subsurface(source.get_bounding_rect(min_alpha=128))
scale = min(15 / crop.get_width(), 15 / crop.get_height())
sprite = pygame.transform.scale(crop, (max(1, round(crop.get_width()*scale)), max(1, round(crop.get_height()*scale))))
surface = pygame.Surface((16,16), pygame.SRCALPHA)
surface.blit(sprite, ((16-sprite.get_width())//2, 16-sprite.get_height()))
pygame.image.save(surface, str(root / 'merren.png'))
