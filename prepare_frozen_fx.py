"""Prepare the generated ice-only overlay; game runtime uses Tk, not Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw
import json
ROOT=Path(__file__).resolve().parent
ART=ROOT/'assets'/'battle'/'fx'/'frozen-shell'

def prepare():
    source=Image.open(ART/'source.png').convert('RGBA')
    atlas=Image.new('RGBA',(176,96));frames=[]
    for i in range(8):
        row,column=divmod(i,4)
        cell=source.crop((round(column*source.width/4)+4,round(row*source.height/2)+4,
                          round((column+1)*source.width/4)-4,round((row+1)*source.height/2)-4))
        # One shared crop is essential: growing shards must not be stretched
        # to the same height as the final shell.
        cell=cell.crop((20,30,414,402)).resize((44,48),Image.Resampling.NEAREST)
        pixels=[]
        for r,g,b,a in cell.getdata():
            if a<64:pixels.append((0,0,0,0))
            else:pixels.append((r,g,b,min(a,220) if min(r,g,b)>195 else round(a*.55)))
        cell.putdata(pixels)
        frame=Image.new('RGBA',(44,48))
        if 3<=i<=6:
            ImageDraw.Draw(frame).polygon([(22,6),(32,15),(32,36),(22,43),(12,36),(12,15)],fill=(85,164,219,42 if i==6 else 65))
        frame.alpha_composite(cell)
        frame.save(ART/f'{i}.png');frames.append(frame)
        atlas.alpha_composite(frame,((i%4)*44,(i//4)*48))
    atlas.save(ART/'sheet.png')
    (ART/'manifest.json').write_text(json.dumps({'frame_size':[44,48],'pop_frames':[0,1,2,3],
        'pop_ms_per_frame':80,'hold_frames':[3,4,5,4],'hold_ms_per_frame':280,
        'thaw_frames':[6,7],'thaw_ms_per_frame':140,'transparent':True},indent=2)+'\n',encoding='utf-8')
    actor=Image.open(ROOT/'assets'/'battle'/'retri-v2.png').convert('RGBA').resize((64,64),Image.Resampling.NEAREST)
    sequence=[0,1,2,3,4,5,4,3,4,5,6,7,None];preview=[]
    for index in sequence:
        image=Image.new('RGBA',(128,128),'#111b2b');image.alpha_composite(actor,(32,40))
        if index is not None:image.alpha_composite(frames[index].resize((88,96),Image.Resampling.NEAREST),(20,12))
        preview.append(image.convert('RGB').resize((384,384),Image.Resampling.NEAREST))
    preview[0].save(ART/'preview.gif',save_all=True,append_images=preview[1:],duration=[80]*4+[280]*6+[140]*2+[500],loop=0)
    preview[5].save(ART/'preview.png')

if __name__=='__main__':prepare()
