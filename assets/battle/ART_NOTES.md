# Cavern battle assets

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
