# Caldrona Lite

A separate, lightweight retro experiment for Caldrona. It opens at a main menu with Play, Load Game, and Settings. Play enters the first cavern instance; Load Game currently reports that no save exists yet.

Run Caldrona_Lite.py from PyCharm. Install the one optional controller dependency with:

    python -m pip install -r requirements.txt

Keyboard: arrows or WASD to move, Enter to select, Escape to open or close the in-game menu.

The opening cavern dialogue introduces Retri, a skirter investigating a strange sound. Press Enter, Cross, or click to advance each line. Walking pauses while the panel is open. Internal thoughts are italicized, and longer text is paged to fit the blue, silver-bordered box in `dialogue.py`.

The in-game menu in `game_menu.py` opens with Escape or the controller Options button. D-pad/arrows move the cursor with a short initial delay and faster repeat; Enter/Cross opens the selected section, and Escape/Circle goes back. The sections are navigation shells for future features. "Title Screen" goes back to the start screen.

PlayStation controller: use the digital D-pad to move, Cross to select, Circle to go back, and Options to open or close the in-game menu. Analog sticks are ignored. Pygame reads the standardized D-pad when Windows exposes the controller through SDL; direct joystick hats are supported too.

The cavern uses a fixed 320×180 logical view enlarged 3×, connected rooms, directional Retri walking frames, and tile-by-tile collision against rock. Each step lands Retri exactly at a tile center, keeping his 16×16 sprite within a single floor tile. Static cave art is cached in chunks.

The supplied Cavern Travel track plays on a loop in the cavern, fades in on Play, and fades out when returning to the menu. The menu stays silent.

This project reuses three existing Ipi assets, copied into this project:

- assets/retri-overworld.png — Retri's directional walking atlas
- assets/portraits/allsprites.png — supplied pixel-art portrait atlas; the dialogue panel crops Retri from it
- assets/cobble_floor.png — cavern floor tile
- assets/wall_brick.png — cavern wall tile
- assets/audio/cavern-travel.mp3 — cavern exploration music

The bundled VT323 and Press Start 2P fonts are from Google Fonts, with their SIL Open Font Licenses in fonts/. This project has its own local Git repository, separate from the full game in PycharmProjects/Ipi.
