"""Export the generated mount art at native scale; this does not enable mounts in play."""
from pathlib import Path
import json
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parent
ART=ROOT/'assets'/'mounts'/'sheep-bird'
DIRECTIONS=('down','left','right','up')

def prepare():
    source=Image.open(ART/'source.png').convert('RGBA')
    cells=[]
    for row in range(4):
        frames=[]
        for column in range(3):
            # Exclude the generated sheet separators, then preserve the actual alpha.
            cell=source.crop((round(column*source.width/3)+8,round(row*source.height/4)+8,
                              round((column+1)*source.width/3)-8,round((row+1)*source.height/4)-8))
            cell.putalpha(cell.getchannel('A').point(lambda a:255 if a>=128 else 0))
            bounds=cell.getbbox()
            frames.append(cell.crop(bounds))
        cells.append(frames)
    scale=26/max(im.height for row in cells for im in row)
    atlas=Image.new('RGBA',(96,128))
    manifest={'id':'sheep_bird_mount','display_name':'Sheep-Bird Mount',
              'status':'asset_only','enabled':False,'riding_implemented':False,
              'frame_size':[32,32],'foot_anchor':[16,30],
              'sprite_sheet':'assets/mounts/sheep-bird/idle-sheet.png',
              'idle_frame_durations_ms':[650,250,150],
              'directions':{},
              'integration_notes':'Saddle anchors are draft attachment points. Walking, running, rider overlays, collision, spawning, and mount controls are future work.'}
    for row,(direction,frames) in enumerate(zip(DIRECTIONS,cells)):
        folder=ART/direction;folder.mkdir(exist_ok=True)
        paths=[]
        for column,cell in enumerate(frames):
            size=(round(cell.width*scale),round(cell.height*scale))
            sprite=cell.resize(size,Image.Resampling.NEAREST)
            frame=Image.new('RGBA',(32,32))
            frame.alpha_composite(sprite,((32-size[0])//2,30-size[1]))
            frame.save(folder/f'idle-{column}.png')
            atlas.alpha_composite(frame,(column*32,row*32))
            paths.append(f'assets/mounts/sheep-bird/{direction}/idle-{column}.png')
        manifest['directions'][direction]={'row':row,'idle_frames':paths,
            'saddle_anchor':[17,16] if direction=='left' else [15,16] if direction=='right' else [16,16]}
    atlas.save(ART/'idle-sheet.png')
    (ART/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    preview=Image.new('RGB',(432,600),'#142033');draw=ImageDraw.Draw(preview)
    for row,direction in enumerate(DIRECTIONS):
        draw.text((12,row*148+8),direction.upper(),fill='#eddcb6')
        for column in range(3):
            frame=Image.open(ART/direction/f'idle-{column}.png').resize((128,128),Image.Resampling.NEAREST)
            preview.paste(frame,(column*140+6,row*148+22),frame)
    preview.save(ART/'preview.png')
    animation=[]
    for column in range(3):
        image=Image.new('RGB',(512,160),'#142033');d=ImageDraw.Draw(image)
        for i,direction in enumerate(DIRECTIONS):
            d.text((i*128+8,8),direction.upper(),fill='#eddcb6')
            frame=Image.open(ART/direction/f'idle-{column}.png').resize((128,128),Image.Resampling.NEAREST)
            image.paste(frame,(i*128,28),frame)
        animation.append(image)
    animation[0].save(ART/'idle-preview.gif',save_all=True,append_images=animation[1:],duration=[650,250,150],loop=0)
    print('Exported 12 native 32x32 RGBA mount frames, atlas, manifest, and previews.')

if __name__=='__main__':prepare()
