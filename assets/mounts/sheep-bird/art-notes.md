# Sheep-Bird Mount — future asset

Generated with the built-in ImageGen tool from the user's Sheep-Chocobo Mount Sprite Sheet concept reference. Working asset ID: `sheep_bird_mount`; the final creature name is undecided.

The cream wool, ram horns, beak, bird legs, brown saddle, and red/gold saddle cloth carry over from the reference. The export uses 32×32 transparent cells, with a visible height of roughly 26 pixels beside the game's 16-pixel characters.

## Contents

- `source.png`: original generated transparent artwork; preserved intact.
- `idle-sheet.png`: 96×128 atlas; three columns, rows down/left/right/up.
- Direction folders: three native idle PNGs per direction.
- `manifest.json`: frame paths, durations, shared foot anchor, and draft saddle attachment points.
- `preview.png` and `idle-preview.gif`: enlarged previews against a dark background.

The asset is registered as disabled in `data/mounts.json`. It is not spawned or loaded by gameplay. Riding, walking/running sequences, rider layers, collision, acquisition, and controls are not implemented. Saddle attachment points require tuning when a rider is added.

`prepare_mount_assets.py` rebuilds exports from the original source with Pillow: it excludes sheet separators, thresholds edge alpha, resizes with nearest-neighbor, and aligns every frame to the same foot baseline. Source and exported alpha are preserved; there is no baked background.

## Exact generation prompt

Use case: stylized-concept. Asset: production transparent sprite sheet for a future rideable mount in a small 16-pixel-tile retro fantasy RPG. Input image is CONCEPT REFERENCE ONLY: preserve its cream sheep wool, curled brown ram horns, golden bird beak, expressive dark eyes, two sturdy golden bird legs, small woolly feather tail, brown leather saddle, and a simple muted red-and-gold saddle cloth. No rider. Create the SAME creature consistently in all views. Art direction: chunky deliberate low-resolution pixel art, simplified SNES overworld sprites, limited palette and clean pixel clusters, readable at 32x32 native pixels. Mount about 1.5 times the height of a 16px character. Avoid the highly detailed concept illustration style. Deliver ONE sheet in a precise THREE-COLUMN by FOUR-ROW rectangular grid, equal cells, generous transparent gutters, no text, labels, gridlines, scenery, floor, props, or drop shadows. ROW 1: three FRONT-facing idle breathing frames (looking down toward viewer). ROW 2: three LEFT-facing idle breathing frames. ROW 3: three RIGHT-facing idle breathing frames. ROW 4: three BACK-facing idle breathing frames (looking away/up). Each row has same stance and fixed foot baseline across all three frames; only a very subtle chest/wool breathing cycle and blink variation, no stepping, no scale drift. Full body entirely visible in every cell including horns and feet. All cells exactly equal size, identical overall scale between directions, feet grounded at consistent relative position in each cell. True transparent background outside sprites. Warm cream wool and amber accents, saddle must look ready to hold a future small rider but leave it EMPTY.
