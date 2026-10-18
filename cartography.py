"""Observed cartography with licensed artwork and an original fallback."""
import numpy as np
from PIL import Image,ImageDraw
from antique_art import ART_VERSION,render_observed

VERSION='ink-atlas-2-'+ART_VERSION
PAPER=(244,240,228,255)
INK=(72,66,56,255)
FAINT=(167,159,141,255)


def draw_atlas(names,heights,rx=0,rz=0,biomes=None):
    names=np.asarray(names,dtype=object);heights=np.asarray(heights)
    if names.shape!=heights.shape or names.shape not in ((258,258),(288,288)):
        raise ValueError('Cartografia exige superfície 258 ou 288 com halo')
    if biomes is not None and np.asarray(biomes).shape!=names.shape:raise ValueError('Biomas incompatíveis')
    original_names=names;original_heights=heights
    if names.shape==(258,258):
        names=np.pad(names,15,constant_values='minecraft:air')
        heights=np.pad(heights,15,constant_values=-32768)
        if biomes is not None:biomes=np.pad(np.asarray(biomes,dtype=object),15,constant_values='')
    try:return render_observed(names,heights,rx,rz,biomes)
    except (OSError,ValueError) as error:
        import logging
        logging.getLogger(__name__).warning('Arte indisponível; usando símbolos locais: %s',error)
        if original_names.shape==(288,288):
            original_names=original_names[15:-15,15:-15];original_heights=original_heights[15:-15,15:-15]
        return _draw_original_atlas(original_names,original_heights,rx,rz)


def _draw_original_atlas(names,heights,rx=0,rz=0):
    """258² source with one-block halo -> 256² image; symbols on a stable world grid."""
    names=np.asarray(names,dtype=object);heights=np.asarray(heights)
    if names.shape!=(258,258) or heights.shape!=(258,258):raise ValueError('Cartografia exige halo de 258 × 258')
    known=heights!=-32768
    water=np.zeros(names.shape,dtype=bool);trees=water.copy();sand=water.copy()
    # Classify the small local palette, avoiding tens of thousands of string searches per tile.
    for name in set(names.flat):
        if name in ('minecraft:air','minecraft:cave_air','minecraft:void_air',''):known&=names!=name
        elif name in ('minecraft:water','minecraft:flowing_water'):water|=names==name
        elif 'leaves' in name:trees|=names==name
        elif 'sand' in name and 'sandstone' not in name:sand|=names==name
    water&=known
    core=known[1:-1,1:-1];sea=water[1:-1,1:-1]
    pixels=np.zeros((256,256,4),dtype=np.uint8);pixels[core]=PAPER
    # Never draw a coastline against absent data: both adjacent columns must be observed.
    coast=np.zeros((256,256),dtype=bool)
    for a,b in [(np.s_[:-2,1:-1],np.s_[2:,1:-1]),(np.s_[1:-1,:-2],np.s_[1:-1,2:])]:
        for neighbor in (a,b):coast|=core&~sea&known[neighbor]&water[neighbor]
    pixels[coast]=INK
    image=Image.fromarray(pixels);draw=ImageDraw.Draw(image)
    # Icons represent observed land cover / elevation, not predicted biomes or structures.
    for gy in range(-1,17):
        for gx in range(-1,17):
            # The small jitter is coordinate-stable, independent of zoom/tile size.
            wx=rx*16+gx;wz=rz*16+gy;seed=(wx*73856093^wz*19349663)&0xffffffff
            cx=gx*16+8+int(seed%5)-2;cy=gy*16+8+int((seed>>4)%5)-2
            if not 0<=cx<256 or not 0<=cy<256:continue
            block=np.s_[cy-4+1:cy+5+1,cx-4+1:cx+5+1]
            k=known[block];w=water[block];h=heights[block]
            if k.shape!=(9,9) or not k.all():continue
            if w.all():
                if seed%3==0:draw.line([(cx-5,cy),(cx-2,cy-1),(cx+1,cy),(cx+4,cy-1)],fill=FAINT,width=1)
                continue
            if w.any():continue
            if float(np.mean(trees[block]))>.18:
                # Two small trees, distinct from a literal block texture.
                for dx,dy in [(-2,1),(3,-2)]:
                    x=cx+dx;y=cy+dy
                    draw.line([(x,y+4),(x,y-4)],fill=INK)
                    draw.line([(x-3,y+1),(x,y-4),(x+3,y+1)],fill=INK)
                    draw.line([(x-3,y+3),(x,y-1),(x+3,y+3)],fill=INK)
            elif int(h.max())>=100 and (int(h.max())-int(h.min())>=4 or int(h.max())>=140):
                draw.line([(cx-6,cy+4),(cx-1,cy-5),(cx+5,cy+4)],fill=INK)
                draw.line([(cx-1,cy-5),(cx,cy),(cx+3,cy+3)],fill=FAINT)
                draw.line([(cx-4,cy+3),(cx-2,cy),(cx-2,cy+3)],fill=FAINT)
            elif float(np.mean(sand[block]))>.5:
                for dx,dy in [(-3,0),(2,-2),(4,3)]:draw.point((cx+dx,cy+dy),fill=FAINT)
            elif int(h.max())-int(h.min())>=3:
                draw.arc((cx-5,cy-2,cx+5,cy+4),185,340,fill=FAINT)
    return image
