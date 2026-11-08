# Caldrona Lite

A separate, lightweight retro experiment for Caldrona. It opens at a main menu with Play, Load Game, and Settings. Play enters the first cavern instance; Load Game currently reports that no save exists yet.

Display settings are available only from the title screen. Choose fullscreen or a 4:3 window size that fits the desktop, then select Apply. The choice is saved to `display_settings.json` and takes effect only after closing and restarting the game. The 16:9 game picture stays proportional inside a 4:3 window, with dark letterboxing; fullscreen scales the pixel art to fit the desktop.

Run Caldrona_Lite.py from PyCharm. Install the one optional controller dependency with:

    python -m pip install -r requirements.txt

Keyboard: arrows or WASD to move, Enter to select, Escape to open or close the in-game menu.

The opening cavern dialogue introduces Retri, a skirter investigating a strange sound. Press Enter, Cross, or click to advance each line. Walking pauses while the panel is open. Internal thoughts are italicized, and longer text is paged to fit the blue, silver-bordered box in `dialogue.py`.

The in-game menu in `game_menu.py` opens with Escape or the controller Options button. D-pad/arrows move the cursor with a short initial delay and faster repeat; Enter/Cross opens the selected section, and Escape/Circle goes back. The sections are navigation shells for future features. "Title Screen" goes back to the start screen.

PlayStation controller: use the digital D-pad to move, Cross to select, Circle to go back, and Options to open or close the in-game menu. Analog sticks are ignored. Pygame reads the standardized D-pad when Windows exposes the controller through SDL; direct joystick hats are supported too.

The cavern uses a fixed 320×180 logical view enlarged 3×, connected rooms, directional Retri walking frames, and tile-by-tile collision against rock. Each step lands Retri exactly at a tile center, keeping his 16×16 sprite within a single floor tile. Static cave art is cached in chunks.

The supplied Cavern Travel track plays on a loop in the cavern, fades in on Play, and fades out when returning to the menu. The menu stays silent.

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
Guard, Potion, or Flee; Enter/Cross confirms. Escape/Circle highlights Flee
without executing it. Mouse command selection also works. An enemy replies
once after your action, and never attacks while you are choosing a command.
Choose Items, then Potion to restore up to 25 HP; Back or Circle returns to the commands without using a turn. Guard halves the next hit, and fleeing has a 75%
success chance. Retri starts with 60 HP and three potions. Victory awards gold,
restores up to 8 HP, and replenishes one potion (maximum three). Defeat returns
Retri to the entrance with full health and potions. Confirm the result screen
to resume exploring. These stats and rewards last for the current journey;
saving and equipment remain future features.

Victories also award experience equal to twice the enemy's gold reward. The
next level requires 30 times the current level in XP; excess carries over.
Each level adds 5 maximum HP and 1 attack damage. Level and XP persist during
the current journey, including through defeat; saving remains a future feature.

`battle.py` holds the encounter logic, combat model, battle UI, and transition.
Sprites load once and are reused; turns and transitions use the existing tick,
without blocking waits. `prepare_battle_assets.py` is an offline asset-preparation
tool, not a runtime dependency. Enemy generation details are in
`assets/battle/ART_NOTES.md`.

Run the regression checks with:

    python -m unittest test_battle test_battle_ui test_display_settings

This project reuses three existing Ipi assets, copied into this project:

- assets/retri-overworld.png — Retri's directional walking atlas
- assets/portraits/allsprites.png — supplied pixel-art portrait atlas; the dialogue panel crops Retri from it
- assets/cobble_floor.png — cavern floor tile
- assets/wall_brick.png — cavern wall tile
- assets/audio/cavern-travel.mp3 — cavern exploration music

The bundled VT323 and Press Start 2P fonts are from Google Fonts, with their SIL Open Font Licenses in fonts/. This project has its own local Git repository, separate from the full game in PycharmProjects/Ipi.
