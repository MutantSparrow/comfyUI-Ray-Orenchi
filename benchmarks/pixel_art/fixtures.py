"""Independent procedural fixtures with uniformly distributed degradations."""
from pathlib import Path
import io
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def originals():
    palette = ['#172333','#31485c','#698596','#b5d1cf','#fff0c4', '#a65742',
               '#e0a355','#6f9951','#365837','#532f42','#a07594','#f1d69f']
    sprite = Image.new('RGB', (48,32), palette[0]); d=ImageDraw.Draw(sprite)
    d.ellipse((9,26,38,30), fill=palette[1]); d.rectangle((17,16,31,26),fill=palette[5])
    d.rectangle((15,5,32,17),fill=palette[2]); d.rectangle((17,7,30,15),fill=palette[3])
    d.rectangle((18,10,22,12),fill=palette[0]); d.point((21,10),fill=palette[4])
    d.rectangle((26,10,29,12),fill=palette[0]); d.point((28,10),fill=palette[4])
    d.line((21,15,27,15),fill=palette[5]); d.rectangle((19,19,29,23),fill=palette[6])
    d.line((16,17,10,23,12,25),fill=palette[3],width=2)
    d.line((32,17,37,23,40,18),fill=palette[3],width=2)
    d.line((20,26,18,29,14,29),fill=palette[2],width=2)
    d.line((29,26,31,29,35,29),fill=palette[2],width=2)
    tiles = Image.new('RGB',(64,48),palette[3]); d=ImageDraw.Draw(tiles)
    d.ellipse((32,3,40,11),fill=palette[4]); d.polygon([(0,22),(12,6),(27,22)],fill=palette[2])
    d.polygon([(18,22),(33,12),(47,23)],fill=palette[1]); d.rectangle((0,23,47,31),fill=palette[8])
    d.rectangle((9,18,21,28),fill=palette[6]); d.polygon([(7,18),(15,12),(23,18)],fill=palette[5])
    d.rectangle((14,22,17,28),fill=palette[0]); d.rectangle((10,20,12,22),fill=palette[4])
    for x in [29,36,44]:
        d.line((x,22,x,29),fill=palette[5]); d.polygon([(x-4,23),(x,15),(x+4,23)],fill=palette[7])
    details=Image.new('RGB',(48,32),palette[0]); d=ImageDraw.Draw(details)
    for j,color in enumerate(palette[1:]):
        x=(j%6)*8; y=(j//6)*16
        d.rectangle((x+1,y+2,x+6,y+12),outline=color)
        d.line((x+1,y+12,x+6,y+2),fill=color)
        d.point((x+4,y+7),fill=palette[4])
    # Fine intentional dithering is part of this original, not added damage.
    for y in range(18,30):
        for x in range(33,47):
            d.point((x,y),fill=palette[(x+y)%2+1])
    return {'sprite':sprite,'landscape':tiles,'thin_details':details.crop((0,0,40,24))}


def distort(image, kind, seed):
    rng=np.random.default_rng(seed)
    if kind=='native': return image.copy()
    scale=6.25 if kind in ('fractional','bilinear') else 6
    size=tuple(round(v*scale) for v in image.size)
    out=image.resize(size,Image.Resampling.BILINEAR if kind=='bilinear' else Image.Resampling.NEAREST)
    if kind=='blur': out=out.filter(ImageFilter.GaussianBlur(1.0))
    if kind=='jpeg':
        stream=io.BytesIO(); out.save(stream,format='JPEG',quality=55); stream.seek(0); out=Image.open(stream).convert('RGB')
    if kind=='noise':
        a=np.array(out,dtype=float)+rng.normal(0,12,(*np.array(out).shape,))
        out=Image.fromarray(np.clip(np.rint(a),0,255).astype(np.uint8))
    if kind=='uneven':
        a=np.array(out); original=np.array(image)
        xs=np.arange(image.width+1)*6; ys=np.arange(image.height+1)*6
        xs[1:-1]+=rng.integers(-1,2,image.width-1); ys[1:-1]+=rng.integers(-1,2,image.height-1)
        for y in range(image.height):
            for x in range(image.width): a[ys[y]:ys[y+1],xs[x]:xs[x+1]]=original[y,x]
        out=Image.fromarray(a)
    return out


def write_fixtures(root):
    root=Path(root); root.mkdir(exist_ok=True,parents=True)
    jobs=[]
    for index,(name,original) in enumerate(originals().items()):
        original.save(root/f'{name}-original.png')
        for kind in ['native','integer','fractional','bilinear','blur','jpeg','noise','uneven']:
            key=f'{name}-{kind}'; image=distort(original,kind,index+123)
            path=root/f'{key}.png'; image.save(path)
            jobs.append({'id':key,'input':str(path.resolve()),'original':str((root/f'{name}-original.png').resolve()),
                         'size':original.size,'kind':kind})
    return jobs
