"""Pixel geometry and choreography for the twenty Crescendos."""

from dataclasses import dataclass
from math import atan2, cos, pi, sin, tau
from collections.abc import Callable


def clamp(value):
    return max(0., min(1., value))


def ease(value):
    t = clamp(value)
    return t * t * (3 - 2 * t)


def between(a, b, t):
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def offset(point, dx=0, dy=0):
    return point[0] + dx, point[1] + dy


class Art:
    """Draw on a two-pixel grid with a four-color palette."""

    def __init__(self, canvas, tags, palette, caster, targets, windup, release, landed):
        self.canvas, self.tags = canvas, tags
        self.dark, self.color, self.light, self.white = palette
        self.caster, self.targets = caster, targets
        self.w, self.r, self.landed = windup, release, landed

    @staticmethod
    def coords(points):
        return [2 * round(v / 2) for x, y in points for v in (x, max(16, min(303, y)))]

    def line(self, points, color, width=2):
        self.canvas.create_line(*self.coords(points), fill=color, width=width, tags=self.tags)

    def poly(self, points, color, outline=""):
        self.canvas.create_polygon(*self.coords(points), fill=color, outline=outline,
                                   width=2, tags=self.tags)

    def box(self, point, width, height, color):
        x, y = point
        self.canvas.create_rectangle(*self.coords(((x-width/2, y-height/2), (x+width/2, y+height/2))),
                                     fill=color, outline="", tags=self.tags)

    def ring(self, p, rx, ry, color, width=2, start=0, span=tau):
        if rx < 2 or ry < 2:
            return
        points = [offset(p, rx*cos(start+i*span/24), ry*sin(start+i*span/24)) for i in range(25)]
        self.line(points, color, width)

    def spark(self, p, size, color):
        if size < 2:
            return
        self.box(p, 2*size, 2, color)
        self.box(p, 2, 2*size, color)
        self.box(p, 2, 2, self.white)

    def diamond(self, p, width, height, fill, outline=""):
        self.poly([offset(p, 0, -height), offset(p, width), offset(p, 0, height),
                   offset(p, -width)], fill, outline)

    def slash(self, p, angle, length, width):
        def blade(x, y):
            return offset(p, x*cos(angle) - y*sin(angle), x*sin(angle) + y*cos(angle))

        self.poly([blade(-length*.57, width*.8), blade(-length*.17, -width*.35),
                   blade(length*.35, -width*.55), blade(length*.58, -width*.88),
                   blade(length*.24, width*.65), blade(-length*.24, width)], self.dark)
        self.poly([blade(-length*.48, width*.52), blade(-length*.12, -width*.23),
                   blade(length*.53, -width*.78), blade(length*.17, width*.27)], self.color)
        self.line([blade(-length*.32, width*.40), blade(length*.05, 0),
                   blade(length*.48, -width*.62)], self.light, 4)
        self.line([blade(-length*.10, width*.18), blade(length*.30, -width*.33)], self.white)

    def burst(self, p, age, size, count, *, gravity=0, seed=0):
        if not 0 <= age < 1:
            return
        for i in range(count):
            angle = i * 2.39996 + seed
            reach = size * (.38 + i % 7 * .10) * (1 - (1-age)**2)
            dx, dy = cos(angle)*reach, sin(angle)*reach + gravity*age**2
            length = 2 + 7*(1-age)*(1-i%3/4)
            tip = offset(p, dx, dy)
            tail = offset(tip, -cos(angle)*length, -sin(angle)*length)
            color = (self.light, self.color, self.dark)[(i + int(age*3)) % 3]
            self.line((tip, tail), color, 2 if i % 3 else 4)

    def strand(self, a, b, sag, color, width=2, phase=0):
        points = []
        for i in range(17):
            t = i / 16
            p = between(a, b, t)
            points.append(offset(p, 0, sag*sin(pi*t)*cos(t*pi+phase)))
        self.line(points, color, width)

    def dagger(self, p, angle, scale=1):
        def tip(x, y):
            return offset(p, scale*(x*cos(angle) - y*sin(angle)),
                          scale*(x*sin(angle) + y*cos(angle)))

        self.poly([tip(-13, -3), tip(-2, -3), tip(-2, -6), tip(18, 0),
                   tip(-2, 6), tip(-2, 3), tip(-13, 3)], self.dark, self.color)
        self.poly([tip(0, -4), tip(18, 0), tip(0, 1)], self.light)
        self.line((tip(-2, -7), tip(-2, 7)), self.white)


