# Caldrona Lite

A separate, lightweight retro experiment for Caldrona. It opens at a main menu labeled NEW JOURNEY, CONTINUE, and SETTINGS. NEW JOURNEY starts the first cavern; CONTINUE opens the four save files; SETTINGS opens display settings.

Display settings are available only from the title screen. Choose fullscreen or a 4:3 window size that fits the desktop, then select Apply. The choice is saved to `display_settings.json` and takes effect only after closing and restarting the game. The 16:9 game picture stays proportional inside a 4:3 window, with dark letterboxing; fullscreen scales the pixel art to fit the desktop.

Run Caldrona_Lite.py from PyCharm. Install the one optional controller dependency with:

    python -m pip install -r requirements.txt

Keyboard: arrows or WASD to move, Enter to select, Escape to open or close the in-game menu.

The opening cavern dialogue introduces Retri, a skirter checking calls for help before a collapse traps him inside. Press Enter, Cross, or click to advance each line. Walking pauses while the panel is open. Internal thoughts are italicized, and longer text is paged to fit the blue, silver-bordered box in `dialogue.py`.

Temur approaches after the opening collapse. Choose Travel with Temur to recruit him or Continue alone to send him down the corridor and continue solo. In older journeys where he was still waiting, talking to him offers the same choice. The decision persists in saves. Battle turns use an Agility-based CTB queue; supplies can target party members. Allies and enemies recover independently, so faster combatants can act more often. Continue after a party defeat restores the party at the entrance. Use the save sphere outside the Shalehorn entrance to preserve recruitment and journey progress.

Temur has directional world poses and a separate left-facing battle sprite. His world poses share Retri’s visible foot baseline. His dialogue portrait is registered by speaker name, so every Temur line receives it automatically. The party menu displays both members' portraits after recruitment. Generated source art and the prompts are documented in `assets/temur-art-notes.md`.

Retri's updated battle pose and portrait follow Temur's approved art style. Temur's world sprite is prepared directly at 16×16 so his eyes remain readable. The source art, preparation steps and prompts for these revisions are in `assets/party-art-notes.md`.

The in-game menu in `game_menu.py` opens with Escape or the controller Options button. D-pad/arrows move the cursor with a short initial delay and faster repeat; Enter/Cross opens the selected section, and Escape/Circle goes back. "Title Screen" goes back to the start screen.

### Equipment

Choose **Equip** in the in-game menu. Up/down selects Armor, Weapon, Shield,
or Accessory (the shared slot for artifacts, trinkets and accessories). Press
Enter/Cross to browse a category, then choose an item to equip it or choose
Remove Equipment. L1/R1 switches party members, including reserves;
Escape/Circle goes back. The equipped slots and character sprite appear together.
The stat panel below shows changes before you confirm an item. The list shows free
versus total owned copies, so a single item
cannot be worn by two people. Long lists scroll with up/down, and categories,
characters, and items also support mouse clicks.

A small starter collection is available to exercise the screen. Equipment
bonuses are separate from level-up stats. Strength and defense affect current
combat, while maximum HP/MP bonuses affect healing and the status display;
other bonuses are displayed for future mechanics. Equipment remains with the
party for the current journey; journey saves preserve equipment and inventory.

To add gear, add an `Equipment` entry to `CATALOG` in `equipment.py`, using a
unique ID and one of `armor`, `weapon`, `shield`, or `accessory`. For example:

```python
Equipment("silver_blade", "Silver Blade", "weapon", {"strength": 3},
          "A bright, well-balanced blade.")
```

Bonuses can use any key in `STAT_LABELS`, such as `defense`, `magic`,
`max_hp`, `max_mp`, `agility`, or `luck`. Adding an item to the catalog does
not automatically give it to the player: add quantities to `STARTING_GEAR`
for starter items, or increase `self.gear_inventory[item_id]` when implementing
loot or a shop. The stored quantity includes equipped copies.

PlayStation controller: use the digital D-pad to move, Cross to select, Circle to go back, and Options to open or close the in-game menu. Analog sticks are ignored. Pygame reads the standardized D-pad when Windows exposes the controller through SDL; direct joystick hats are supported too.

