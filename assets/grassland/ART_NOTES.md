# Sunrest cordon art

Korward's current overworld art is `assets/korward-overworld.png`. The built-in
ImageGen tool drafted the four-direction atlas from the party sprites and
Korward's portrait. The shipped sheet reduces each pose to the same native
16-pixel tile as Temur. The face, amber scarf, and shoulder armor were cleaned
up at that resolution. Rows are down, left, right, and up. The middle column
is idle and the outer columns are the two walking contact poses.

**Atlas prompt**

> Use case: stylized-concept. Asset: one original 4-row by 3-column retro JRPG overworld animation atlas for Korward, a weathered mountain road guard. First two supplied images are the existing party sprite atlases and are references for exact silhouette proportions, sprite cell scale and poses. Third image is Korward's portrait, the character design reference. Give Korward a broad uncovered head, swept charcoal hair with slate gray streaks, strong tan face, tiny beard, steel blue armor with an angular pauldron, a bright muted amber scarf and clasp, navy trousers and brown boots. Same bold, clean 16-bit pixel clusters and expressive 14-pixel-tall character as the party. Eyes and warm cheeks read even at one-cell scale. All sprite cells have the same head size and baseline. Four rows in this strict order: straight front, looking and walking left, looking and walking right, straight back. Three columns: first walking contact, idle feet beside each other, opposite walking contact. 12 sprites exactly, in a perfectly regular grid, equal gaps, no touching, alpha transparent, no cast shadow, no words or divider lines. Produce a master designed at the exact appearance of only 16x16 native pixels per cell, major features have clean whole blocks, no fine dithering or anti-aliasing, rendered at an integer enlargement for inspection.

## Original cordon art

The built-in ImageGen tool produced the portrait, front-facing sprite, three
enemies, and battle backdrop. The game files use native-size crops and reduced
palettes. Korward's side and back cels and the fence tiles were drawn on the
same 16-pixel grid.

| Asset | Generation prompt |
|---|---|
| Korward portrait | Generate original pixel-art JRPG dialogue portrait for Caldrona Lite. Medieval mountain road warden Korward, square head-and-shoulders three-quarter portrait, stern kind veteran, cropped dark gray hair, short beard, angular face, weathered slate-blue gambeson, gunmetal shoulder plate, muted amber scarf and clasp. Polished 16-bit console JRPG portrait; chunky deliberate pixel clusters, strong contours, hard-edged limited palette, no gradients, no text; subdued deep blue-gray flat backdrop. Fill square with head, shoulders trail at bottom. This asset is for a 128x128 pixel dialogue slot. |
| Korward field sprite | Original full body overworld sprite for medieval JRPG guard Korward. Single front-facing chibi figure centered on transparent background. Face with short gray-brown hair, gray short beard and warm tan skin, slate-blue cloth, gunmetal shoulders, muted amber scarf and clasp, dark leather boots, no props, hands down. Approximately a 12x16 logical pixel sprite with hard edges and flat tones, no text, no cast shadow. Tiny retro pixel art for 16px tile top-down game. |
| Cinder Hornet | Game asset design, ORIGINAL classic 16-bit RPG native low resolution pixel art battle sprite, single mountain hornet, broad striped amber and charcoal abdomen, raised hooked antennae, three visible angular legs, ochre translucent angular wings swept back, 3/4 pose facing screen-right towards heroes. Inspired by the attached hornet's silhouette. Palette muted honey, charcoal, chestnut, pale cream. Strong outline and clustered pixels, designed to reduce to 48x48. Tight clear sharp silhouette, centered with margin, transparent background, no shadow on ground, typography or props. |
| Ashmane Wolf | Game asset design, ORIGINAL classic retro 16-bit RPG native low resolution pixel art battle sprite, single Ashmane wolf, shaggy dark slate fur, thorned rust-orange mane tips, restrained russet accents at shoulder and ear, braced on four legs in a low three-quarter prowl aimed towards SCREEN RIGHT. Inspired by the attached creature's colors only. Deliberate hard edged pixel clusters, limited palette, strong readable outline, designed to reduce to 64x56. Centered with margin on genuinely transparent background, no base or text. |
| Torshield Ram | Game asset design, ORIGINAL classic retro 16-bit RPG low resolution pixel art battle sprite, single stocky Torshield Ram, curled sandstone horns, dark moss-green and charcoal rocky wool, broad shoulders and four short black hooves, braced facing SCREEN RIGHT in a three-quarter view. Clear silhouette distinct from a wolf and an insect. Limited olive, slate, ochre and off-white palette; chunky pixel clusters, hard edges, designed to reduce to 56x48. Transparent backdrop, full body centered with safe margin, no text or props. |
| Sunrest battle stage | Original retro 16-bit JRPG side-view battle stage with airy widescreen composition, aspect ratio 3:1, Sunrest grasslands mountain pass, green and ochre grass underfoot, cool slate geology and distant rolling western ridge in the upper third, pale cool sky, warm muted colors, crisp coarse pixel clusters, understated, no characters, no buildings, no text, foreground open flat grassy battlefield for overlaying sprites. Landscape. |
