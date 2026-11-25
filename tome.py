"""The party roster and each member's categorized research tome."""
from classes import current_job
from abilities import remember
from research import ANALECTS, CATEGORIES, lessons_for, research_lesson, research_status


class TomeScene:
    TAG = "tome"

    def __init__(self, canvas, font, portrait):
        self.canvas, self.font, self.portrait = canvas, font, portrait

    def start(self, party, analects):
        self.party, self.analects = party, analects
        self.member_index = self.category = self.selection = 0
        self.reading = False
        self.held = None
        self.repeat_at = 0.0
        self.feedback = ""
        self.portraits = {}
        self.draw()

    @property
    def member(self):
        return self.party[self.member_index]

    def entries(self):
        return [lesson for lesson in lessons_for(self.member)
                if lesson.category == CATEGORIES[self.category]]

    def change_category(self, step):
        if self.reading:
            self.category = (self.category + step) % len(CATEGORIES)
            self.selection = 0
            self.feedback = ""
            self.draw()

    def navigate(self, direction, now):
        allowed = ("up", "down", "left", "right") if self.reading else ("up", "down")
        if direction not in allowed:
            self.held = None
            return
        if direction == self.held and now < self.repeat_at:
            return
        self.held, self.repeat_at = direction, now + 0.19
        step = -1 if direction in ("up", "left") else 1
        if direction in ("left", "right"):
            self.change_category(step)
            return
        if self.reading:
            self.selection = (self.selection + step) % max(1, len(self.entries()))
        else:
            self.member_index = (self.member_index + step) % len(self.party)
        self.feedback = ""
        self.draw()

    def confirm(self):
        if self.reading:
            if not self.entries():
                return
            lesson = self.entries()[self.selection]
            self.feedback = research_lesson(self.member, lesson, self.analects)
            remember(self.member)
        else:
            self.reading = True
            self.category = self.selection = 0
        self.draw()

    def back(self):
        if self.reading:
            self.reading = False
            self.feedback = ""
            self.draw()
            return False
        self.canvas.delete(self.TAG)
        return True

    def click(self, x, y):
        if not self.reading:
            i = (y - 116) // 63 + max(0, self.member_index - 4)
            if 52 <= x <= 906 and 116 <= y < 431 and 0 <= i < len(self.party):
                self.member_index = i
                self.confirm()
            return
        if 49 <= x < 913 and 102 <= y <= 143:
            self.change_category((x - 49) // 216 - self.category)
        elif 50 <= x <= 535 and 169 <= y < 421:
            i = (y - 168) // 38
            if i < len(self.entries()):
                if i == self.selection:
                    self.confirm()
                else:
                    self.selection = i
                    self.feedback = ""
                    self.draw()

    def text(self, x, y, label, size=20, color="#edf3ff", **options):
        self.canvas.create_text(x, y, text=label, anchor=options.pop("anchor", "w"),
                                fill=color, font=self.font(size), tags=self.TAG, **options)

    def draw(self):
        c, tag = self.canvas, self.TAG
        c.delete(tag)
        c.create_rectangle(0, 0, 960, 540, fill="#0d1424", outline="", tags=tag)
        c.create_rectangle(25, 25, 935, 515, outline="#bc9d64", width=3, tags=tag)
        if not self.reading:
            self.text(50, 59, "TOME", 31, "#f0d28c")
            self.text(50, 93, "Choose a party member.", 19, "#97cbdb")
            first = max(0, self.member_index - 4)
            for i, member in enumerate(self.party[first:first+5], first):
                y = 144 + (i - first)*63
                name = member["name"]
                selected = i == self.member_index
                c.create_rectangle(49, y-26, 912, y+26, outline="#587791",
                                   fill="#203555" if selected else "#141f33", tags=tag)
                if name not in self.portraits:
                    portrait = self.portrait(name)
                    self.portraits[name] = portrait.subsample(3) if portrait is not None else None
                if self.portraits[name] is not None:
                    c.create_image(104, y, image=self.portraits[name], tags=tag)
                self.text(60, y, "â–¶" if selected else "", 17, "#f0d28c")
                self.text(147, y, name, 23)
                self.text(438, y, current_job(member) or "Unbound", 20, "#97cbdb")
                self.text(882, y, f"{member.get('rp', 0)} RP", 20, anchor="e")
            self.text(50, 482, "UP / DOWN PARTY   ENTER / CROSS OPEN   ESC / CIRCLE BACK", 17, "#97cbdb")
            return
        member = self.member
        job = current_job(member) or "Unbound"
        self.text(50, 59, f"{member['name']} Â· {job} Tome", 28, "#f0d28c")
        self.text(906, 59, f"LV {member.get('level', 1)}   {member.get('rp', 0)} RP", 22, "#f0d28c", anchor="e")
        for i, category in enumerate(CATEGORIES):
            x = 49 + 216*i
            selected = i == self.category
            c.create_rectangle(x, 103, x+207, 142, fill="#264363" if selected else "#131e34",
                               outline="#82b4cb" if selected else "#406078", tags=tag)
            self.text(x+103, 122, category.upper(), 18, anchor="center")
        c.create_rectangle(548, 167, 912, 421, fill="#141f33", outline="#587791", tags=tag)
        entries = self.entries()
        for i, lesson in enumerate(entries):
            y = 187 + i*38
            selected = self.selection == i
            if selected:
                c.create_rectangle(49, y-19, 533, y+19, fill="#203555", outline="#82b4cb", tags=tag)
            status = research_status(member, lesson, self.analects)
            color = "#9ad5a7" if status == "Learned" else "#f0d28c" if status == "Ready" else "#95afc3"
            self.text(59, y, "â–¶" if selected else "", 15, "#f0d28c")
            self.text(81, y, lesson.name, 20)
            self.text(520, y, status, 15, color, anchor="e")
        if not entries:
            self.text(81, 189, "No entries in this category.", 20, "#95afc3")
            self.text(50, 461, "LEFT / RIGHT TO CHANGE CATEGORY", 16, "#97cbdb")
            return
        lesson = entries[self.selection]
        self.text(568, 198, lesson.name, 22, "#f0d28c")
        self.text(568, 234, lesson.description, 18, width=315)
        self.text(568, 286, f"{lesson.menu} · LV {lesson.level} · {lesson.rp} RP · {lesson.mp} MP", 17, "#97cbdb")
        source = lesson.source or "Reach the required level."
        if source in ANALECTS and self.analects.get(source, 0):
            source += " Â· Found"
        self.text(568, 322, source, 16, "#97cbdb", width=315)
        self.text(568, 378, self.feedback, 17, "#f0d28c", width=315)
        self.text(50, 461, "LEFT / RIGHT OR L1 / R1 PAGE   UP / DOWN ENTRY", 16, "#97cbdb")
        self.text(50, 488, "ENTER / CROSS RESEARCH   ESC / CIRCLE BACK", 16, "#97cbdb")
