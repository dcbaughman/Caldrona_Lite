# Caldrona Lite

A separate, lightweight retro experiment for Caldrona. It opens at a main menu labeled NEW JOURNEY, CONTINUE, and SETTINGS. NEW JOURNEY starts the first cavern; CONTINUE reports that no save exists yet; SETTINGS opens display settings.

Display settings are available only from the title screen. Choose fullscreen or a 4:3 window size that fits the desktop, then select Apply. The choice is saved to `display_settings.json` and takes effect only after closing and restarting the game. The 16:9 game picture stays proportional inside a 4:3 window, with dark letterboxing; fullscreen scales the pixel art to fit the desktop.

Run Caldrona_Lite.py from PyCharm. Install the one optional controller dependency with:

    python -m pip install -r requirements.txt

Keyboard: arrows or WASD to move, Enter to select, Escape to open or close the in-game menu.

The opening cavern dialogue introduces Retri, a skirter investigating a strange sound. Press Enter, Cross, or click to advance each line. Walking pauses while the panel is open. Internal thoughts are italicized, and longer text is paged to fit the blue, silver-bordered box in `dialogue.py`.

Temur waits near the entrance. Face him and press Enter or Cross to talk. After the cave shakes and the conversation finishes, he joins for the current journey. Party members take individual battle turns; the shared inventory's Potion heals the acting member. A surviving enemy responds after the party's turns. Continue after a party defeat restores the party at the entrance. The existing save system is not yet implemented, so recruitment lasts until a new journey begins.

Temur uses separate front-facing world and left-facing battle sprites, prepared at Retri's source pixel height and displayed at the same scales. His dialogue portrait is registered by speaker name, so every Temur line receives it automatically. The party menu displays both members' portraits after recruitment. Generated source art and the prompts are documented in `assets/temur-art-notes.md`.

Retri's updated battle pose and portrait follow Temur's approved art style. Temur's world sprite is prepared directly at 16×16 so his eyes remain readable. The source art, preparation steps and prompts for these revisions are in `assets/party-art-notes.md`.

The in-game menu in `game_menu.py` opens with Escape or the controller Options button. D-pad/arrows move the cursor with a short initial delay and faster repeat; Enter/Cross opens the selected section, and Escape/Circle goes back. The sections are navigation shells for future features. "Title Screen" goes back to the start screen.

PlayStation controller: use the digital D-pad to move, Cross to select, Circle to go back, and Options to open or close the in-game menu. Analog sticks are ignored. Pygame reads the standardized D-pad when Windows exposes the controller through SDL; direct joystick hats are supported too.

The cavern uses a fixed 320×180 logical view enlarged 3×, connected rooms, directional Retri walking frames, and tile-by-tile collision against rock. Each step lands Retri exactly at a tile center, keeping his 16×16 sprite within a single floor tile. Static cave art is cached in chunks.

A treasure chest sits in the first cavern room. Face it and press Enter or Cross to collect one potion; the opened chest remains empty for the current journey.

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
Astral Sync. Use left/right to choose a party member, up/down to choose a path, and
confirm to review it. The confirmation defaults to Go Back: select Bind only when
ready. Each member's choice is permanent for the current journey. Select Leave Unattuned
or press Back to decide later, then return to the stone or use Sync in the menu.
Seer ignores armor, Sollers earns bonus victory gold, and Saint restores 3 HP on Guard.
Retri and Temur appear in class-specific outfits during battles after attunement.
The southern door returns to the quarry. Saving a journey is not yet implemented.

Formation lets you confirm a recruited member to switch between active and reserve.
Up to three fight at once. New recruits enter reserve when all three slots are occupied.
Formation and the boss unlock last for the current journey.

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
