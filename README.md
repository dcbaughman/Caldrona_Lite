# Caldrona Lite

A separate, lightweight retro experiment for Caldrona. It now starts directly inside a walkable cavern instance instead of opening the title menu.

Run Caldrona_Lite.py from PyCharm or with python Caldrona_Lite.py. Move using WASD or the arrow keys; press Esc to close.

The cave is a small hand-authored set of connected rooms and halls. The camera follows the single player and redraws the visible tile area as needed. Collision keeps the character on walkable floor. The window uses a 320×180 logical view enlarged 3× with crisp nearest-neighbor pixel scaling.

This prototype reuses three existing Ipi assets, copied into this project so it can evolve independently:

- assets/retri-overworld.png — Retri's directional walking atlas
- assets/cobble_floor.png — cavern floor tile
- assets/wall_brick.png — cavern wall tile

The bundled VT323 font is used for the cavern HUD, with its SIL Open Font License in fonts/. The local Git repository is separate from the full game in PycharmProjects/Ipi.