def rising_edge(a):
    foe = a.targets[0]
    if not a.landed:
        p = offset(a.caster, -32, 21)
        a.slash(p, -1.2 + .55*a.w, 22+45*a.w, 5+a.w*3)
        a.spark(offset(p, -12, -17), 3+5*a.w, a.light)
        if a.w > .57:
            travel = ease((a.w-.57)/.43)
            a.slash(between(p, offset(foe, 0, 35), travel), -.70, 50+60*travel, 10)
    else:
        lift = ease(a.r*3)
        a.ring(offset(foe, 0, 37), 30+132*lift, 5+15*lift, a.color, 3)
        if a.r < .48:
            a.slash(offset(foe, -12+50*lift, 24-104*lift), -1.03,
                    167*(1-a.r), 25*(1-a.r))
        a.burst(offset(foe, 0, -8), a.r, 110, 32, gravity=28)


def quarry_break(a):
    for n, foe in enumerate(a.targets):
        start = offset(a.caster, -19, 31)
        end = offset(foe, 0, 34)
        travel = ease((a.w-.18-n*.06)/.79)
        if not travel:
            continue
        crack = [offset(between(start, end, i*travel/12), 0, (-1)**i*(i%4)*5)
                 for i in range(13)]
        a.line(crack, a.dark, 12)
        a.line(crack, a.color, 4)
        for i in range(3, 13, 3):
            root = crack[i]
            branch = offset(root, -13, (-1)**(i+n)*(18+i%4*5)*travel)
            a.line((root, between(root, branch, .55), offset(branch, 9, 2)), a.light, 2)
        if a.landed:
            a.ring(end, 25+96*ease(a.r), 8+26*a.r, a.color, 4)
            for i in range(12):
                height = (35+i%4*19)*sin(pi*clamp(a.r*1.13+.04))
                stone = offset(end, (i-5.5)*(7+a.r*7), -height)
                size = 5+i%4*2
                a.poly([offset(stone,-size,3), offset(stone,-size+3,-size),
                        offset(stone,4,-size-3), offset(stone,size,1),
                        offset(stone,2,size)], a.dark, a.color)
                a.line((offset(stone,-size+3,-size), offset(stone,4,-size-3)), a.light)
            a.burst(end, a.r, 94, 16, gravity=35, seed=n)


def second_wind(a):
    for n, p in enumerate(a.targets):
        for i in range(22):
            age = (i/22 + a.w*.8 + a.r*1.25 + n*.22) % 1
            theta = i*.57 + a.w*4 + a.r*6
            radius = (23+33*a.w) * (1-.35*age)
            leaf = offset(p, radius*cos(theta), 39-age*(60+60*a.w)-a.r*31 + 12*sin(theta))
            size = (4+i%3)*(1-a.r)*min(1, a.w*4)
            a.diamond(leaf, size*1.65, size, a.color if sin(theta) > 0 else a.dark)
            if i % 4 == 0:
                a.spark(leaf, 4*(1-a.r), a.light)
        a.ring(offset(p, 0, 33), 28+34*a.w+19*a.r, 7+9*a.w, a.color, 3)


