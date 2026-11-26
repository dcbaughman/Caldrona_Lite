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

from classes import NOKTAKORO, SENBRANKA, current_job
from equipment import item_for, worn_id
from research import Lesson, lessons_for, researched_ids

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "data" / "abilities_manifest.json"
FX_ROOT = ROOT / "assets" / "battle" / "fx"
STONES = ("unattuned", "first_stone", NOKTAKORO, SENBRANKA)


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
    travel_ms: int = 0
    contact_ms: int = 0
    tier: int = 1
    camera_shake: int = 0
    camera_pan: int = 0
    flash_color: str = "#b4c5dc"


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
        travel_ms=int(meta.get("travel_ms", 0)),
        contact_ms=int(meta.get("contact_ms", 0)),
        tier=int(meta.get("tier", 1)),
        camera_shake=int(meta.get("camera_shake", 0)),
        camera_pan=int(meta.get("camera_pan", 0)),
        flash_color=str(meta.get("flash_color", "#b4c5dc")),
    )


def _load():
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_job: dict[str, tuple[Ability, ...]] = {}
    planned: dict[str, tuple[str, ...]] = {}
    for job, block in data["classes"].items():
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
_APPROVED_MANIFEST = FX_ROOT / "approved_attacks" / "manifest.json"
EXTRA_FX = {
    name: {key: _load_variant(key, spec) for key, spec in variants.items()}
    for name, variants in json.loads(_APPROVED_MANIFEST.read_text(encoding="utf-8")).items()
}


_RESEARCH_MANIFEST = FX_ROOT / "research_moves" / "manifest.json"
RESEARCH_FX = {
    name: {key: _load_variant(key, spec) for key, spec in variants.items()}
    for name, variants in json.loads(_RESEARCH_MANIFEST.read_text(encoding="utf-8")).items()
} if _RESEARCH_MANIFEST.exists() else {}


def attuned_stone(member) -> str:
    """Gray until the first stone. Topaz is listed for later and has no files."""
    if current_job(member) in (None, "", "Unbound"):
        return "unattuned"
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


def learned_abilities(member) -> tuple[Ability | Lesson, ...]:
    """Return researched lessons, with level-based support for older callers."""
    if "researched" in member:
        known = researched_ids(member)
        return tuple(lesson for lesson in lessons_for(member) if lesson.id in known)
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


def _choose_variant(variants, member):
    if "untinted" in variants:
        return variants["untinted"]
    stone = attuned_stone(member)
    return variants.get(stone) or variants["unattuned"]


def variant_for(ability: Ability, member) -> AbilityVariant:
    """Pick the shipped file set. Never builds a recolored image."""
    return _choose_variant(ability.variants, member)


# Placeholder FX for kit moves with no drawn effect yet (movesets.md [N]/[P] moves).
# Each borrows an existing shipped frame set; nothing is recolored.
PLACEHOLDER_ART = {
    "seer_twist_of_fate": "seer_star_thread", "seer_prophecy": "seer_veil_sight",
    "tidecaller_rolling_tide": "unbound_first_aid", "tidecaller_undertow": "seer_gale",
    "tidecaller_rinse": "saint_litany", "tidecaller_swell": "unbound_steady_breath",
    "tidecaller_ebb": "sollers_stitch_up", "tidecaller_sea_mist": "seer_premonition",
    "tidecaller_spring_tide": "saint_restoration",
    "weaver_read_the_strand": "seer_glimpse", "weaver_onyx_lash": "seer_echo_glass",
    "weaver_weft_snare": "seer_mist_ray", "weaver_hush": "seer_mind_flare",
    "weaver_tether_pact": "seer_star_thread", "weaver_closing_verse": "seer_final_omen",
    "sollers_sleight_of_hand": "sollers_feint",
    "reliquary_mourners_veil": "unbound_cover", "reliquary_lid_shut": "unbound_hold_line",
    "reliquary_hollow_tithe": "seer_moon_pulse", "reliquary_grave_weight": "seer_destiny_mark",
    "reliquary_ashen_hush": "sollers_smokescreen", "reliquary_twin_reliquary": "seer_farseal",
    "saint_purify": "saint_litany", "saint_benediction": "saint_restoration",
}


def lesson_variant(lesson, member):
    if isinstance(lesson, Ability):
        return variant_for(lesson, member)
    shared_art = {"weaver_black_thread": "seer_mist_ray", "weaver_silkbolt": "seer_mist_ray",
                  "tidecaller_tide_dart": "seer_gale",
                  "reliquary_retribution": "seer_farseal",
                  "unbound_sleepers_ward": "unbound_cover",
                  **PLACEHOLDER_ART}.get(lesson.id, lesson.id)
    if shared_art in RESEARCH_FX:
        return _choose_variant(RESEARCH_FX[shared_art], member)
    if shared_art in EXTRA_FX:
        return _choose_variant(EXTRA_FX[shared_art], member)
    art = find_ability(current_job(member), lesson.id)
    return variant_for(art, member) if art is not None else None


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
    """Basic Attack artwork for the equipped weapon and active stone."""
    item = item_for(worn_id(member, "weapon"))
    if item is None:
        return None
    if item.basic_attack_fx in EXTRA_FX:
        return _choose_variant(EXTRA_FX[item.basic_attack_fx], member)
    if item.basic_attack_fx != "sword_strike":
        return None
    ability = find_ability(current_job(member), "strike") or find_ability("Saint", "strike")
    return variant_for(ability, member)
