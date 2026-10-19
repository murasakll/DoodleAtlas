"""Masked Lambert hillshade; a one-column halo makes adjacent tiles agree."""
import numpy as np

UNKNOWN=-32768

def hillshade(heights,exaggeration=1.5,intensity=.8):
    h=np.asarray(heights,dtype=float)
    valid=np.isfinite(h)&(h!=UNKNOWN)
    c=h[1:-1,1:-1];cv=valid[1:-1,1:-1]
    left=np.where(valid[1:-1,:-2],h[1:-1,:-2],c)
    right=np.where(valid[1:-1,2:],h[1:-1,2:],c)
    up=np.where(valid[:-2,1:-1],h[:-2,1:-1],c)
    down=np.where(valid[2:,1:-1],h[2:,1:-1],c)
    dx=(right-left)*.5*exaggeration;dz=(down-up)*.5*exaggeration
    # Light from northwest, elevated above the terrain.
    diffuse=np.maximum(0,(dx+dz+1.5)/(np.sqrt(dx*dx+dz*dz+1)*np.sqrt(4.25)))
    baseline=1.5/np.sqrt(4.25)
    return np.where(cv,np.clip(1+intensity*.6*(diffuse-baseline),.5,1.4),1)

def biome_tint(name,biome):
    biome=str(biome or '').lower()
    if any(n in name for n in ('grass','leaves','fern','vine')):
        if any(b in biome for b in ('desert','savanna','badlands')):return np.array([1.12,.95,.68])
        if any(b in biome for b in ('swamp','mangrove')):return np.array([.72,.88,.70])
        if any(b in biome for b in ('taiga','snow','frozen')):return np.array([.76,.98,1.02])
    return np.ones(3)
