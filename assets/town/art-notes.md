# Town tileset (Windehus)

`prepare_town_tiles.py` draws all of this from code on the game's 16 px grid. It is original art, lit from the top left, with dark ink only on the shadow side. Rebuild it with:

```
python prepare_town_tiles.py
```

The grass is not redrawn. Towns use the overworld's own `assets/grassland/meadow0-5.png`, picked the same way as the fields around Sunrest (`windehus.grass_index`), so a town sits in the same meadow.

## Paving: `ground-<paving>.png`

There are four pavings: `cobble` (round field cobbles), `flag` (the market square), `brick` (basket-weave brick) and `dirt` (packed road dirt).

The square is a few steps darker than the houses, so the buildings carry the eye. Its slabs come in mixed sizes, laid in no fixed rows, and no slab is left flat:
- each has its own grain (specked, banded or mottled), a lit top-left bevel, a dark lower edge and a footworn middle;
- pits catch the light on their lower lip, and some slabs have chipped corners, a fleck of lichen or a hairline crack;
- the grout crumbles in patches into open gaps, loose grit and the odd weed, chipping the slab edges beside it;
- a few long cracks run across several stones, and moss creeps into the joints and corners nearest the grass.

Two lifted-slab decals, `square-gap-0` and `square-gap-1`, show where slabs are gone and the clay bed shows through: dried and cracked, with pebbles, a weed, a broken shard, ragged slab edges, and the shadow of the slab behind the hole. Each decal is drawn for the texture under its exact tiles, so it only fits where `windehus.SQUARE_GAPS` puts it.

Each sheet is 256 × 256 px:

- **Columns** are the corner mask, 0–15. Bit 1 = top-left corner paved, 2 = top-right, 4 = bottom-left, 8 = bottom-right. Mask 15 is a fully paved tile.
- **Rows** are the sub-tile, 0–15, of a seamless 64 × 64 texture. A tile at (x, y) uses row `(y % 4) * 4 + x % 4`, so paving never repeats on a visible 16 px grid.

How edges work:

- A corner counts as paved if any of the four tiles around it is that paving. A paved tile is always full, and the grass tiles beside it get the ragged edge.
- Cobbles, slabs and bricks are kept or dropped whole, so edges follow the stones. Dirt edges are ragged per pixel.
- Grass tufts lean over every edge.
- Where two pavings meet, draw them in `windehus.PAVINGS` order. The later one lies over the earlier one.

## Pieces: `tileset.png` + `tileset.json`

`tileset.json` maps each name to `[x, y, w, h]` in `tileset.png`.

**Retaining walls**
- `wall-<kind>-<end>-<variant>` (16 × 16), in the overworld cliffs' cool slate.
- `kind`:
  - `top`: has the coping, the lit capstones along the upper terrace's edge.
  - `mid`: plain courses.
  - `base`: has the plinth where the wall meets the lower ground.
  - `solo`: a one-course wall with both coping and plinth.
- `end`: `l`, `m` or `r`. Ends get quoins.
- `variant`: 0 plain, 1 mossy, 2 ivy.
- `wall-shadow` goes on the ground tile just below a wall.

**Stairs**
- `stairs-<kind>-<end>`: steps cut through a wall, with the same `kind` values. `end` is `l`, `m`, `r` or `solo`, and the ends of a flight get stone cheek walls.
- The west cheek shades the flight. The shade widens step by step on the way down, and `shade-stair-foot` carries it out onto the ground below the flight's west end. Stairs get no `wall-shadow` below them.

**Terrace sides**
- `edge-l` / `edge-r`: coping along a raised terrace's west or east edge, drawn over the upper ground.

**Fences and walls**
- `fence-l|m|r|solo`: a rail fence across a tile.
- `fence-v`: a fence running north–south.
- `fence-gate`: a gate in a fence.
- `lowwall-l|m|r|solo`: a dry-stone garden wall.

**Buildings**
- Two storeys, from the bottom up:
  - a fieldstone footing;
  - a ground floor of dressed stone, or of plaster where brick shows through bald patches;
  - a jettied beam with joist ends and a band of shade under the overhang;
  - a close-studded half-timbered upper floor with braces;
  - a tiled roof (red clay or blue slate) with cross gables and a chimney.