def steady_line(a):
    for n, ally in enumerate(a.targets):
        p = offset(ally, -47, 21)
        for i in range(5):
            rise = ease((a.w-.10-i*.095-n*.05)/.32)
            if not rise:
                continue
            b = offset(p, (i-2)*15, (i-2)*4)
            height = rise*(53+(2-abs(2-i))*12) * (1-ease((a.r-.58)/.42))
            if height < 3:
                continue
            panel = [offset(b,-8,6), offset(b,-8,-height+8), offset(b,1,-height),
                     offset(b,8,-height+4), offset(b,8,1)]
            a.poly(panel, a.dark, a.color)
            a.line((panel[1], panel[2], panel[3]), a.light, 3)
            a.box(offset(b, 0, -height*.58), 4, 4, a.light)
            a.line((offset(b,-7,-height*.39), offset(b,7,-height*.39-4)), a.color, 4)
        if a.landed:
            a.burst(offset(p, 0, -25), a.r, 59, 19, gravity=18, seed=n)


def starbreak(a):
    foe = a.targets[0]
    sky = (foe[0]-26, 57)
    if not a.landed:
        dive = ease((a.w-.67)/.33)
        p = between(sky, foe, dive)
        r = 14+29*a.w
        for i in range(3):
            a.ring(p, r+13*i, (r+13*i)*(.38+i*.14), a.color if i else a.light,
                   2, a.w*5+i, pi*1.46)
        for i in range(5):
            theta = tau*i/5-a.w*5
            a.diamond(offset(p, cos(theta)*r, sin(theta)*r*.82), 4, 8, a.light)
        a.diamond(p, 9+9*a.w, 19+11*a.w, a.white, a.light)
        if dive:
            a.strand(sky, p, 15*dive, a.light, 6)
    else:
        how = ease(a.r*1.9)
        for i in range(5):
            theta = tau*i/5-pi/2
            far = offset(foe, cos(theta)*(26+124*how), sin(theta)*(21+80*how))
            a.line((foe, far), a.dark, max(2, 13*(1-a.r)))
            a.diamond(far, (1-a.r)*11, (1-a.r)*17, a.color, a.light)
        a.spark(foe, 41*(1-a.r), a.white)
        a.burst(foe, a.r, 126, 31)


def constellation_sweep(a):
    center = sum(p[0] for p in a.targets)/len(a.targets)
    stars = [offset((center, 76), x, y) for x, y in
             ((-151,16),(-101,-15),(-44,10),(12,-28),(75,-8),(139,11),(179,-23))]
    count = min(len(stars), 1+int(a.w*7.5))
    stars = stars[:count]
    if len(stars) > 1 and a.r < .68:
        a.line(stars, a.dark, 8)
        a.line(stars, a.light, 2)
    for i, p in enumerate(stars):
        if a.r < .8:
            a.spark(p, (5+i%3*3)*(1-a.r), a.color)
        foe = a.targets[i % len(a.targets)]
        dart = ease((a.w-.76+i*.017)/.26 + a.r*2.4)
        if dart:
            point = between(p, foe, dart)
            a.line((between(p, foe, max(0, dart-.32)), point), a.color, 4)
            a.diamond(point, 5*(1-a.r), 12*(1-a.r), a.white)
    if a.landed:
        for i, p in enumerate(a.targets):
            a.ring(offset(p,0,27), 15+87*a.r, 7+19*a.r, a.color, 3)
            a.burst(p, a.r, 88, 22, seed=i)


def starlit_shelter(a):
    for i, p in enumerate(a.targets):
        cap = offset(p, 0, -9)
        rx = (23+47*a.w) * (1-.16*a.r)
        ry = (20+54*a.w) * (1-.20*a.r)
        arc = -pi * (1 + .45*(1-a.w))
        a.ring(cap, rx, ry, a.dark, 9, arc, pi*(.69+.31*a.w))
        a.ring(cap, rx, ry, a.light, 3, arc, pi*(.69+.31*a.w))
        a.ring(offset(p,0,34), rx, 12, a.color, 3)
        crest = offset(cap, 0, -ry)
        a.diamond(crest, 7+6*a.w, 13+9*a.w, a.color, a.white)
        for j in range(6):
            angle = pi + j*pi/5
            tip = offset(cap, rx*cos(angle), ry*sin(angle))
            a.line((crest, tip), a.color, 2)
            a.spark(tip, (3+(j+i)%3)*(1-a.r), a.light)


