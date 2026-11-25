"""Generate tier-scaled pixel animation sequences for research moves missing shipped art."""
import json
import math
from pathlib import Path
import pygame
from research import LESSONS

ROOT = Path(__file__).resolve().parent
FX = ROOT / 'assets' / 'battle' / 'fx'

def tier_for(lesson):
    return 1 if lesson.level < 6 else 2 if lesson.level < 12 else 3 if lesson.level < 16 else 4

def draw_frame(surface, palette, lesson, tier, frame, count):
    """Anticipation, contact, then dissipating aftermath, centered on the target."""
    t = frame / (count-1)
    charge = min(1, t/.38)
    decay = max(0, (1-t)/.45) if t > .55 else 1
    radius = int((9+9*tier)*charge)
    center = 64
    seed = sum(map(ord, lesson.id))
    core, light, mid, dark, *_ = palette
    def line(color,a,b,w=1): pygame.draw.line(surface,color,a,b,w)
    def ring(r,color=mid,y=64):
        pygame.draw.ellipse(surface,color,(64-r,y-r//3,2*r,max(2,2*r//3)),1)
    def star(x,y,r=3,color=light):
        line(color,(x-r,y),(x+r,y)); line(color,(x,y-r),(x,y+r))
    if t < .3:
        for j in range(3+tier):
            angle=j*math.tau/(3+tier)+seed*.1
            r=int(40-28*charge)
            star(64+int(math.cos(angle)*r),64+int(math.sin(angle)*r),2, dark)
    if lesson.effect == 'physical':
        for j in range(tier+1):
            offset=j*5-tier*2
            reach=int((16+8*tier)*min(1,charge*1.4))
            if .2 < t < .84:
                line(light if j==0 else mid,(64-reach+offset,64+reach),(64+reach+offset,64-reach),2)
                line(core,(64-reach+offset+2,64+reach),(64+reach+offset+2,64-reach))
        if t >= .38:
            ring(int((t-.38)*80),dark,94)
            for j in range(3+tier*2):
                angle=j*math.tau/(3+tier*2)
                r=int(8+(t-.38)*(30+8*tier))
                x=64+int(math.cos(angle)*r);y=64+int(math.sin(angle)*r*.7)
                line(mid,(x,y),(x+int(math.cos(angle)*4),y+int(math.sin(angle)*4)))
        if 'venom' in lesson.id:
            for j in range(4+tier): star(48+j*5,78-int(t*22)+(j%2)*6,2,pygame.Color('#8bce68'))
    elif lesson.effect in ('heal','restore'):
        ring(radius,mid,90-int(t*15))
        for j in range(3+tier*2):
            x=64+int(math.sin(j*2.4+seed)* (10+tier*6)); y=92-int(t*68)+(j%3)*9
            star(x,y,2+tier//2,core if j%2 else light)
        if tier >= 2:
            for j in range(tier): ring(radius-j*5,dark,88-j*17-int(t*10))
        if tier >= 3 and .25 < t < .8:
            line(dark,(52,93),(52,24));line(mid,(76,93),(76,24))
    elif lesson.effect == 'ward':
        extent=int((14+tier*5)*charge)
        pygame.draw.polygon(surface,light,[(64,64-extent),(64+extent,52),(64+extent-4,78),(64,92),(64-extent+4,78),(64-extent,52)],2)
        if tier >= 2: ring(radius,dark,92)
        if tier >= 3: pygame.draw.circle(surface,mid,(64,62),radius+5,1)
        for j in range(2+tier): star(64+int(math.cos(j*2.1+t)*radius),62+int(math.sin(j*2.1+t)*radius),2)
    elif lesson.effect in ('mark','steal'):
        r=max(3,int((18+tier*5)*(1-.5*charge)))
        pygame.draw.ellipse(surface,mid,(64-r*2,64-r,4*r,2*r),1)
        pygame.draw.circle(surface,light,(64,64),max(2,r//3),2)
        for j in range(tier+2):
            angle=j*math.tau/(tier+2)+t
            x=64+int(math.cos(angle)*(r+8));y=64+int(math.sin(angle)*(r+8))
            star(x,y,3)
    else:
        theme = 'wind' if 'gale' in lesson.id else 'wave' if any(x in lesson.id for x in ('flood','tide','mist')) else 'moon' if any(x in lesson.id for x in ('moon','lunar')) else 'fire' if any(x in lesson.id for x in ('fire','flame','ember','flint')) else 'astral'
        if theme == 'wind':
            for j in range(2+tier):
                pygame.draw.arc(surface,light if j%2 else mid,(64-radius,48-radius//2+j*6,2*radius,max(4,radius)),t*3+j, t*3+j+3.4,2)
        elif theme == 'wave':
            for j in range(2+tier):
                points=[(x,64+j*5+int(math.sin(x*.12-t*8+j)* (5+tier*2))) for x in range(64-radius,65+radius,2)]
                if len(points)>1: pygame.draw.lines(surface,light if j==0 else mid,False,points,1)
        elif theme == 'moon':
            pygame.draw.arc(surface,light,(64-radius,64-radius,2*radius,2*radius),.6+t,5.3+t,3)
            star(64,64,4+tier)
        elif theme == 'fire':
            for j in range(3+tier):
                x=64+(j-(2+tier)//2)*7
                pygame.draw.polygon(surface,light if j%2 else mid,[(x-5,85),(x+5,85),(x+int(math.sin(t*12+j)*5),85-int(radius*(.7+(j%3)*.2)))])
        else:
            pygame.draw.circle(surface,mid,(64,64),max(2,radius),1)
            points=[]
            for j in range(4+tier):
                angle=j*math.tau/(4+tier)+seed*.07+t
                x=64+int(math.cos(angle)*radius);y=64+int(math.sin(angle)*radius)
                points.append((x,y));star(x,y,2+tier//2)
            if .3<t<.75: pygame.draw.lines(surface,dark,True,points,1)
        # Signature shapes keep related Seer spells readable as distinct moves.
        if 'echo_glass' in lesson.id and .25 < t < .85:
            for j in range(4):
                x=45+j*12; y=46+(j%2)*15
                pygame.draw.polygon(surface,light,[(x,y-12),(x+5,y),(x,y+13),(x-4,y)],1)
        if 'star_thread' in lesson.id and .25 < t < .85:
            for j in range(3):
                line(light,(28,43+j*13),(100,80-j*13))
                star(40+j*24,50+j*9,3,core)
        if 'final_omen' in lesson.id and .3 < t < .8:
            pygame.draw.circle(surface,dark,(64,64),max(3,radius-5))
            pygame.draw.arc(surface,core,(64-radius,64-radius,2*radius,2*radius),t*4,t*4+4.8,3)
            line(mid,(64,10),(64,118),2)
            line(mid,(20,64),(108,64),1)
        if tier>=3:
            ring(int(radius*1.25),dark,93)
            for j in range(tier):
                angle=j*math.tau/tier+t*2
                star(64+int(math.cos(angle)*(radius+8)),64+int(math.sin(angle)*(radius+8)),3,mid)
    if .38 <= t <= .56:
        star(64,64,4+tier*2,core)
    # Fade without soft edges: retain crisp, progressively sparser pixels.
    if t>.76:
        for y in range(128):
            for x in range(128):
                if (x*3+y*5+seed)%8 >= max(0,int(decay*8)):
                    surface.set_at((x,y),(0,0,0,0))

def prepare():
    from abilities import EXTRA_FX, find_ability
    ramps=json.loads((FX/'stones.json').read_text())
    manifest={}
    for job,lessons in LESSONS.items():
        for lesson in lessons:
            if lesson.id in EXTRA_FX or find_ability(job,lesson.id) is not None:
                continue
            tier=tier_for(lesson); count=10+tier*2
            fixed=lesson.effect in ('heal','restore') or job=='Saint'
            colors=('#efffdf','#b2f6ad','#63d98b','#338866','#204636') if lesson.effect=='heal' else ('#fff8d7','#f6dc91','#dca94f','#987043','#574329')
            palettes={'untinted':colors} if fixed else {stone:tuple(ramps[stone].values()) for stone in ('unattuned','first_stone')}
            manifest[lesson.id]={}
            for stone,colors in palettes.items():
                base=FX/'research_moves'/lesson.id/stone; frames=base/'frames'
                frames.mkdir(parents=True,exist_ok=True)
                palette=[pygame.Color(c) for c in colors]
                for i in range(count):
                    surface=pygame.Surface((128,128),pygame.SRCALPHA)
                    draw_frame(surface,palette,lesson,tier,i,count)
                    pygame.image.save(surface,str(frames/f'{i:02d}.png'))
                timings=[55]*count
                timings[int((count-1)*.4)]=80+tier*15
                path=base/'effect.json'
                meta={'frames':count,'ms_per_frame':timings,'total_ms':sum(timings),'frame_w':128,'frame_h':128,'scale_in_battle':2,'target_center':[64,64],
                      'contact_ms':sum(timings[:int((count-1)*.4)]),'tier':tier,
                      'camera_shake':(tier-1)*2 if lesson.effect in ('physical','arcane') else 0,
                      'camera_pan':(tier-1)*3,
                      'flash_color':'#b4c5dc' if job=='Seer' else '#e0c997' if job=='Saint' else '#9cafbd'}
                path.write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
                manifest[lesson.id][stone]={'json':path.relative_to(FX).as_posix(),'frames_dir':frames.relative_to(FX).as_posix()}
    (FX/'research_moves'/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(f'Built {len(manifest)} tier-scaled move animations.')

if __name__=='__main__': prepare()