The cavern uses a fixed 320×180 logical view enlarged 3×, connected rooms, directional Retri walking frames, and tile-by-tile collision against rock. Each step lands Retri exactly at a tile center, keeping his 16×16 sprite within a single floor tile. Static cave art is cached in chunks.

A front-facing gunmetal lockbox sits in the first cavern room and fits within one tile. Face it and press Enter or Cross to collect one potion; the opened chest remains empty for the current journey.

The title menu uses the main Caldrona home screen: the four-sky castle landscape, embroidered CALDRONA wordmark, and navy-and-gold panel. Menu commands use the bundled Press Start 2P pixel font. Settings rows and the load-game notice use VT323. The landscape cycles through daylight, sunset, crescent night, and the orange moon, with moving water, stars, and wordmark glints. Background frames are 384 pixels wide and are enlarged 3× with nearest-neighbor zoom so they stay crisp on the 960×540 picture.

Gold, the main game's title theme, is stored as `assets/audio/gold.mp3` (128 kbps, encoded from the supplied wav). It loops on the menu, settings, and the load-game notice. It fades in when the menu opens and fades out when NEW JOURNEY starts, then Cavern Travel fades in as before. Returning to the menu fades Gold back in. The supplied Cavern Travel track still loops in the cavern and fades out on the way back to the menu.

### Cavern battles

Random encounters are checked only after a successful tile move. `battle.py` exposes
`ENCOUNTER_CHANCE = 0.08` (8% per step) and `SAFE_STEPS = 12`. The first twelve steps
after starting or finishing a battle are safe; the default averages roughly 25
steps between encounters. Standing still, hitting a wall, dialogue, and menus
never roll an encounter.

A short alternating shutter transitions into a side-view battle with Retri on
the right and one randomly selected Ivory Spider, Echo Bat, or Rock Crawler on
the left. Each sprite uses a 32×32 transparent asset at the same pixel scale.
The supplied Cavern Battle theme loops during combat. Music fades down during
the transition, then the incoming theme fades in; exploration music returns
after battle.

Battles are strictly turn-based: arrows/WASD or the PS4 D-pad select Attack,
Guard, Items, or Flee; Enter/Cross confirms. Escape/Circle highlights Flee
without executing it. Mouse command selection also works. An enemy replies
once after your action, and never attacks while you are choosing a command.
Choose Items, then Potion and a party member to restore up to 30 HP. The white
pointer marks the selected target; Back or Circle cancels targeting without
using a turn. Potions cannot revive fainted members. Guard halves the next hit, and fleeing has a 75%
success chance. Retri starts with 60 HP and three potions. Victory awards gold,
restores up to 8 HP to surviving active members, and replenishes one potion (maximum three). Defeat returns
Retri to the entrance with full health and potions. Confirm the result screen
to resume exploring. These stats and rewards last for the current journey;
saving and equipment remain future features.

Victories also award experience equal to twice the enemy's gold reward. The
next level requires 30 times the current level in XP; excess carries over.
Each level adds 8 maximum HP for Retri or 10 for Temur, and 1 Strength.
Every second level also adds 1 Defense, Magic, Magic Defense, Agility and maximum MP.
After attunement, Seer gains extra Magic and MP, Sollers gains Agility and Accuracy,
and Saint gains HP and Defense. These bonuses apply to future levels only.
Reserve members grow with the party; fainted members display their character's
standard fainted pose across all classes and remain fainted after victory.
Continuing after defeat restores the party.
Level and XP persist during
the current journey, including through defeat; saving remains a future feature.
The results screen shows the fighters who took part and the party's shared XP and gold. A glowing LEVEL UP animation appears when he advances, while
the supplied Caldrona Level Up track plays once for every victory. On a level-up,
confirm to review the old and new values for each party member's changed stats,
including reserves. Confirm through those pages to return to the cavern.

