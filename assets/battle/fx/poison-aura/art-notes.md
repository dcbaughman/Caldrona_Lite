# Poison aura overlay

Generated with the built-in ImageGen tool using the user's Pixel Hero Poison Progression Animation.gif as a visual reference. The reference was inspected across its frames: purple fumes, rising green bubbles, and a brief skull puff.

The source is poison effects only, with no baked character. `prepare_poison_fx.py` exports eight transparent 48×52 native frames with one shared crop/foot baseline. Low-alpha background artifacts are discarded and visible fumes retain partial transparency. Runtime uses cached Tk images and persistent overlay items, follows camera offsets, and scales larger monsters.

Frames 0–3 play once at impact (100 ms each); 4–7 loop (180 ms each) until the actual Poison condition is cured. Carry-in Poison resumes the loop in subsequent battles. Cure, KO, or battle exit clears the visual; only cure removes the permanent underlying condition. Frozen can overlay the poison effect independently.

`source.png` is the intact generated artwork. `sheet.png` is the native atlas; `preview.gif` composites the export over Retri for inspection.

## Exact generation prompt

Use case: stylized-concept. Asset: ICE-FREE POISON ONLY transparent pixel-art battle overlay sprite sheet for a small retro RPG. Reference: the user's attached poisoned adventurer animation, its purple toxic fumes swirling around the feet, bright green bubbles rising beside the body, and a brief poison skull puff on application. Do NOT draw any character, creature, body, clothing, scenery, floor, border or text. The existing game character will remain underneath the overlay. Deliver exactly EIGHT equal cells in a FOUR-COLUMN by TWO-ROW grid, fixed common center/foot baseline and consistent scale. Frames 0-3 are application: small purple/green ground wisps appear, bubbles rise, a SMALL faint green skull-shaped puff briefly appears near the shoulder in frame 3 only. Frames 4-7 are a seamless restrained idle loop: thin curling purple fumes low around the feet, two or three small green bubbles rise along the sides and fade; NO skull in the loop. Leave the entire central body/face area empty/transparent, with wisps along the sides and below only. Minimal effect, small particles, no gigantic cloud or persistent overhead icon, keep the RPG battlefield clean. Crisp chunky pixel art readable at 44x52 native pixels, limited muted purple and moss/lime green palette, hard pixel edges, no blur or elaborate glows. True transparent background and gutters, no dividers or labels. This is a status effect overlay, not a character sprite sheet.
