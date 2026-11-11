# Party art update

Generated with the built-in imagegen tool. Retri's character design sheet supplies his identity; Temur's approved sprite and portrait supply the shared rendering style.

## Runtime files

- `battle/retri-v2.png`: 32×32 cell; silhouette height 26 pixels, bottom at pixel 28, same as Temur. Uses the existing 2× battle scale.
- `portraits/retri-v2.png`: 128×128 portrait, used in Retri's dialogue, menu and victory screen.
- `temur-world-v4.png`: 16×16 world sprite with simple square eye whites and dark pupils. Face and body use the same base pixel grid, with no fine face details. Uses the existing 3× world scale. `temur-world-v4-preview.png` is an exact nearest-neighbor enlargement of this native asset.

Preparation is offline in `prepare_party_art.py`, using nearest-neighbor sampling and binary sprite alpha. Temur's fixed sample phase retains both eye whites at the native resolution. Older assets remain for reference. Source files are `battle/retri-v2-source.png`, `portraits/retri-v2-source.png`, and `temur-world-v4-source.png`.

## Retri battle sprite prompt

Use case: style-transfer. Create a single production battle sprite of RETRI, matching the style, head/body proportions, outline thickness and low pixel detail of the first reference (Temur's approved battle sprite). Second reference is Retri's character identity sheet: youthful blond hero, messy golden hair, royal navy-blue page coat with gold trim, off-white sleeves and trousers, brown gloves/belt/boots. One full-body sprite, side-facing LEFT, ready stance with bent arms, compact legs, same stance and scale as Temur. Design like a native 16-pixels-wide by 26-pixels-tall 16-bit JRPG sprite, enlarged nearest-neighbor; 8-pixel head, solid single-pixel outline, deliberately sparse square color clusters, limited palette, no realistic detail, no text, no additional poses, no effects, no ground or shadow. Transparent background with ample space around the silhouette. Retri must have a youthful face without beard; keep his distinctive blond hair and blue/gold clothing.

## Retri portrait prompt

Create a single square RETRI dialogue portrait for this exact retro JRPG. Input1 Temur portrait is the approved ART STYLE reference: match its pixel size, confident dark outline, crisp stepped pixel clusters, rich controlled 16-bit shading, shoulder framing, teal background and three-quarter face flow. Input2 is Retri's character design identity: youthful clean-shaven face, warm brown eyes, messy golden blond hair with long textured bangs, royal navy blue high-collared coat with gold trim, brown straps and off-white undershirt. A calm determined friendly young hero, not Temur, no beard or fur. Head and shoulders fill the frame, facing toward the viewer's right like the approved Temur portrait. Native 128x128 pixel-art look enlarged with nearest-neighbor, no watercolor or photoreal shading. Solid teal background, no text or frame, one portrait only.

## Temur eye edit prompt

The current base-pixel revision was edited using the built-in imagegen tool, then prepared on the literal 16×16 game grid. Final prompt:

Precise pixel cleanup of this exact Temur sprite. Keep the same transparent canvas, character silhouette, pose, blue clothes, hair, beard, fur, colors, and placement. ONLY simplify the face and eyes to the same COARSE BASE PIXEL GRID as the body. Each eye should be a few simple square pixels: a small ivory white pixel next to a dark pupil square under a dark eyebrow. Remove the tall smooth rectangular detailed eyes and the finely divided nose. No subpixel lines, no half-size squares, no gradients, no detailed irises or highlights. All eyes, nose and face edges must fall on the SAME square grid as the large clothing pixels. Authentic tiny low-resolution JRPG sprite, not an HD face pasted onto a blocky body. Preserve the original overall size and keep everything outside the silhouette transparent. No text or added marks.

Earlier eye edit prompt:

Edit ONLY the eyes and immediately surrounding face pixels of this front-facing Temur sprite. Preserve the exact canvas, transparent margins, silhouette, hair, blue clothing, fur, pose, native pixel grid and foot position. Replace the unreadable orange eye area with two clearly separated HIGH-CONTRAST JRPG eyes like Retri: bright ivory whites surrounding solid nearly black vertical pupils, a small tan nose between, dark eyebrows above. Lift just the fringe at the eye line if necessary so both eyes are clearly visible. This is tiny world-map pixel art that will be viewed at 16x16, so make each white eye area broad and obvious, not tiny shine dots, no blending, no antialiasing, no realism. Keep the short beard below the face. Full body front sprite, no text, no added objects, transparent background.