`battle.py` holds the encounter logic, combat model, battle UI, and transition.
Retri and Temur have lower starting stats with their own strengths. Status shows HP,
MP, Strength, Defense, Magic, Magic Defense, Agility, Luck, Evasion, and Accuracy.
The bat, beetle and spider have scaled-down starter profiles. HP, Strength and Defense affect current combat calculations.
The other stats are tracked for future combat mechanics.
Sprites load once and are reused; turns and transitions use the existing tick,
without blocking waits. `prepare_battle_assets.py` is an offline asset-preparation
tool, not a runtime dependency. Enemy generation details are in
`assets/battle/ART_NOTES.md`.

### Astral Hollow

The timber door in the north wall of the northeastern quarry room leads to Astral Hollow.
Walk into the door or face it and confirm. Inside, Shalehorn stands over a blue stone.
Watch the charge target and Guard with that fighter to expose its flank. Quarry Tremor hits
all standing fighters. During Burrow, use the turn to guard or heal. First Boss plays for
this encounter. After victory, approach or face the stone to see its reveal and open
Astral Sync. Use L1/R1 to choose a party member, up/down to choose a path, and
confirm to review it. The confirmation defaults to Go Back: select Bind only when
ready. Each member's choice is permanent for the current journey. Select Leave Unattuned
or press Back to decide later, then return to the stone or use Sync in the menu.
Seer ignores armor, Sollers earns bonus victory gold, and Saint restores 3 HP on Guard.
Retri and Temur appear in class-specific outfits during battles after attunement.
The southern door returns to the quarry. Saving a journey is not yet implemented.

In **Formation**, confirm a recruited member to switch between active and reserve.
Highlight a standing, active member and press **Right** to set the field leader.
The other active members follow one tile behind, including around corners. The
leader choice travels with the save. Up to three members fight at once.

Run the regression checks with:

    python -m unittest discover

This project reuses three existing Ipi assets, copied into this project:

- assets/retri-overworld.png — Retri's directional walking atlas
- assets/portraits/allsprites.png — supplied pixel-art portrait atlas; the dialogue panel crops Retri from it
- assets/cobble_floor.png — cavern floor tile
- assets/wall_brick.png — cavern wall tile
- assets/audio/cavern-travel.mp3 — cavern exploration music

The title menu reuses the main Caldrona title, copied byte-for-byte from https://github.com/dcbaughman/Caldrona:

- assets/title/sky-*.png — from assets/caldrona-title/sky-*.png (day, sunset, crescent night, and orange-moon blends)
- assets/title/logo-384-*.png — from assets/caldrona-title/logo-384-*.png (384-wide wordmark; the home menu shows alpha step 15)
- assets/audio/gold.mp3 — encoded at 128 kbps from assets/music/gold.wav (title theme, about 150 seconds, looped)

The bundled VT323 and Press Start 2P fonts are from Google Fonts, with their SIL Open Font Licenses in fonts/. This project has its own local Git repository, separate from the full game in PycharmProjects/Ipi.

### Saving and continuing

A floating save sphere stands outside Shalehorn's room, two tiles left of the
entrance approach. Face it and press Enter/Cross, or walk toward it, to choose
one of four files. Occupied files require an overwrite confirmation; Go Back
is selected by default. Escape/Circle closes the panel. Mouse selection works
in both the file list and the overwrite prompt. A successful save restores
the roster's full HP and MP and revives fallen allies, both in play and in
the saved file. Standing allies keep their existing ailments.

Continue on the home menu opens the same four files for loading, with party,
level, gold, location, and save time. Files live beside the game in
`saves/slot_1.json` through `saves/slot_4.json`. Each stores party statistics,
classes, attunement, equipment, research, consumables, gear, analects, material
and bazaar progress, recruitment, opened chests, boss/world flags, and position.
New Journey leaves existing save files intact. Writes use an atomic replacement;
an unreadable file does not prevent using the other slots. Saves occur only
when selected at the sphere.

### Crescendo

Each party member has a Crescendo meter and one equipped move. A damaging action
earns 16 charge. Healing, applying a stronger ward, or marking an enemy with a
lesson earns 12 when it changes the battle. Surviving a direct hit adds 8 plus
30 times the HP lost as a fraction of maximum HP, up to 20 for that action.
Charge carries between battles and through saves. KO clears it.