- **Doors:** every door in town, the windmill's included, is the same 10 × 20 px opening as the cave gates. A door stands either on the 5 px footing or up a stoop, so doors line up across a street at one of two heights. A door in a house's end column keeps 2 px in from the corner (`windehus.door_px()`), so its frame and lintel sit on the wall.
- **Doorsteps:** the houses in `windehus.DOORSTEPS` stand on the street. The `doorstep` piece (16 × 11) is two low stone steps up to the 5 px sill, standing 5 px out onto the row below the house.
- **Stoops:** the houses in `windehus.STOOPS` stand on a cellar plinth (a lit coping over big dressed blocks, with barred cellar vents), so their door sits 12 px up. The `stoop` piece (20 × 24) is four 3 px steps between stone cheeks. It stands out from the door 12 px onto the row below the house, its west cheek shades the steps, and it casts a little shade east.
- **Weathering:** each house's limewashed plaster is aged to its `wear` (0-1). Flakes are chipped off down to the daub, with a shaded upper edge and a lit lower lip. Grey streaks wash down from the sills and beams, with the odd grimy one, and there are chalky faded patches. Shutter paint is worn to the wood in places. The bakery is the most weathered and the inn the least.
- `buildings.json` lists each building's size in tiles, its door rectangles, and whether it has a stoop.
- The current set: `inn` (7 wide), `house-red`, `house-slate`, `cottage`, `shop-arms`, `shop-goods` and `bakery`.
- The `building()` function makes new ones. It takes a width, a roof palette, gables, doors, ground and upper windows, flower boxes, a chimney, a sign icon (`bed`, `mug`, `sword`, `shield`, `flask` or `loaf`) and a ground-floor style.

