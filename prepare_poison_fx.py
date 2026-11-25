"""Pack the generated poison-only overlays, keeping a shared foot baseline."""
from pathlib import Path
from PIL import Image
import json
ROOT=Path(__file__).resolve().parent
ART=ROOT/'assets'/'battle'/'fx'/'poison-aura'

def prepare():
 source=Image.open(ART/'source.png').convert('RGBA');frames=[];atlas=Image.new('RGBA',(192,104))
 for i in range(8):
  row,column=divmod(i,4)
  cell=source.crop((round(column*source.width/4),round(row*source.height/2),round((column+1)*source.width/4),round((row+1)*source.height/2)))
  cell=cell.crop((24,35,420,425)).resize((48,52),Image.Resampling.NEAREST)
  pixels=cell.load()
  for y in range(cell.height):
   for x in range(cell.width):
    r,g,b,a=pixels[x,y];pixels[x,y]=(r,g,b,min(a,205)) if a>=64 else (0,0,0,0)
  cell.save(ART/f'{i}.png');frames.append(cell);atlas.alpha_composite(cell,((i%4)*48,(i//4)*52))
 atlas.save(ART/'sheet.png')
 (ART/'manifest.json').write_text(json.dumps({'frame_size':[48,52],'apply_frames':[0,1,2,3],'apply_ms_per_frame':100,'loop_frames':[4,5,6,7],'loop_ms_per_frame':180,'transparent':True},indent=2)+'\n',encoding='utf-8')
 actor=Image.open(ROOT/'assets'/'battle'/'retri-v2.png').convert('RGBA').resize((64,64),Image.Resampling.NEAREST)
 preview=[]
 for index in [0,1,2,3]+[4,5,6,7]*3+[None]:
  frame=Image.new('RGBA',(128,128),'#111b2b');frame.alpha_composite(actor,(32,40))
  if index is not None:frame.alpha_composite(frames[index].resize((96,104),Image.Resampling.NEAREST),(16,4))
  preview.append(frame.convert('RGB').resize((384,384),Image.Resampling.NEAREST))
 preview[0].save(ART/'preview.gif',save_all=True,append_images=preview[1:],duration=[100]*4+[180]*12+[500],loop=0)
 preview[7].save(ART/'preview.png')
if __name__=='__main__':prepare()
