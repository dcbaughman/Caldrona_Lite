"""Sunrest's guarded shelter and the western route around the mountain."""

from dialogue import DialogueLine


ENTRANCE = (32, 2)
GATE = (32, 13)
KORWARD = (33, 12)
SENBRANKA_TILE = (8, 5)
ROAD = {(32, y) for y in range(3, 18)} | {(x, 18) for x in range(7, 33)} | {(7, y) for y in range(3, 18)}
# The west road runs on north through a cut in the cliffs. Stepping into the cut leads to Windehus.
TOWN_ROAD = {(7, y) for y in range(3)}
FROM_TOWN = (7, 3)
FENCE = ({(x, 13) for x in range(23, 43)} |
         {(x, y) for x in (23, 42) for y in range(3, 13)}) - {GATE}
RIDGE = {(x, y) for y in range(3, 15)
         for x in range(12 + (y-3)//3, 23 - (y-3)//4)}
CHOICES = ("Open the gate", "I'll prepare first")


class GrasslandInstance:
    width, height = 64, 40
    spawn = (32.5 * 16, 3.5 * 16)

    def __init__(self):
        self.floor = {(x, y) for y in range(3, self.height - 1)
                      for x in range(1, self.width - 1)} - FENCE - RIDGE - {KORWARD, SENBRANKA_TILE}

    def walkable(self, px, py):
        return (int(px // 16), int(py // 16)) in self.floor

    @staticmethod
    def sheltered(tile):
        return 23 < tile[0] < 42 and 3 <= tile[1] < GATE[1]


class Cordon:
    TAG = "sunrest_cordon"
    MAP = "windehus_map"

    def __init__(self, app, art, scale, faces):
        self.app, self.scale = app, scale
        c = app.canvas
        self.fences = [(tile, c.create_image(0, 0, image=art["side" if tile[1] != GATE[1] else "rail"],
                                             state="hidden", tags=self.TAG)) for tile in sorted(FENCE)]
        self.gate = c.create_image(0, 0, image=art["gate"], state="hidden", tags=self.TAG)
        self.guard = c.create_image(0, 0, image=faces["down"], state="hidden", tags=self.TAG)

    def render(self, camera):
        a = self.app
        c = a.canvas
        cx, cy = camera
        for (x, y), item in (*self.fences, (GATE, self.gate), (KORWARD, self.guard)):
            c.coords(item, ((x+.5)*16-cx)*self.scale, ((y+.5)*16-cy)*self.scale)
            visible = a.outdoors and not getattr(a, "in_town", False) and (item != self.gate or not a.cordon_open)
            c.itemconfigure(item, state="normal" if visible else "hidden")

    def talk(self):
        a = self.app
        if a.cordon_open:
            a.dialogue.show([DialogueLine("Korward", "West below the ridge, then north for Windehus.")],
                            on_complete=self.show_map)
            return
        lines = []
        if not a.route_map:
            lines.extend([
                DialogueLine("Korward", "Hold there. What brought you to the quarry?"),
                DialogueLine("Retri", "I was carrying mill bearings to Windehus. Then I heard someone call from inside the cave."),
                DialogueLine("Retri", "I went in to help. The roof came down behind me. I can't get back the way I came."),
                DialogueLine("Korward", "Then take my map. Follow the road west below the ridge. Turn north once you're around the mountain."),
                DialogueLine("", "Received the Windehus route map. Press M to view it."),
                DialogueLine("Korward", "Past this gate, watch the long grass. Stock up on Potions and a Remedy from Merren. If a ram lowers its head, guard."),
            ])
        lines.append(DialogueLine("Korward", "Ready for me to open the gate?"))
        a.dialogue.show(lines, on_complete=self.offer)

    def offer(self):
        a = self.app
        a.route_map = True
        a.screen = "cordon_choice"
        a.keys.clear()
        a.held_direction = None
        self.select(1)

    def select(self, choice):
        self.choice = choice
        self.app.dialogue.draw_choice(CHOICES, choice)

    def choose(self):
        a = self.app
        a.dialogue.clear()
        a.screen = "game"
        if self.choice == 0:
            a.cordon_open = True
            a.encounters.reset()
            self.render(a.world_camera)
            a.dialogue.show([DialogueLine("Korward", "Gate's open. Keep the ridge on your right.")])

    def show_map(self):
        a = self.app
        a.screen = "route_map"
        c, tag = a.canvas, self.MAP
        c.create_rectangle(267, 55, 693, 485, fill="#30291f", outline="#9e8456", width=4, tags=tag)
        c.create_rectangle(279, 67, 681, 473, fill="#d0b883", outline="#634b30", width=2, tags=tag)
        c.create_text(480, 102, text="ROAD TO WINDEHUS", font=a._font(27, True), fill="#3e3023", tags=tag)
        for x, y in sorted(RIDGE):
            x, y = 364 + x*7, 158 + y*11
            c.create_rectangle(x, y, x+8, y+12, fill="#857555", outline="", tags=tag)
        route = [(32, 3), (32, 18), (7, 18), (7, 2)]
        c.create_line(*(v for x, y in route for v in (364+x*7, 158+y*11)),
                      fill="#824936", width=4, arrow="last", tags=tag)
        c.create_text(409, 148, text="WINDEHUS", font=a._font(18, True), fill="#3e3023", tags=tag)
        c.create_text(585, 155, text="SUNREST", font=a._font(18, True), fill="#3e3023", tags=tag)
        c.create_text(481, 405, text="West below the ridge, then north.", font=a._font(19), fill="#3e3023", tags=tag)
        c.create_text(481, 447, text="ENTER / CROSS · CLOSE", font=a._font(17), fill="#3e3023", tags=tag)

    def close_map(self):
        a = self.app
        a.canvas.delete(self.MAP)
        a.screen = "game"
        a.keys.clear()
        a.held_direction = None