def clear_sky(a):
    center = (a.caster[0], 68)
    parted = ease(a.w) * 136
    for side in (-1, 1):
        for j in range(5):
            p = offset(center, side*(13+26*j+parted), 5*sin(j*2)+a.r*8)
            a.poly([offset(p,-23,5), offset(p,-18,-3), offset(p,-9,-3), offset(p,-4,-12),
                    offset(p,13,-12), offset(p,18,-5), offset(p,28,-3), offset(p,32,5)],
                   a.dark, a.color)
    a.ring(center, 16+64*a.w, 7+14*a.w, a.light, 3, pi, pi)
    for n, p in enumerate(a.targets):
        for i in range(9):
            rain = clamp((a.w-.54)*1.5+a.r*1.65-i*.083)
            if 0 < rain < 1:
                q = between(offset(center,(i-4)*12+n*27,10), offset(p,(i-4)*8,23), rain)
                a.line((offset(q,0,-14),q), a.color)
                a.diamond(q, 3, 7, a.light)
        if a.landed:
            a.ring(offset(p,0,33), 16+43*a.r, 5+10*a.r, a.light, 2)


def gilded_strike(a):
    foe = a.targets[0]
    origin = offset(a.caster,-33,-17)
    if not a.landed:
        travel = ease((a.w-.54)/.46)
        coin = offset(between(origin, foe, travel), 0, -45*sin(pi*travel))
        for i in range(4, 0, -1):
            p = offset(coin, i*11, -i*3)
            a.ring(p, 3+7*abs(cos(a.w*26+i*.4)), 12, a.dark, 3)
        a.diamond(coin, 4+12*abs(cos(a.w*26)), 17, a.color, a.light)
        a.spark(offset(coin,0,-9), 5, a.white)
    else:
        if a.r < .59:
            a.slash(offset(foe,-8,2), -.59, 155*(1-a.r), 23*(1-a.r))
        if .10 < a.r < .70:
            a.slash(offset(foe,11,1), .66, 144*(1-a.r), 17*(1-a.r))
        for i in range(12):
            tip = offset(foe, cos(i*2.4)*a.r*120, sin(i*2.4)*a.r*90+28*a.r**2)
            a.diamond(tip, (1-a.r)*(4+i%3), (1-a.r)*(7+i%3), a.color, a.light)
        a.burst(foe, a.r, 102, 23, seed=3)


def knife_rain(a):
    for n, p in enumerate(a.targets):
        for i in range(7):
            landing = offset(p,(i-3)*15, (i%3-1)*15+10)
            launch = offset(p, (i-3)*27+115, -121-i%3*9)
            toss = clamp((a.w-.55)*1.5 + a.r*2.1 - i*.093 - n*.03)
            if toss < 1:
                knife = between(launch, landing, toss)
                angle = atan2(landing[1]-launch[1], landing[0]-launch[0])
                if toss:
                    a.line((between(launch, landing, max(0,toss-.19)),knife), a.color, 3)
                a.dagger(knife, angle+(1-ease(a.w*2))*.85, min(1,.35+a.w*1.8))
            elif a.r < .84:
                a.spark(landing, 8*(1-a.r), a.light)
        if a.landed:
            a.burst(p, a.r, 68, 19, gravity=22, seed=n)