Open **Crescendo** in the field menu to equip one of four moves for the selected
member. Use Left/Right or L1/R1 to switch members. At 100%, the meter turns gold
and the equipped move appears under **Abilities**. It spends the full meter and
uses a rank-5 CTB turn without spending MP. Defaults are Rising Edge for Unbound,
Starbreak for Seer, Gilded Strike for Sollers, Dawn Chorus for Saint, and Onyx
Sever for the planned Weaver class.

Each Crescendo has its own two- to three-second animation. The cavern goes
gray during the cast so the colored effects stay readable. Damage and recovery
numbers appear at the move's impact, including green healing and blue MP gains.

### CTB battle order

The slim right-edge queue shows the current combatant (muted gold pointer) and
five upcoming turns. Party members use small portraits; monster entries use
MON A/B/C and bosses use BOSS. Enemy letters also appear in the selected enemy
name in the bottom panel; there are no overhead nameplates. The turn number counts individual combatant actions, including
monster turns. HP and current/maximum MP remain visible throughout battle.
Choosing actions and targets does not advance battle ticks. Preview assumes
rank-3 actions for later turns and uses the currently selected action for the
current actor, so it is a forecast, not a guarantee of every future action.

Recovery is `ceil(tick_speed(Agility) * action_rank * status_modifier)` using
effective equipment-adjusted Agility. Breakpoints are implemented in `ctb.py`:
0:28, 1:26, 2:24, 3:22, 4:20, 5–6:16, 7–9:15, 10–11:14, 12–14:13,
15–16:12, 17–18:11, 19–22:10, 23–28:9, 29–34:8, 35–43:7, 44–61:6,
62–97:5, 98–169:4, 170–255:3. Values outside 0–255 clamp to the endpoints.

Attack, Flee, and Steal use rank 3. Items, Guard, marks, and wards use rank 2.
Healing/MP recovery lessons use rank 3. Other offensive lessons use rank 4,
or rank 6 when learned at level 12 or later. Guard and wards expire at the
recipient's next turn; they can cover multiple intervening enemy actions.
Shalehorn's telegraphed sequence advances on its own CTB turns.

The opening is deterministic: each actor starts with `tick_speed * 3` wait;
equal counters resolve in party/enemy registration order. A separate randomized
opening formula was not supplied. Every living monster has its own counter.
Dead combatants are excluded from forecasts and future turns.

The scheduler supports Haste (half recovery) and Slow (double recovery). Applying
Haste immediately floors the remaining wait divided by two; Slow doubles it.
Removing either leaves the existing wait alone. This provides timing support
for future status moves; no new Haste/Slow spells have been added here.

### First ailment and enemy-skill set

These are Caldrona's own balance rules, inspired by the supplied status reference:

| Ailment | Effect | Duration |
| --- | --- | --- |
| Poison | Loses 8% of equipment-adjusted maximum HP, rounded up, after each own turn; can cause KO. Shalehorn takes 2%. | Until cured |
| Frozen | Loses one CTB turn; recovery still uses rank 3. Physical damage thaws the target. Thawing or curing grants resistance for two own turns. | 1 affected turn |
| Darkness | Physical hit chance drops to 25–65%, based on Accuracy versus Evasion. Magic is unaffected. | Until cured |
| Silence | Blocks commands classified as Magic, without spending MP or a turn. Items, Guard, Attack, and Abilities remain available. | Until cured |
| Webbed | Halves Evasion and blocks party escape while any standing ally is webbed. Other commands remain available. | 3 own turns, or 1 from Web Shot |

Poison, Darkness, and Silence persist on standing characters through
battle exit, exploration, and saves. KO clears all ailments. Continuing after
a party defeat clears the entire roster's ailments at the entrance. Frozen and
Webbed count down on the affected combatant's own turns. Reapplying never
stacks intensity. Poison damage ticks once per resolved turn in battle.
Shalehorn is immune to Frozen and Silence; Darkness still affects its direct
physical attacks but not its ground-wide Tremor.

