"""Frequency-weighted palettes with explicit highlight slots.

Lab/RGB means and chroma/lightness ramps restore the original node's choices.
All strategies share the same hard color budget; supplied palettes bypass this.
"""
import numpy as np
import cv2
from sklearn.cluster import MiniBatchKMeans
from threadpoolctl import threadpool_limits
try:
    from .ray_pixel_families import family_palette
except ImportError:
    from ray_pixel_families import family_palette


def cie_lab(rgb):
    return cv2.cvtColor(np.asarray(rgb, np.float32).reshape(1, -1, 3), cv2.COLOR_RGB2Lab).reshape(-1, 3)


def build_palette(rgb, count, seed, oklab, nearest, strategy="kmeans_lab",
                  protect=True, threshold=90, ramp_levels=4, source_colors=False,
                  allocation="area_preserving"):
    if strategy == "color_families":
        return family_palette(rgb, max(1, int(count)), seed, cie_lab,
                              source_colors, protect, threshold)
    # Build the complete histogram: random pixel subsampling can miss tiny glints.
    colors, inverse, counts = np.unique(np.round(np.clip(rgb.reshape(-1, 3), 0, 1)*255).astype(np.uint8),
                               axis=0, return_inverse=True, return_counts=True)
    colors = colors.astype(np.float32)/255
    weights = counts.astype(np.float64)
    support = np.zeros(len(colors), np.float64)
    if allocation == "area_preserving" and rgb.ndim >= 3:
        frames = rgb.reshape(-1, *rgb.shape[-3:])
        local_weights=[]
        for frame in frames:
            lab = oklab(frame)
            mean = cv2.boxFilter(lab, -1, (5,5), borderType=cv2.BORDER_REFLECT)
            variance = np.maximum(cv2.boxFilter(lab*lab, -1, (5,5), borderType=cv2.BORDER_REFLECT)-mean*mean, 0).sum(-1)
            local_weights.append(np.exp(-variance/.025**2).ravel())
        coherence = np.concatenate(local_weights)
        support = np.bincount(inverse, weights=coherence, minlength=len(colors))
        # Keep a baseline vote for detailed materials, but let coherent fills
        # carry more influence than equally numerous scattered texture colors.
        weights = .2*counts + .8*support
    count = max(1, int(count))
    if len(colors) <= count:
        return colors
    cie = cie_lab(colors)
    reserved = []
    remaining = np.ones(len(colors), bool)
    if protect and count > 1:
        bright = cie[:, 0] >= threshold
        # Keep neutral metal glints separate from warm hair/skin highlights.
        neutral = np.linalg.norm(cie[:, 1:], axis=1) < 12
        groups = [bright & neutral, bright & ~neutral] if count >= 8 else [bright]
        for mask in groups:
            if mask.any():
                center = np.average(colors[mask], axis=0, weights=weights[mask])
                if source_colors or strategy == "oklab_source":
                    group = colors[mask]
                    center = group[np.sum((oklab(group)-oklab(center))**2, axis=1).argmin()]
                reserved.append(center)
                remaining[mask] = False
    if allocation == "area_preserving" and support.sum() > 0 and count >= 8:
        # Broad source-color basins get anchor slots. This is spatial evidence,
        # not semantic recognition of skin, hair, metal, or any particular hue.
        bins = np.minimum((colors*15).astype(int), 15)
        keys = (bins[:,0]*256+bins[:,1]*16+bins[:,2])
        populations = np.bincount(keys, weights=support*remaining, minlength=4096)
        for key in np.argsort(-populations):
            if len(reserved) >= min(8, count//3) or populations[key] < rgb.reshape(-1,3).shape[0]*.002:
                break
            mask=(keys == key)&remaining
            if not mask.any():
                continue
            center=np.average(colors[mask],axis=0,weights=support[mask]+1e-12)
            if reserved and np.min(np.linalg.norm(oklab(np.asarray(reserved))-oklab(center),axis=-1)) < .07:
                continue
            if source_colors or strategy == "oklab_source":
                ids=np.flatnonzero(mask)
                center=colors[ids[np.linalg.norm(oklab(colors[ids])-oklab(center),axis=-1).argmin()]]
            reserved.append(center)
            # Exclude only close shades of this stable fill, never an entire
            # material ramp. Its dark/light shades remain in the fitting budget.
            remaining &= np.linalg.norm(oklab(colors)-oklab(center),axis=-1) > .02
    budget = count-len(reserved)
    c, w = colors[remaining], weights[remaining].astype(np.float64)
    palette = list(reserved)
    if not len(c):
        return np.asarray(palette, np.float32)
    if len(c) <= budget:
        return np.asarray(palette+list(c), np.float32)
    if strategy == "quantize_simple":
        # Original RGB buckets, then clustering if their count exceeds budget.
        step=max(1,255//count)
        bucket=np.floor(np.round(c*255)/step)*step/255
        c, ids=np.unique(bucket.astype(np.float32),axis=0,return_inverse=True)
        w=np.bincount(ids,weights=w,minlength=len(c)) if allocation == "area_preserving" else np.ones(len(c))
        if len(c) <= budget:
            return np.unique(np.asarray(palette+list(c),np.float32),axis=0)
    perceptual = oklab(c)
    features = cie_lab(c) if strategy == "kmeans_lab" else c if strategy in ("kmeans_rgb", "quantize_simple") else perceptual
    clusters = min(len(c), max(1, int(np.ceil(budget/max(2, ramp_levels))))) if strategy == "ramps_oklab" else budget
    features = features[:, 1:] if strategy == "ramps_oklab" else features
    with threadpool_limits(limits=1):
        fit = MiniBatchKMeans(n_clusters=clusters, random_state=seed, n_init=3,
                             batch_size=4096, max_iter=100, reassignment_ratio=0)
        fit.fit(features, sample_weight=w)
        centers = fit.cluster_centers_
        # Histogram-weighted Lloyd refinement avoids minibatch centroid drift.
        for _ in range(6):
            labels = np.empty(len(c), np.int32)
            for start in range(0, len(c), 4096):
                labels[start:start+4096] = ((features[start:start+4096, None]-centers)**2).sum(-1).argmin(-1)
            for i in range(clusters):
                mask = labels == i
                if mask.any():
                    centers[i] = np.average(features[mask], axis=0, weights=w[mask])
    if strategy == "ramps_oklab":
        # Divide each chroma family into weighted lightness bands, then use actual
        # mean source colors. No synthetic out-of-gamut shades or budget overflow.
        allocations = np.full(clusters, budget//clusters)
        populations = np.bincount(labels, weights=w, minlength=clusters)
        allocations[np.argsort(-populations)[:budget % clusters]] += 1
        groups = []
        for i, levels in enumerate(allocations):
            indices = np.flatnonzero(labels == i)
            if not len(indices):
                continue
            indices = indices[np.argsort(perceptual[indices, 0])]
            cumulative = np.cumsum(w[indices])-.5*w[indices]
            bands = np.minimum((cumulative/w[indices].sum()*levels).astype(int), levels-1)
            groups.extend(indices[bands == j] for j in range(levels))
    else:
        groups = [np.flatnonzero(labels == i) for i in range(clusters)]
    for ids in groups:
        if not len(ids):
            continue
        if strategy == "oklab_source" or source_colors:
            center = np.average(perceptual[ids], axis=0, weights=w[ids])
            value = c[ids[np.sum((perceptual[ids]-center)**2, axis=1).argmin()]]
        else:
            value = np.average(c[ids], axis=0, weights=w[ids])
        palette.append(value)
    return np.unique(np.asarray(palette, np.float32), axis=0)