def curtain_call(a):
    foe = a.targets[0]
    length = (48+105*a.w)*(1-ease((a.r-.22)/.42))
    for side in (-1,1):
        top = max(23, foe[1]-117)
        edge = foe[0]+side*(100-73*a.w+62*a.r)
        for i in range(6):
            x = edge+side*i*13
            tail = x+side*(16+i*1.4)
            a.poly([(x,top),(x+side*15,top),(tail+side*11,top+length-2*i),
                    (tail,top+length+6-2*i)], a.dark if i%2 else a.color)
            a.line(((x,top+4),(tail,top+length-2*i)), a.color if i%2 else a.light, 2)
    if a.landed:
        if a.r < .42:
            a.slash(foe, -.19, 197*(1-a.r), 21*(1-a.r))
        cape = offset(a.caster,-5,0)
        swing = 24+54*sin(pi*a.r)
        a.ring(cape, swing, 57, a.dark, 13, .55, pi*1.25)
        a.ring(cape, swing+3, 58, a.light, 3, .55, pi*1.25)
        a.burst(foe, a.r, 97, 20)


def lucky_recovery(a):
    center = offset(a.caster, -74, -63)
    pips = ((-4,-5),(4,-5),(-4,0),(4,0),(-4,5),(4,5))
    for i in range(3):
        turn = i*2+a.w*10
        if not a.landed:
            p = offset(center, (i-1)*37+16*sin(turn), 19*cos(turn))
        else:
            p = between(offset(center,(i-1)*41,0), offset(a.caster,-5,-2), ease((a.r-.2)*1.5))
        size = (10+4*abs(cos(turn))) * (1-ease((a.r-.57)/.43))
        if size < 3:
            continue
        x, y = p
        shear = 5*sin(turn)*(1-a.r)
        a.poly([(x-size,y-size),(x+size,y-size+shear),(x+size,y+size),
                (x-size,y+size-shear)], a.dark, a.light)
        a.line(((x-size,y-size),(x+size,y-size+shear)), a.white, 3)
        count = 6 if a.landed else 1+(int(a.w*12)+i*2)%6
        for px, py in pips[:count]:
            a.box(offset(p,px,py), 3, 3, a.color)
    if a.landed:
        a.burst(a.caster, a.r, 77, 29, gravity=-42)
        a.ring(offset(a.caster,0,34), 13+59*a.r, 6+15*a.r, a.color, 3)


def dawn_chorus(a):
    x = sum(p[0] for p in a.targets)/len(a.targets)
    horizon = (x, 130)
    sun = offset(horizon, 0, -54*ease(a.w))
    radius = 9+29*a.w
    if a.r < .83:
        a.ring(sun, radius, radius, a.dark, 13)
        a.ring(sun, radius, radius, a.color, 7)
        a.ring(sun, radius-4, radius-4, a.light, 4)
        for i in range(11):
            theta = pi*i/10+pi
            start = offset(sun, (radius+8)*cos(theta), (radius+8)*sin(theta))
            tip = offset(start, (9+23*a.w)*cos(theta), (9+23*a.w)*sin(theta))
            a.line((start,tip), a.light, 2)
    if a.landed:
        for i, p in enumerate(a.targets):
            glow = offset(p,0,33)
            a.poly([offset(sun,-7,13),offset(glow,-24,0),offset(glow,24,0),offset(sun,7,13)],
                   a.dark, a.color)
            for j in range(7):
                beam = offset(glow,(j-3)*8,-a.r*(33+j%4*23))
                a.spark(beam, (1-a.r)*7, a.light)
            a.ring(glow, 24+45*a.r, 7+13*a.r, a.color, 3)


def radiant_verdict(a):
    foe = a.targets[0]
    seal = (foe[0],47)
    if not a.landed:
        a.diamond(seal, 10+24*a.w, 10+17*a.w, a.dark, a.color)
        a.spark(seal, 9+21*a.w, a.light)
        a.line((offset(seal,0,18),offset(foe,0,-23)), a.color, 2)
        a.ring(offset(foe,0,34), 20+50*a.w, 7+12*a.w, a.light, 3)
    else:
        width = 56*(1-ease(a.r*.95))
        if width > 3:
            bottom = offset(foe, 0, 31)
            for w, color in ((width,a.dark),(width*.67,a.color),(width*.32,a.light),(width*.12,a.white)):
                a.poly([offset(seal,-w),offset(seal,w),offset(bottom,w*.58),offset(bottom,-w*.58)],
                       color)
            a.line((offset(foe,-width*1.3,-41),offset(foe,width*1.3,-41)), a.light, 6)
        a.burst(offset(foe,0,28), a.r, 121, 36, gravity=-24)
        a.ring(offset(foe,0,34), 26+129*a.r, 6+26*a.r, a.light, 4)


