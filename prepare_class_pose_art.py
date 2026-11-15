"""Repaint approved native poses, preserving heads, silhouettes and baselines."""
from pathlib import Path
import pygame

ROOT = Path(__file__).resolve().parent / "assets" / "battle"
PALETTES = {
    "sollers": ((26, 21, 32), (68, 46, 79), (134, 100, 145)),
    "saint": ((78, 72, 82), (181, 174, 155), (248, 237, 205)),
    "seer": ((24, 23, 65), (60, 64, 146), (137, 143, 219)),
}

def repaint(source, job, pose):
    result = source.copy()
    bounds = source.get_bounding_rect(min_alpha=128)
    for y in range(source.get_height()):
        for x in range(source.get_width()):
            # Head, face, hair and beard are protected, including Temur's
            # exact standing-head pixels used by the approved Guard sprite.
            if pose == "guard" and (y < 13 or (y < 16 and 11 <= x < 17)):
                continue
            if pose == "fainted" and x < bounds.left + 12:
                continue
            r, g, b, a = source.get_at((x, y))
            if a < 128 or b <= r * 1.02 or b < g * .95 or max(r,g,b) < 30:
                continue
            tone = min(2., max(0., (max(r,g,b)-24)/80))
            low = min(1, int(tone))
            mix = tone-low
            colors = PALETTES[job]
            rgb = [round(colors[low][i]*(1-mix)+colors[low+1][i]*mix) for i in range(3)]
            result.set_at((x,y), (*rgb,a))
    return result

def prepare():
    for name in ("retri", "temur"):
        atlas = pygame.Surface((96,96), pygame.SRCALPHA)
        for row, job in enumerate(PALETTES):
            standing = pygame.image.load(str(ROOT / "classes" / f"{name}-{job}.png"))
            atlas.blit(standing, (0,row*32))
            for col, pose in enumerate(("guard", "fainted"),1):
                filename = f"{name}-guard.png" if pose == "guard" else ("retri-fainted-v2.png" if name == "retri" else "temur-fainted-v1.png")
                source = pygame.image.load(str(ROOT / filename))
                result = repaint(source,job,pose)
                assert result.get_bounding_rect(min_alpha=128) == source.get_bounding_rect(min_alpha=128)
                assert result.get_size() == (32,32)
                pygame.image.save(result, str(ROOT / "classes" / f"{name}-{job}-{pose}.png"))
                atlas.blit(result,(col*32,row*32))
        pygame.image.save(atlas, str(ROOT / "classes" / f"{name}-pose-sheet.png"))

if __name__ == "__main__":
    prepare()