Enemy signature skills alternate with basic attacks and require finite MP:
Ivory Spider can poison with Venom Bite. Echo Bat’s Echo Screech and Rock Crawler’s
Dust Ram deal damage with their own animations.
Silenced enemies fall back to basic attacks when their planned skill is Magic.
Quarry Tremor can also inflict Darkness through shale dust. The enemy panel
shows the next planned move, and skill attacks reuse the existing effect art.

Players gain ailments through existing research moves, keeping class pool sizes:
Venom Edge (85% Poison), Smoke Spark (75% Darkness), Mind Flare (75% Silence),
Mist Ray (65% Frozen), Unbound Spark (40% Silence), and Flint Burst (50% Darkness).
Mend also cures Poison. Litany cleanses ailments while restoring MP.
Research descriptions show these additions.

Remedy cures ailments on a standing ally, costs 12 gold at Merren, and
uses the existing antidote icon. New journeys start with two Remedies; existing
save inventories are preserved. Healthy targets do not consume a Remedy.
The battle item list scrolls four rows to keep its panel compact.

PSN/FRZ/DRK/SIL labels show remaining turns in the bottom party/status panels.
The selected enemy's ailments replace its next-move hint while afflicted.
Permanent ailments show PSN/DRK/SIL without countdown numbers. A translucent faceted ice shell pops up at impact and stays until thaw; it then
breaks into shards. The overlay follows camera movement and larger monsters, and a small colored edge marks afflicted CTB entries.
Shalehorn's tell uses the existing message box while choosing a command. Poison damage has its own brief green damage number.

### Frozen crystal animation

Frozen uses `assets/battle/fx/frozen-shell/`, generated from the supplied frozen
adventurer GIF. The ice is an overlay over the current class/monster sprite,
not a replacement character. It grows from foot-level shards at the hit contact,
closes into a translucent crystal, shimmers for as long as Frozen remains active,
and breaks apart when the status expires, is cured, or physical damage thaws it.
KO, victory, defeat, battle restart, and battle exit clear the overlay. This is
a visual update; freeze duration and resistance rules remain unchanged.

`prepare_frozen_fx.py` rebuilds the packed transparent frames and preview GIF
from the preserved generated source. Exact ImageGen prompt and asset details
are in `assets/battle/fx/frozen-shell/art-notes.md`.

### Persistent poison animation and cures

Poison now uses `assets/battle/fx/poison-aura/`: purple fumes, green bubbles, and
a brief application puff inspired by the supplied Poison Progression GIF. The
application animation waits for impact, then loops until Poison is actually
removed. Already-poisoned party members resume the held loop in the next battle.
The overlay follows characters, larger enemies, and camera movement. A KO
clears Poison and its overlay. A revived character can be poisoned again.

Party records store permanent ailments in the optional `ailments` dictionary
using `-1` for until-cured. Old save files without that dictionary still load.
Standing characters carry these ailments through saving, loading, winning,
and fleeing. Reviving a party member and continuing after a defeat clear ailments.
Remedy works in both field and battle; Saint's Mend removes Poison, and Litany
removes all ailments. HP recovery alone does not cure them. The Status menu lists
current ailments. Frozen retains its existing one-turn/thaw behavior and is not
written into persistent party records.

`prepare_poison_fx.py` exports the transparent native overlay frames and preview
from the preserved ImageGen source. The exact prompt and art notes are in
`assets/battle/fx/poison-aura/art-notes.md`.

### Darkness and Silence visuals

Darkness gives the actual combatant sprite a near-black tint while preserving its
transparent silhouette and faint internal detail. Cached tint variants follow
guard/standing poses, and curing Darkness restores the correct original sprite.
Poison fumes and Frozen remain independent overlays, so combined ailments are
visible together. KO clears Darkness and its tint. A standing character retains
Darkness between battles until it is cured.

Silence uses a small muted-violet hex over the mouth with three crossed stitches.
It follows the actual sprite during camera motion, lunges, and hit blinking.
It disappears on cure/KO/exit. These are native Tk shapes and cached in-memory
tints; they do not replace character artwork or add overhead nameplates.