def sanctuary_bell(a):
    x = sum(p[0] for p in a.targets)/len(a.targets)
    p = (x + sin(a.w*4*pi+a.r*12)*25*(1-a.r), 72)
    if a.r < .82:
        profile = ((-42,25),(-34,17),(-29,-8),(-20,-25),(-11,-30),(11,-30),(20,-25),
                   (29,-8),(34,17),(42,25),(31,32),(-31,32))
        a.poly([offset(p,dx,dy) for dx,dy in profile], a.dark, a.light)
        a.line([offset(p,dx,dy) for dx,dy in ((-33,19),(-23,0),(-15,-17),(-6,-22))], a.color, 6)
        a.line((offset(p,-39,25),offset(p,40,25)), a.white, 4)
        a.diamond(offset(p,0,33), 7, 10, a.color, a.light)
    for n, ally in enumerate(a.targets):
        for delay in (0,.16,.32):
            wave = (a.r-delay-n*.035)*1.45
            if a.landed and 0 <= wave < 1:
                a.ring(offset(ally,0,32), 13+89*wave, 5+19*wave, a.light if delay == 0 else a.color, 3)
        if a.landed:
            a.burst(offset(ally,0,14), a.r, 63, 14, gravity=-30, seed=n)


def last_light(a):
    for i, p in enumerate(a.targets):
        if not a.landed:
            ember = offset(p, -9+8*sin(a.w*9+i), 21-45*ease(a.w))
            a.ring(offset(p,0,34), 8+43*a.w, 4+10*a.w, a.color, 2, a.w*4, pi*1.7)
            a.diamond(ember, 3+7*a.w, 6+11*a.w, a.light, a.white)
            a.spark(ember, 5+7*a.w, a.light)
        else:
            rise = ease(a.r*1.8)
            crown = offset(p, 0, -13-71*rise)
            ground = offset(p,0,38)
            width = 15*(1-ease((a.r-.34)/.66))
            a.poly([offset(ground,-width,0),offset(crown,-width*.37,0),
                    offset(crown,width*.37,0),offset(ground,width,0)], a.color)
            a.line((ground,crown), a.white, max(2,width/3))
            for side in (-1,1):
                for j in range(6):
                    span = (25+j*9)*rise*(1-.56*a.r)
                    tail = offset(p, side*span, -22-j*12-18*rise)
                    a.poly([offset(p,0,10-j*5),offset(tail,-side*13,8),tail,
                            offset(p,side*11,17-j*4)], a.light if j%2 else a.color)
                    a.spark(tail, 4*(1-a.r), a.white)
            a.burst(crown, a.r, 75, 23, gravity=-29, seed=i)


def onyx_sever(a):
    hand = offset(a.caster,-24,-11)
    shadow = offset(a.targets[0],0,33)
    if not a.landed:
        reach = ease((a.w-.13)/.64)
        tip = between(hand,shadow,reach)
        sag = (1-a.w)*90
        a.strand(hand,tip,sag,a.dark,6,a.w*3)
        a.strand(hand,tip,sag,a.light,2,a.w*3)
        a.spark(tip,6,a.white)
        a.ring(shadow, 10+23*reach, 6+5*reach, a.color, 3)
    else:
        split = between(hand,shadow,.47)
        a.strand(hand,offset(split,a.r*128,-56*a.r),47*a.r,a.color,3,a.r*6)
        a.strand(shadow,offset(split,-a.r*169,-77*a.r),-95*a.r,a.light,4,a.r*9)
        if a.r < .61:
            a.slash(offset(shadow,0,-37),-1.34,133*(1-a.r),24*(1-a.r))
        a.burst(shadow, a.r, 111, 29, gravity=-38)


