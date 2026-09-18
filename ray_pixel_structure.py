"""Structure reconstruction for the two Pixel Art input families.

Repair uses a stable lattice and perceptual labels for placement only. Photo
abstraction uses local iterative superpixel assignments, inspired by Gerstner
et al., Pixelated Image Abstraction (2012); it is not a reproduction of the paper.
"""
from math import gcd
import numpy as np
from scipy.ndimage import gaussian_filter, maximum_filter, median_filter


def native_grid_evidence(rgb):
    """Crisp one-pixel runs indicate existing fine details worth keeping."""
    flat=np.rint(rgb.reshape(-1,3)*255).astype(np.uint8)
    if len(np.unique(flat[::max(1,len(flat)//8192)],axis=0))>256:
        return False
    packed=flat.astype(np.int32)@np.array([65536,256,1])
    if len(np.unique(packed))>256:
        return False
    fractions=[]
    for axis in (0,1):
        change=np.max(np.abs(np.diff(rgb,axis=axis)),axis=-1)>.06
        if axis==0: change=change.T
        gaps=[]
        for row in change:
            gaps.extend(np.diff(np.flatnonzero(row)).tolist())
        fractions.append(np.mean(np.asarray(gaps)==1) if gaps else 0.)
    return max(fractions)>.15


def distinct_palette(palette, source, oklab, nearest_indices):
    """Merge near-duplicate generated shades; never modify a supplied palette."""
    colors=palette.copy()
    if len(colors)<=2: return colors
    lab=oklab(source).reshape(-1,3)
    sample=lab[::max(1,len(lab)//32768)]
    while len(colors)>2:
        p=oklab(colors)
        distance=np.linalg.norm(p[:,None]-p[None],axis=-1)
        np.fill_diagonal(distance,np.inf)
        a,b=np.unravel_index(distance.argmin(),distance.shape)
        if distance[a,b]>=.025: break
        counts=np.bincount(nearest_indices(sample,p),minlength=len(p))
        remove=b if counts[a]>=counts[b] else a
        colors=np.delete(colors,remove,axis=0)
    return colors


def clean_clusters(image, source, palette, oklab, nearest_indices):
    """Consolidate weak isolated shades; retain high-contrast accents and lines."""
    labels=nearest_indices(oklab(image),oklab(palette))
    original=labels.copy(); h,w=labels.shape
    padded=np.pad(original,1,mode='edge')
    neighbors=np.stack([padded[dy:dy+h,dx:dx+w] for dy in range(3) for dx in range(3)
                        if (dy,dx)!=(1,1)],axis=-1)
    own=(neighbors==original[...,None]).sum(-1)
    candidates=np.argwhere(own<=1)
    plab=oklab(palette); source_lab=oklab(source)
    for y,x in candidates:
        options,counts=np.unique(neighbors[y,x],return_counts=True)
        best=int(options[counts.argmax()]); current=original[y,x]
        if counts.max()<5 or np.linalg.norm(plab[best]-plab[current])>.065:
            continue
        before=np.sum((source_lab[y,x]-plab[current])**2)
        after=np.sum((source_lab[y,x]-plab[best])**2)
        if after-before<=.001:
            labels[y,x]=best
    return palette[labels]


def detect_size(rgb, fallback):
    h,w=rgb.shape[:2]
    if min(h,w)<16 or (h*w<=1_500_000 and native_grid_evidence(rgb)):
        return (h,w), 'native detail'
    if np.max(np.std(rgb.reshape(-1,3),axis=0))<1e-5:
        return fallback,'no grid: flat image'
    # Limit analysis memory; sampling/reconstruction still uses the full image.
    image=np.clip(np.rint(rgb*255),0,255).astype(np.uint8)
    if h*w>1_500_000:
        import cv2
        factor=np.sqrt(1_500_000/(h*w))
        image=cv2.resize(image,(round(w*factor),round(h*factor)),interpolation=cv2.INTER_AREA)
    rgba=np.dstack([image,np.full(image.shape[:2],255,np.uint8)])
    try:
        from .ray_pixel_fixer import detect
    except ImportError:
        from ray_pixel_fixer import detect
    # OpenCV's default RNG is per-thread. Run detection in a fresh worker so
    # preceding nodes cannot change its palette initialization, or vice versa.
    from concurrent.futures import ThreadPoolExecutor
    def run_detector():
        import cv2
        cv2.setRNGSeed(42)
        return detect(rgba,mode='full',low_memory=True)
    with ThreadPoolExecutor(max_workers=1) as executor:
        result=executor.submit(run_detector).result()
    # Choose the closest common point on the exact-aspect integer lattice.
    g=gcd(h,w); uh,uw=h//g,w//g
    k=int(np.clip(np.rint((result['rows']/uh+result['cols']/uw)/2),1,g))
    return (uh*k,uw*k),result['consensus']


def cell_geometry(shape,size):
    h,w=shape; rows,cols=size
    # Pixel-center convention matches nearest resampling at fractional scales.
    ix=np.minimum(((np.arange(w)+.5)*cols/w).astype(int),cols-1)
    iy=np.minimum(((np.arange(h)+.5)*rows/h).astype(int),rows-1)
    cell=(iy[:,None]*cols+ix[None,:]).ravel()
    fx=(np.arange(w)+.5)*cols/w-ix
    fy=(np.arange(h)+.5)*rows/h-iy
    weight=((.2+.8*(1-abs(2*fy-1)))[:,None]*(.2+.8*(1-abs(2*fx-1)))[None,:]).ravel()
    return cell,weight


def reconstruct(rgb,size,oklab,make_palette,nearest_indices,seed=0):
    if size==rgb.shape[:2]: return rgb.copy()
    # Structural palette is deliberately independent of the requested output
    # palette. It separates regions without imposing their final colors.
    analysis=median_filter(rgb,size=(3,3,1),mode='nearest') if min(np.array(rgb.shape[:2])/size)>=4 else rgb
    structural=make_palette(analysis,48,seed)
    labels=nearest_indices(oklab(analysis),oklab(structural)).ravel()
    k=len(structural); count=size[0]*size[1]
    cell,weight=cell_geometry(rgb.shape[:2],size)
    votes=np.bincount(cell*k+labels,weights=weight,minlength=count*k).reshape(count,k)
    winners=votes.argmax(1)
    # Correct spatial-center tie break, including even-width cells.
    cy=np.minimum(((np.arange(size[0])+.5)*rgb.shape[0]/size[0]).astype(int),rgb.shape[0]-1)
    cx=np.minimum(((np.arange(size[1])+.5)*rgb.shape[1]/size[1]).astype(int),rgb.shape[1]-1)
    centers=labels.reshape(rgb.shape[:2])[cy[:,None],cx].ravel()
    row=np.arange(count)
    tied=np.isclose(votes[row,centers],votes.max(1),rtol=0,atol=1e-7)
    winners[tied]=centers[tied]
    chosen=(labels==winners[cell])
    # Reject isolated impulse noise: retain center-weighted colors of the
    # winning region, never mix both sides of a silhouette boundary.
    reliable=(np.max(np.abs(rgb-analysis),axis=-1).ravel()<=.18)
    selected=weight**2*chosen*reliable
    empty=np.bincount(cell,weights=selected,minlength=count)<1e-9
    selected=np.where(empty[cell],weight**2*chosen,selected)
    denom=np.maximum(np.bincount(cell,weights=selected,minlength=count),1e-9)
    flat=rgb.reshape(-1,3)
    means=np.stack([np.bincount(cell,weights=flat[:,c]*selected,minlength=count)/denom for c in range(3)],1)
    return means.reshape(*size,3).astype(np.float32)


def abstract_image(rgb,size,oklab,nearest_indices,palette=None):
    """Grid-constrained, saliency-weighted superpixels; output stays rectangular."""
    import cv2
    h,w=size
    if size==rgb.shape[:2]: return rgb.copy()
    ah,aw=min(rgb.shape[0],h*3),min(rgb.shape[1],w*3)
    small=cv2.resize(rgb,(aw,ah),interpolation=cv2.INTER_AREA)
    small=cv2.bilateralFilter(small,5,.065,1.5)
    lab=oklab(small); flat=lab.reshape(-1,3)
    yy,xx=np.indices((ah,aw),dtype=np.float32)
    py=(yy+.5)*h/ah; px=(xx+.5)*w/aw
    base_y=np.minimum(py.astype(int),h-1); base_x=np.minimum(px.astype(int),w-1)
    anchor_y,anchor_x=np.indices((h,w),dtype=np.float32)
    anchor_y=anchor_y.ravel()+.5; anchor_x=anchor_x.ravel()+.5
    cy,cx=anchor_y.copy(),anchor_x.copy()
    initial_y=np.minimum((cy*ah/h).astype(int),ah-1)
    initial_x=np.minimum((cx*aw/w).astype(int),aw-1)
    colors=lab[initial_y,initial_x].copy()
    saliency=np.zeros((ah,aw),np.float32)
    for axis in (0,1):
        delta=np.linalg.norm(np.diff(lab,axis=axis),axis=-1)
        if axis==0: saliency[1:]=np.maximum(saliency[1:],delta)
        else: saliency[:,1:]=np.maximum(saliency[:,1:],delta)
    weights=1+3*np.clip(saliency.ravel()/.12,0,1)
    assignments=(base_y*w+base_x).ravel()
    palette_lab=oklab(palette) if palette is not None else None
    for iteration in range(5):
        prototypes=colors if palette_lab is None else palette_lab[nearest_indices(colors,palette_lab)]
        best=np.full((ah,aw),np.inf,np.float32)
        chosen=assignments.reshape(ah,aw).copy()
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                ids=np.clip(base_y+dy,0,h-1)*w+np.clip(base_x+dx,0,w-1)
                spatial=(py-cy[ids])**2+(px-cx[ids])**2
                cost=((lab-prototypes[ids])**2).sum(-1)+.035*spatial
                update=cost<best
                chosen[update]=ids[update]; best[update]=cost[update]
        assignments=chosen.ravel()
        mass=np.bincount(assignments,weights=weights,minlength=h*w)
        good=mass>0; denom=np.maximum(mass,1)
        colors[good]=np.stack([np.bincount(assignments,weights=flat[:,c]*weights,minlength=h*w)/denom for c in range(3)],1)[good]
        cy[good]=(np.bincount(assignments,weights=py.ravel()*weights,minlength=h*w)/denom)[good]
        cx[good]=(np.bincount(assignments,weights=px.ravel()*weights,minlength=h*w)/denom)[good]
        cy=np.clip(cy,anchor_y-.3,anchor_y+.3)
        cx=np.clip(cx,anchor_x-.3,anchor_x+.3)
    # Color reconstruction is separate from the labels used in assignment.
    source=small.reshape(-1,3)
    output=small[initial_y,initial_x].copy()
    means=np.stack([np.bincount(assignments,weights=source[:,c]*weights,minlength=h*w)/denom for c in range(3)],1)
    output[good]=means[good]
    return output.reshape(h,w,3).astype(np.float32)


def dither_regions(lab):
    """Only coherent source ramps qualify, not flat fields or random texture.

    Compare signed local slopes against their absolute magnitude: noise and
    texture cancel, while a real directional ramp maintains its direction.
    """
    from scipy.ndimage import uniform_filter
    edge = np.zeros(lab.shape[:2], np.float32)
    energy = np.zeros_like(edge)
    coherent = np.zeros_like(edge)
    for axis in (0, 1):
        if lab.shape[axis] < 2:
            continue
        g = np.gradient(lab, axis=axis)
        magnitude = np.linalg.norm(g, axis=-1)
        mean = uniform_filter(g, size=(5, 5, 1), mode='nearest')
        coherent += np.sum(mean*mean, axis=-1)
        energy += uniform_filter(magnitude, size=5, mode='nearest')**2
        d = np.linalg.norm(np.diff(lab, axis=axis), axis=-1)
        if axis == 0:
            edge[1:] = np.maximum(edge[1:], d); edge[:-1] = np.maximum(edge[:-1], d)
        else:
            edge[:, 1:] = np.maximum(edge[:, 1:], d); edge[:, :-1] = np.maximum(edge[:, :-1], d)
    slope = np.sqrt(coherent)
    consistency = slope/np.maximum(np.sqrt(energy), 1e-8)
    residual = np.linalg.norm(lab-gaussian_filter(lab, sigma=(1, 1, 0), mode='nearest'), axis=-1)
    protected = maximum_filter(edge > .045, size=3)
    eligible = (~protected) & (consistency > .8) & (slope > .0015) & (residual < slope*1.2)
    return np.where(eligible, np.clip((slope-.0015)/.003, 0, 1), 0).astype(np.float32)
