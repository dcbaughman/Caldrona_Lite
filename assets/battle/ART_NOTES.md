# Cavern battle assets

The current enemy and closed chest art was generated with the built-in imagegen tool using: "Sprite sheet for classic 16-bit JRPG, transparent background, exactly four separate sprites in a horizontal row, equally spaced: ivory cave spider red eyes; purple cave bat; mossy stone armored beetle; closed wooden treasure chest with gold bands. Side view creatures facing right, chest front view. Crisp hand placed pixel art, limited palette, each looks designed on 32x32 pixel grid, dark outlines, no words, no shadows, no scenery. Consistent pixel size, inspired by classic 1990s RPG monster sprites, original designs." The open chest was generated using: "One open empty wooden treasure chest sprite, lid visibly raised with dark empty interior, brass gold bands, front-facing top-down slight angle for retro 16-bit JRPG game. Tiny 16x16 pixel art aesthetic, crisp limited palette dark outlines, isolated, transparent background, no text or shadow." Sources are `enemy-source-v2.png` and `chest-open-source.png`; the older preparation script and source document the previous generation.

Enemy source: generated with the built-in imagegen tool for this patch.
The requested sprite sheets informed the low-resolution presentation; the
existing Retri walking atlas supplies his battle-facing pose, preserving his
current identity. The spider reference informed the ivory/red color scheme.

Runtime assets: `spider.png`, `bat.png`, `crawler.png`, and `retri.png`, each a
transparent 32×32 PNG. `prepare_battle_assets.py` crops, downsamples with nearest
neighbor, reduces color precision, and makes binary alpha. The game loads only
these tiny prepared files, not the high-resolution source sheet. All are enlarged
3× at the base game resolution and use the existing proportional display scaler.

## Final generation prompt

Create a production sprite sheet for a very low resolution retro 16-bit JRPG.
Transparent background. Exactly THREE equal square cells in ONE horizontal row
with generous empty gutters, each isolated creature fully contained in its own
cell. Left: ivory cave spider, eight legs, scarlet eyes and red leg joints inspired
by a white cavern spider. Center: purple cave bat with ears and spread wings.
Right: squat moss green and ochre rock crawler beetle with segmented stone armor.
All enemies face RIGHT toward a hero on the right of a side-view battle. Uniform
pixel density and scale, each designed as if on a 32x32 pixel grid, very simple
chunky deliberate square pixel clusters, dark brown outlines, limited palette
around 8 colors each, flat pixel shading, no realistic texture, no gradients,
no text, no labels, no floor, no shadow. Classic early console battle sprites.
Each creature same approximate visual footprint. Output wide 3:1 sprite sheet.

## Shalehorn and Astral Hollow

Built-in imagegen used the supplied Caldrona Shalehorn Creature Archive as the design reference. The runtime images are `assets/battle/shalehorn.png`, `assets/quarry-door.png` and `assets/astral-stone.png`. The final generation prompt was:

One transparent retro SNES RPG asset sheet. Three isolated sprites, exactly three equal cells in a single horizontal row, generous margins. Left cell: Shalehorn based on reference, squat huge mole-boar with sweeping ivory tusks, slate armored plates and amber mineral cracks, three-quarter facing right, all feet visible. Center cell: front view of a timber-braced arched quarry door, iron latch and dark stone surround. Right cell: a low blue stone glowing with cyan crystalline veins, on a little dark rock base. Simple sharply separated pixel clusters, limited palettes and dark outlines. No letters, scenery or labels.

## Retri and Temur class battle outfits

The six class sprites were generated with the built-in image generator, using the
existing Retri battle art and the side-facing Temur reference. Each prompt asked
for the same character, left-facing idle stance, proportions, hair silhouette,
pixel density, and transparent background. Sollers wears dark teal rogue
leathers, Saint wears ivory and gold with blue accents, and Seer wears violet
and blue with cyan details. The generated originals are in `classes/source/`;
`prepare_class_battle_art.py` fits them to each character's existing 32×32
frame and baseline. Only the small files in `classes/` are loaded at runtime.