### Sunrest cave story and route

The main route is now a linear backbone through the existing entry room, lower
workings, blue-seam room, and Shalehorn forecourt. The first chest, Temur, save
shrine, and boss door retain their established locations. Mining carts, discarded
tools, a damaged support, and a lantern/ledger can be inspected by facing them
and pressing Enter/Cross. Props do not obstruct the corridor backbone.

New Journey starts with Retri at the mine entrance, where he mentions the calls
for help he heard. He takes two steps into the room, pauses to look left and
right, and takes another step before the cave-in. Falling debris, drifting dust,
the supplied rock-fall sound, and Retri's startled jump mark the collapse. The
stone shoulders stay joined to the cave wall as rubble plugs the tunnel. After
the dust settles, Temur walks in to talk. If Retri declines the offer to travel
together, Temur walks out of frame and is absent for the rest of the cave.


A miner near Shalehorn's door warns about the blue rock, the creature guarding
it, attacks on anyone who approaches, and structural damage from its digging.
Approaching the forecourt triggers the warning once; the miner can be spoken to
again, including after the boss is defeated. He points to the survey exit beyond
the boss chamber. This does not add a second exit before Shalehorn.

Saves preserve collapse, miner-warning, and inspected-object progress in the
optional `cave_story` field. Older saves load after the opening without replaying
it. Positions in removed legacy corridors move to the nearest current floor
tile; malformed/out-of-map positions still fail validation.

Shalehorn's neck hinges into a slower Charge toward the center of the
battlefield. The cave dims to gray for the blue tusk shimmer, and loose shale
flies backward along his path. Tremor ripples the
existing floor pixels from the impact toward the party. During Burrow, the
surrounding shale forms a recessed opening that stays visible until Eruption.
The battlefield lighting cycles through the effect while the battle UI stays
still.

Press **T** at the title screen, then use **L1/R1** or **Q/E** to cycle through
Character Skins, Test Animation, Crescendos, and Player Moves. In an animation
tab, select a move with Left/Right, step frames with Up/Down, and replay with Enter/Cross.
**C** compares the previous and revised Burrow, Tremor, or Charge at the same
frame in Test Animation. Crescendos previews all 20 moves in a practice battle,
including the four planned Weaver moves.

Player Moves previews both fighters' equipment poses, bare-handed strikes, magic
casts, and critical kneeling. **C/Triangle** switches outfits. In battle, basic
attacks and weapon-tagged lessons use the equipped weapon's motion. Magic holds
the focus or hand in front for a short glimmer before release. Fighters kneel at
25% HP or lower and use the fainted pose at zero HP.

The standard sword keeps its blade length from windup through recovery.
Player Moves also previews the greatsword, pike, halberd, bow, and whip. The
bow preview shoots at two practice targets at different heights. Battle uses
the same flight effect, aimed at the selected enemy.

### Den Mother's Lair

A short eastern spur off the lower workings ends at a webbed gate. The gate is
sealed in normal play. The planned unlock is to burn the webbing with fire magic.
The lair beyond it contains the Den Mother encounter
and the Black Stone, which can be picked up after victory. Save data records
the gate, victory, and Black Stone progress.

Flee starts at 75%, adds the fastest standing ally's Agility, then subtracts
the largest Agility-plus-Pursuit value among living enemies. The result is
clamped to 1–100% unless Webbed blocks the attempt. Den Mother has 14 Agility
and 65 Pursuit, giving an Agility 8 party a 4% chance when clear of webs.

Den Mother starts with Spin Web and can summon two Spiderlings. At 60% HP she
adds Silk Shroud, Feast, and Venom Spray. Below 25% she can consume the remaining
brood, telegraph Death Embrace, and enter a temporary fury when hit with fire.
Guard or clear the targeted ally's Webbed status to counter Death Embrace.
Merren's Bazaar carries the Webbed-immune Silkweave Coat and the Embersteel Blade.
Fire deals 1.5× damage to Ivory Spiders and Den Mother and 2× to Spiderlings.
