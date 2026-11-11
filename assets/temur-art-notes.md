# Temur artwork

Current world sprite: `temur-world-v4.png`, with the eyes and face reduced to the same native 16×16 pixel grid as the body. See `party-art-notes.md` for this follow-up. The battle sprite and portrait below remain current.

Generated with the built-in imagegen tool, using Retri's sprites as scale/style references and the supplied Temur sheet for his identity.

Runtime assets: `temur-world-v2.png`, `battle/temur-v2.png`, and `portraits/temur.png`. Both sprites use 32×32 cells with Retri's 26-pixel source height and foot baseline. World and battle images use exactly Retri's respective display scales. The original `temur.png` is retained. `prepare_temur_assets.py` performs offline nearest-neighbor preparation and binary-alpha cleanup. Sources are `temur-v2-source.png` and `portraits/temur-source.png`.

## Sprite prompt

Create TWO matching original game sprites of Temur for this exact existing retro JRPG. Input 1 and 2 are STYLE AND PIXEL PROPORTION references: Retri's actual tiny game sprites. Input 3 defines Temur's identity and clothes, NOT the rendering style. Output transparent sprite sheet with exactly TWO separated sprites, one in each half, uniform size. LEFT is front-facing overworld idle. RIGHT is side-facing LEFT battle-ready idle, arms bent, same angle as Retri side sprite. Temur is a mature dark-haired bearded mountain swordsman, hair tied back, indigo blue coat/tunic, small pale fur shoulder accents, brown belt and boots. Match Retri's silhouette proportions exactly: around 16 pixels wide and 24 pixels tall, head around 8x8 pixels, clear face, compact legs, not an oversized square chibi. Authentic hand-placed 16-bit pixel art, precise small clusters, limited about 16 colors, visible one pixel outline. Think original 16x24 sprites enlarged with nearest-neighbor, no extra detail, no anti-aliasing, no painterly gradients, no labels, no ground, no effects. Both full-body sprites same height with roomy transparent margins.

## Cleanup prompt

Precisely clean this two-character sprite sheet. Remove ALL stray glowing white and gray smoky blobs to the left of the right-hand character. Entire space outside the two character silhouettes must be completely transparent. Keep both character sprites, their colors and pixel shapes unchanged. Do not add effects. Only two clean opaque character silhouettes with empty transparent space.

## Portrait prompt

Create one square dialogue portrait of TEMUR for an existing retro JRPG. Input1 is the style reference: match its pixel-art head-and-shoulders character portraits with teal backgrounds, similar to original 16-bit RPG dialogue portraits, 128x128 native pixel look, deliberate pixel clusters, restrained shading, no soft gradients or photographic texture. Input2 is Temur's identity only: mature mountain wanderer, warm tan skin, long tied-back black hair, beard and mustache, indigo scarf, small cream fur shoulder accents. Strong calm slightly stern face, three-quarter view looking to the viewer's left. Face and hair fill most of the square; shoulders cropped at bottom, solid teal #007b80 background. One portrait only, no framing, no text, no sprite sheet.