**Trees**
- Windehus has one tree, the pine: `pine-<tiers>-<green>`, 32 px wide and its height in tiles tall (3, 4 or 5).
- Each pine is drawn whole, so its boughs run into each other with no seam. It is a cone of drooping bough layers. Each layer is lit across its upper left, has ragged needle tips along its hem, and sits in a dark-green band where the layer above overhangs it.
- Below the lowest boughs the trunk shows, flaring into roots, with the tree's shade falling to the lower right. The sprite's bottom edge is the ground line.
- Three greens: `deep` (most of the town's pines), `fir` (bluer) and `moss` (warmer). `windehus.pine_sprite()` picks each pine's green from where it stands, and the script draws only the pines the town uses.

**Shade**
- `shade-strip`, `shade-strip-top`, `shade-strip-end` and `shade-full` are flat, crisp, cool shade tiles.
- `windehus.building_shade()` lays them down the right side of each building. They start on a diagonal under the roof and tail past the front corner.
- Props carry their own small ground shadow: the well, stalls, haystack, lamps, barrels and the windmill.

**Landmarks**
- `windmill` (144 × 192, 9 × 12 tiles): Windehus's tower mill. It is tall and broad beside the town's one door: the tower is about five doors high and six across, and with its cap and vane it's nine doors high. It has:
  - rubble stone in grey, ochre, rust and blue-grey, laid in rough courses that bow toward the viewer, with pale lime mortar, on a stone plinth ring;
  - seven deep-set windows under brick arches, some shuttered, plus a lit dormer in the cap;
  - a plank reefing gallery ringing the tower, with a railing, struts and bronze bells;
  - a boarded curb with a bronze band, and an ogee cap of dark fish-scale shingles;
  - a verdigris collar, a bronze finial and a bronze cockerel weathervane;
  - the door under a brick relieving arch with a bronze medallion, and a bronze lantern beside it;
  - a tail pole down to a capstan wheel, two spare millstones, flour sacks, ivy, and a pennant staff on the gallery;
  - a shade strip cast east, like the houses.
- `windmill-sails-0..3` (144 × 144) go on the same origin as the tower and are drawn right after it. They are four open lattice sails on their whips around a bronze hub, plus the flapping pennant cloth. Each frame turns them a sixteenth of a turn, so cycling 0 → 3 spins them smoothly. `draw_ops()` emits frame 0, and a renderer swaps the number.
- `town-stone`: a boundary stone with *windehus* cut down its face in Selvar, using the same stroke data as the Fjalora codex.

**Animals**
- `sheepbird-<down|left|right|up>-<0..2>` (32 × 32): the game's sheep-bird mount, brought down from `assets/mounts/sheep-bird/source.png` to fit a 2 × 2 tile cell. The mount's own export in `assets/mounts/` is untouched.
  - The illustration is shrunk by averaging, not by picking single pixels. Where a pixel's patch is mostly eye or line, red saddle cloth or gold beak, it keeps that colour.
  - All twelve frames share one small palette, stray pixels are cleaned up, and the outline is closed only where pale wool or gold meets the ground, so it never doubles the illustration's own line.
  - Each sprite carries a small ground shadow. Frames 0 → 1 → 2 are the idle breathing cycle; the mount manifest times them at 650, 250 and 150 ms.
  - Three of them idle in the hay pen: one at the hay bale, two by the fence.

**Props**
- `flowers-0..2`: loose blooms in the grass.
- `barrel`: fits one tile. An oval lid sits in its chime ring over a body that swells at the middle, with staves that narrow toward the sides and three iron hoops that curve round it.
- `crate` (16 × 22) and `crates` (32 × 32): crates show their lid of boards from above, over a framed plank front with a diagonal brace. `crates` is a stack: a big crate with a small one on its lid, and another in front.
- `planter-0..2`: a flower box with a lit rim, an inner lip in shade, a board front between corner posts, and its planting lit on the upper left with a bloom spilling over the front.
- `gourds`: a heap of three ribbed yellow gourds by the red stall. `sacks`: two burlap flour sacks by the bakery, one tied at the neck.
- `bench`: a back of two rails, a seat whose boards catch the light over a shaded edge, and four legs.
- `signpost`: a squared post with a pointed cap and two arrow boards with real thickness, casting shade on the post.
- `stump`: an oval cut face with rings inside a bark rim, a furrowed round body, flaring roots and a little moss.
- `bush`: a round shrub of overlapping leaf clusters, a fresher green than the meadow. `azalea-0` (rose pink) and `azalea-1` (magenta) are the same shrub with glossier, darker leaves and trusses of blossom.
- `haystack`: a round bale lying end on, symmetrical. The rolled top runs back from its round face with two twine bands over it, and loose straw lies at its foot.
- `well`: a round drum of dressed stone. Its courses curve round it and its blocks narrow toward the sides. A coping ring circles dark water, and a small tiled roof stands on two posts over the windlass, rope and bucket.
- `stall-red`, `stall-blue`: a striped awning whose stripes round like folds of canvas, over a scalloped valance in shade. Baskets of goods sit on a plank counter: apples, pears, cabbages and carrots at the red stall, bread, cheese and jars at the blue.
- `lamp-0..5`: an iron street lamp with a four-pane cage. The six frames are the flame's loop, like the trail lanterns': rest, lean left, peak, lean right, dip, ember. A faint warm glow spills past the cage.

## The town

`windehus.py` holds Windehus, a 40 × 36 town. In the Sunrest grasslands, the west road runs on north through a cut in the cliffs and comes into town at the south edge. Walking south off the end of the road leads back to the cut.

It has three terraces:
- **The mill ridge:** a wood along the top, the tower mill, and three houses on a dirt lane (two of them up stoops).
- **The inn square:** the inn and brick yard, the flagstone market square with the well and two stalls, the shops, and a raised flower bed.
- **The road field:** the road in from Sunrest, the bakery, the town stone and a fenced hay field with three sheep-birds.

`draw_ops()` turns the layout into ordered drawing steps that any renderer can follow:
1. grass;
2. pavings, using their corner masks, then the lifted-slab decals;
3. walls, stairs, terrace edges, wall shadows and stair-foot shade;
4. building shade;
5. everything else, sorted by its bottom edge. The mill draws its sails over the tower, and a stoop or doorstep sorts just after its house.

Steps 1–4 are `ground_ops()` and step 5 is `things()`. The script bakes the flat layer into `windehus-ground.png` (640 × 576, opaque), so the game loads it in one go. A test re-renders it and fails if the layout changed without a rebuild.

## In the game (`windehus_town.py`)

- **Ground:** the world chunks are cut from `windehus-ground.png`.
- **Things:** each house, tree, fence and prop is its own canvas image, stacked back to front. The party is slotted in by the row it stands on, so it walks behind a house or a tree's canopy and in front of it once past its bottom row.
- **What blocks** (`windehus.floor()`):
  - walls, fences, the low wall and the flower bed;
  - every building's whole tile rect;
  - the well, the stalls and the hay mounds;
  - the bottom row of other props and of trees;
  - the mill tower's five middle columns, plus its capstan wheel and millstones.
- **What doesn't:** stairs, stoops, doorsteps, flowers and the lifted slabs are walkable. The hay pen's gate stays shut.
- **Animation:** the sails step a sixteenth turn every 0.3 s. Each sheep-bird breathes on its own phase. The lamps flicker through their six flame frames on the trail lanterns' timing (110, 100, 90, 110, 120, 130 ms), each lamp three frames behind the one before.
- **Safe ground:** no random encounters in town.
- **Music:** the calm Sunrest theme plays until a track is added at `assets/audio/windehus.mp3`.
- **Not yet:** doors don't open, there are no townsfolk, and there's no save point in town.
