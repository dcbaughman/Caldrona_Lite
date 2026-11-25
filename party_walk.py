"""Keep the field party on the leader's last walkable tiles."""

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def field_order(roster, preferred):
    active = [member for member in roster if member.get("active", True)]
    if not active:
        return roster[:1]
    standing = [member for member in active if member["hp"] > 0]
    leader = next((member for member in standing if member["name"] == preferred), (standing or active)[0])
    return [leader, *(member for member in active if member is not leader)]


def facing(source, target, default):
    dx, dy = target[0] - source[0], target[1] - source[1]
    if abs(dx) > abs(dy):
        return "right" if dx > 0 else "left"
    if dy:
        return "down" if dy > 0 else "up"
    return default


class PartyTrail:
    """One slot per actor, ordered from the leader back to the last follower."""

    def __init__(self, tile_size):
        self.tile_size = tile_size
        self.area = None
        self.positions = []

    def sample(self, point, direction, count, area, walkable):
        old = self.positions
        if area == self.area and len(old) == count and count:
            x, y = old[0][:2]
            distance = abs(point[0] - x) + abs(point[1] - y)
            if distance == 0:
                return old[1:]
            if distance == self.tile_size and (point[0] == x or point[1] == y):
                trail = [(point[0], point[1], direction)]
                for previous, next_tile in zip(old[1:], old):
                    trail.append((*next_tile[:2], facing(previous, next_tile, previous[2])))
                self.positions = trail
                return trail[1:]

        # On a load, room change, or recruitment, place the line on nearby
        # floor. Prefer the tile behind the leader, even at a dead end.
        self.area = area
        self.positions = [(*point, direction)]
        used = {point}
        dx, dy = DIRECTIONS[direction]
        for _ in range(count - 1):
            x, y, _ = self.positions[-1]
            for ox, oy in ((-dx, -dy), (-dy, dx), (dy, -dx), (dx, dy)):
                neighbor = (x + ox*self.tile_size, y + oy*self.tile_size)
                if neighbor not in used and walkable(*neighbor):
                    self.positions.append((*neighbor, facing(neighbor, (x, y), direction)))
                    used.add(neighbor)
                    break
            else:
                # A single-tile entrance can form the rest of the line as it moves.
                self.positions.append((x, y, direction))
        return self.positions[1:]