def black_silk_storm(a):
    for n, p in enumerate(a.targets):
        hub = offset(p,0,30)
        size = 23+82*a.w
        points = [offset(hub,cos(i*tau/9)*size, sin(i*tau/9)*size*.50) for i in range(9)]
        for i, tip in enumerate(points):
            reached = ease((a.w-.06*i)/.41)
            if reached:
                a.line((hub,between(hub,tip,reached)), a.dark, 6)
                a.line((hub,between(hub,tip,reached)), a.light, 2)
        for ring in (.30,.52,.76,1.):
            count = min(9, int(a.w*13-ring*3))
            if count > 1:
                loop = [between(hub,pin,ring) for pin in points[:count]]
                if count == len(points):
                    loop.append(loop[0])
                tension = sin(pi*a.r)*28
                a.line([offset(knot,0,-tension) for knot in loop], a.color, 4)
                for knot in loop[::2]:
                    a.spark(offset(knot,0,-tension), 4, a.light)
        if a.landed:
            a.burst(offset(hub,0,-39), a.r, 92, 27, gravity=-20, seed=n)
    if len(a.targets) > 1:
        for p, q in zip(a.targets,a.targets[1:]):
            a.strand(offset(p,-61,20),offset(q,59,31),35*a.w,a.dark,7)
            a.strand(offset(p,-61,20),offset(q,59,31),35*a.w,a.light,2)


def shadow_canopy(a):
    for n, p in enumerate(a.targets):
        crest = offset(p, 0, -24-37*a.w)
        radius = 13+65*a.w
        ribs = [offset(p, radius*cos(pi*j/8), -9+17*sin(pi*j/8)) for j in range(9)]
        for j, tip in enumerate(ribs):
            load = ease((a.w-.07*j)/.30)
            if load <= 0:
                continue
            end = between(crest,tip,load)
            if j:
                left = between(crest,ribs[j-1],load)
                a.poly([crest,between(crest,left,.57),left,end,between(crest,end,.57)],
                       a.dark if j%2 else a.color)
            a.strand(crest,end,-21*load,a.light,2)
            tail = offset(end, 4*sin(a.r*8+j+n), 6+j%3*6)
            a.line((end,tail),a.color,3)
            a.diamond(tail,3,6*(1-.7*a.r),a.light)
        a.diamond(crest, 6, 13, a.dark, a.white)


def silken_reprieve(a):
    for n, p in enumerate(a.targets):
        for i in range(13):
            age = clamp((a.w-.045*i)/.35)
            if not age:
                continue
            if not a.landed or a.r < .48:
                y = (6-i)*5
                spin = a.w*8+i*.36+n
                radius = (13+22*sin(pi*(i+1)/14))*age*(1+.34*a.r)
                a.ring(offset(p,0,y), radius, 6+4*sin(spin), a.color if i%2 else a.light,
                       2, spin, pi*(.82+.18*age))
            if a.landed:
                r = clamp(a.r-i*.018)
                theta = i*2.4+a.r*3+n
                plume = offset(p, (21+r*57)*cos(theta), -12-r*74+16*sin(theta))
                size = (2+i%3*2)*(1-a.r)
                a.diamond(plume, 1.3*size, 2.3*size, a.light)
                a.line((plume,offset(plume,3,9)),a.color)


@dataclass(frozen=True)
class Cue:
    draw: Callable[[Art], None]
    duration_ms: int
    contact_ms: int
    palette: tuple[str, str, str, str]
    shake: int = 0
    lunge: int = 0


