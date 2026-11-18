"""Repaint approved native poses, preserving heads, silhouettes and baselines."""
from pathlib import Path
import pygame

ROOT = Path(__file__).resolve().parent / "assets" / "battle"
PALETTES = {
    "sollers": ((20, 21, 29), (45, 49, 59), (82, 78, 96)),
    "saint": ((70, 64, 74), (210, 195, 168), (248, 237, 205)),
    "seer": ((23, 15, 52), (65, 37, 112), (110, 152, 220)),
}

SEER_ACCENTS = {
    ("retri", "guard"): {(17, 15), (20, 21)},
    ("retri", "fainted"): {(22, 18), (28, 21)},
    ("temur", "guard"): {(15, 19), (18, 23)},
    ("temur", "fainted"): {(20, 17), (22, 20)},
}
SEER_ACCENT_COLORS = {"retri": (70, 215, 218), "temur": (124, 242, 246)}
SAINT_GOLD = {
    ("temur", "guard"): {(17, 19), (18, 23)},
    ("temur", "fainted"): {(20, 19), (19, 22)},
}
SOLLERS_TEMUR_SASH = {
    "guard": {(16, 22), (16, 23), (16, 24)},
    "fainted": {(18, 22), (18, 23)},
}

def repaint(source, job, pose, character=None):
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
            # Retri's Sollers outfit uses dark leather rather than the broad
            # gold panels in the unbound pose. Leave skin, hair and the belt.
            if (job == "sollers" and character == "retri" and y >= 19
                    and r >= 190 and g > r * .52 and g < r * .86 and b < 95):
                result.set_at((x, y), (round(r * .48), round(g * .48), round(b * .85), a))
                continue
            # Temur's unbound red sash becomes brown leather in Sollers;
            # the protected head region keeps his red hair tie unchanged.
            if (job == "sollers" and character == "temur"
                    and (x, y) in SOLLERS_TEMUR_SASH.get(pose, set())):
                result.set_at((x, y), (round(r * .50), round(g * .75), round(b * .78), a))
                continue
            if a < 128 or b <= r * 1.02 or b < g * .95 or max(r,g,b) < 30:
                continue
            # Seer's standing art has two bright cyan accents; keep their
            # counterpart on the cloth rather than recoloring head or skin.
            if job == "seer" and (x, y) in SEER_ACCENTS.get((character, pose), set()):
                result.set_at((x, y), (*SEER_ACCENT_COLORS[character], a))
                continue
            if job == "saint" and (x, y) in SAINT_GOLD.get((character, pose), set()):
                result.set_at((x, y), (245, 187, 80, a))
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
                result = repaint(source,job,pose,name)
                assert result.get_bounding_rect(min_alpha=128) == source.get_bounding_rect(min_alpha=128)
                assert result.get_size() == (32,32)
                pygame.image.save(result, str(ROOT / "classes" / f"{name}-{job}-{pose}.png"))
                atlas.blit(result,(col*32,row*32))
        pygame.image.save(atlas, str(ROOT / "classes" / f"{name}-pose-sheet.png"))

if __name__ == "__main__":
    prepare()
