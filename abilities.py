"""Starter abilities for Seer, Sollers, and Saint.

Learn levels, MP costs and power strings are the pack's suggestions. Nothing
here spends MP or changes HP. Battle plays the shipped frames and leaves the
numbers alone until Caleb defines the effects.

Gray versus blue is a file choice. ``attuned_stone`` defaults to ``"unattuned"``.
``"first_stone"`` selects the blue set. Saint Mend and Sanctuary have one
untinted gold set, and this module never recolors a pixel.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from classes import JOBS, current_job
from equipment import equipped_item

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "data" / "abilities_manifest.json"
FX_ROOT = ROOT / "assets" / "battle" / "fx"
STONES = ("unattuned", "first_stone")


@dataclass(frozen=True)
class AbilityVariant:
    key: str
    frames: tuple[Path, ...]
    ms_per_frame: tuple[int, ...]
    total_ms: int
    frame_w: int
    frame_h: int
    scale: int
    target_center: tuple[int, int]
    loop_frames: tuple[int, ...] | None
    json_path: Path


@dataclass(frozen=True)
class Ability:
    id: str
    name: str
    description: str
    job: str
    target: str
    learn_level: int
    mp_cost: int
    power: str
    kind: str
    attunement_tinted: bool
    variants: dict[str, AbilityVariant]


def _fx_path(pack_path: str) -> Path:
    relative = pack_path
    if relative.startswith("abilities/"):
        relative = relative[len("abilities/"):]
    return FX_ROOT / relative


def _load_variant(key: str, spec: dict) -> AbilityVariant:
    json_path = _fx_path(spec["json"])
    meta = json.loads(json_path.read_text(encoding="utf-8"))
    frames_dir = _fx_path(spec["frames_dir"])
    frames = tuple(sorted(path for path in frames_dir.glob("*.png")))
    expected = int(meta["frames"])
    if len(frames) != expected:
        raise RuntimeError(f"{frames_dir} has {len(frames)} frames, manifest json says {expected}")
    center = meta["target_center"]
    loop = meta.get("loop_frames")
    return AbilityVariant(
        key=key,
        frames=frames,
        ms_per_frame=tuple(int(ms) for ms in meta["ms_per_frame"]),
        total_ms=int(meta["total_ms"]),
        frame_w=int(meta["frame_w"]),
        frame_h=int(meta["frame_h"]),
        scale=int(meta.get("scale_in_battle") or 2),
        target_center=(int(center[0]), int(center[1])),
        loop_frames=None if not loop else tuple(int(frame) for frame in loop),
        json_path=json_path,
    )


def _load():
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_job: dict[str, tuple[Ability, ...]] = {}
    planned: dict[str, tuple[str, ...]] = {}
    for job in JOBS:
        block = data["classes"][job]
        abilities = []
        for row in block["abilities"]:
            anim = row["anim"]
            variants = {
                key: _load_variant(key, spec)
                for key, spec in row["effect_variants"].items()
            }
            abilities.append(Ability(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                job=job,
                target=row["target"],
                learn_level=int(row["learn_level_suggested"]),
                mp_cost=int(row["mp_cost_suggested"]),
                power=str(row["power_suggested"]),
                kind=anim.get("kind") or "",
                attunement_tinted=bool(anim.get("attunement_tinted")),
                variants=variants,
            ))
        by_job[job] = tuple(abilities)
        planned[job] = tuple(row["id"] for row in block.get("planned_not_drawn") or ())
    return by_job, planned


BY_JOB, PLANNED = _load()


def attuned_stone(member) -> str:
    """Gray until the first stone. Topaz is listed for later and has no files."""
    stone = member.get("attuned_stone") or "unattuned"
    if stone not in STONES:
        return "unattuned"
    return stone


def attune(member, stone="first_stone"):
    member["attuned_stone"] = stone if stone in STONES else "unattuned"


def class_abilities(job) -> tuple[Ability, ...]:
    return BY_JOB.get(job, ())


def find_ability(job, ability_id) -> Ability | None:
    for ability in class_abilities(job):
        if ability.id == ability_id:
            return ability
    return None


def learned_abilities(member) -> tuple[Ability, ...]:
    """Class abilities whose suggested level has been reached.

    Strike is not an ability the player sees. It is the weapon's attack
    animation. Undrawn abilities in ``PLANNED`` are never returned.
    """
    job = current_job(member)
    if job not in BY_JOB:
        return ()
    level = member.get("level", 1)
    return tuple(
        ability for ability in BY_JOB[job]
        if ability.id != "strike" and level >= ability.learn_level
    )


def remember(member):
    """Stamp the learned ids on the member so a future save keeps them."""
    member["abilities"] = [ability.id for ability in learned_abilities(member)]


def variant_for(ability: Ability, member) -> AbilityVariant:
    """Pick the shipped file set. Never builds a recolored image."""
    if "untinted" in ability.variants or not ability.attunement_tinted:
        return ability.variants["untinted"]
    stone = attuned_stone(member)
    if stone not in ability.variants:
        stone = "unattuned"
    return ability.variants[stone]


def frame_index(variant: AbilityVariant, elapsed_ms: float) -> int:
    """Frame for a clock reading, using each frame's own duration.

    ``loop_frames`` is stored for when a buff can hold the last frames.
    Effects are not applied yet, so playback walks the strip once.
    """
    if elapsed_ms <= 0:
        return 0
    elapsed = 0
    for index, duration in enumerate(variant.ms_per_frame):
        elapsed += duration
        if elapsed_ms < elapsed:
            return index
    return len(variant.frames) - 1


def frame_at(variant: AbilityVariant, elapsed_ms: float) -> Path:
    return variant.frames[frame_index(variant, elapsed_ms)]


def strike_variant(member) -> AbilityVariant | None:
    """Slash frames for Attack when the worn weapon asks for sword_strike.

    The player never picks Strike. Gray or blue follows ``attuned_stone``.
    """
    item = equipped_item(member, "weapon")
    if item is None or item.weapon is None or item.weapon.basic_attack_fx != "sword_strike":
        return None
    job = current_job(member) or "Saint"
    ability = find_ability(job, "strike")
    if ability is None:
        return None
    return variant_for(ability, member)