CUES = {
    "rising_edge": Cue(rising_edge, 2060, 880, ("#263d58","#679fce","#c1e9ff","#f6ffff"), 9, 48),
    "quarry_break": Cue(quarry_break, 2420, 1140, ("#442a2d","#bb673e","#efa86f","#ffe8ba"), 14, 10),
    "second_wind": Cue(second_wind, 2120, 950, ("#16404b","#41aa91","#8cedc0","#efffe1")),
    "steady_line": Cue(steady_line, 2020, 890, ("#40414b","#8f8071","#e2c29a","#fff0d0"), 4),
    "starbreak": Cue(starbreak, 2480, 1190, ("#20386b","#568ee1","#a5dffc","#ecfcff"), 9),
    "constellation_sweep": Cue(constellation_sweep, 2530, 1230, ("#362859","#8667d7","#c9a7ff","#f8efff"), 6),
    "starlit_shelter": Cue(starlit_shelter, 2160, 980, ("#203a5a","#588ac7","#a5e8fa","#f3fdff")),
    "clear_sky": Cue(clear_sky, 2210, 950, ("#3e5862","#7cbbc5","#bceff0","#f2ffff")),
    "gilded_strike": Cue(gilded_strike, 2040, 920, ("#502f23","#c1842f","#ffda73","#fff1b6"), 8, 42),
    "knife_rain": Cue(knife_rain, 2280, 990, ("#352645","#a06498","#e3a9c5","#fff0ec"), 6, 12),
    "curtain_call": Cue(curtain_call, 2410, 1040, ("#471c2e","#a94058","#f28687","#ffe1ca"), 8, 32),
    "lucky_recovery": Cue(lucky_recovery, 2170, 960, ("#17493d","#48b573","#afebaa","#f7ffe4")),
    "dawn_chorus": Cue(dawn_chorus, 2420, 1100, ("#51372f","#da9855","#ffd98a","#fffae3")),
    "radiant_verdict": Cue(radiant_verdict, 2450, 1130, ("#563520","#d88a39","#ffd36d","#fffce7"), 12),
    "sanctuary_bell": Cue(sanctuary_bell, 2560, 1090, ("#42322b","#b58355","#ffcc82","#fff7c8"), 4),
    "last_light": Cue(last_light, 2650, 1130, ("#5b3b3c","#d49575","#fbd1a0","#fff9e7")),
    "onyx_sever": Cue(onyx_sever, 2240, 1060, ("#110e1b","#654779","#ad96c3","#f1e9ff"), 9, 22),
    "black_silk_storm": Cue(black_silk_storm, 2500, 1120, ("#130e1d","#604975","#abb1cc","#eeeffc"), 7),
    "shadow_canopy": Cue(shadow_canopy, 2280, 1010, ("#151321","#433b63","#aa92c7","#e9dff5")),
    "silken_reprieve": Cue(silken_reprieve, 2380, 1030, ("#2a243e","#765c9b","#c7aedf","#f6efff")),
}

# Placeholder cues for the new Crescendos (movesets.md): existing choreography,
# recolored palettes only. Replace when dedicated Crescendo art is drawn.
from dataclasses import replace as _replace_cue

_PLACEHOLDER_CUES = {
    "flood_tide": ("second_wind", ("#123a52","#3f8fc4","#93d6f2","#eafaff")),
    "riptide": ("constellation_sweep", ("#13324a","#3d7fb8","#8fcbe9","#e8f8ff")),
    "slack_water": ("clear_sky", ("#244a5a","#5fa7c2","#b4e7f2","#f1ffff")),
    "return_tide": ("second_wind", ("#183c55","#4b93c0","#a2dcef","#f0fcff")),
    "lid_crack": ("onyx_sever", ("#14111a","#5c4a63","#b19bb5","#f3eaf5")),
    "mourning_bell": ("black_silk_storm", ("#17121c","#5a4864","#aa9bb8","#efe8f7")),
    "ashen_vespers": ("shadow_canopy", ("#1a1820","#4f4859","#a99fb5","#ece6f2")),
    "nox_sepulta": ("shadow_canopy", ("#100d16","#3d3350","#9b88b8","#e6dcf5")),
}
for _name, (_source, _palette) in _PLACEHOLDER_CUES.items():
    CUES[_name] = _replace_cue(CUES[_source], palette=_palette)
