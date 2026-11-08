# Caldrona Lite

A separate, lightweight retro experiment for Caldrona. It opens at a main menu with Play, Load Game, and Settings. Play enters the first cavern instance; Load Game currently reports that no save exists yet.

Run Caldrona_Lite.py from PyCharm. Install the one optional controller dependency with:

    python -m pip install -r requirements.txt

Keyboard: arrows or WASD to move, Enter to select, Escape to return to menu.

PlayStation controller: use the digital D-pad to move, Cross to select, and Circle to return. Analog sticks are ignored. Pygame reads the standardized D-pad when Windows exposes the controller through SDL; direct joystick hats are supported too.

The cavern uses a fixed 320×180 logical view enlarged 3×, connected rooms, directional Retri walking frames, and collision against rock. Static cave art is cached in chunks and the background moves in one Canvas operation while the player walks.

The supplied Cavern Travel track plays on a loop in the cavern, fades in on Play, and fades out when returning to the menu. The menu stays silent.

This project reuses three existing Ipi assets, copied into this project:

- assets/retri-overworld.png — Retri's directional walking atlas
- assets/cobble_floor.png — cavern floor tile
- assets/wall_brick.png — cavern wall tile
- assets/audio/cavern-travel.mp3 — cavern exploration music

The bundled VT323 and Press Start 2P fonts are from Google Fonts, with their SIL Open Font Licenses in fonts/. This project has its own local Git repository, separate from the full game in PycharmProjects/Ipi.
