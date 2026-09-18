"""Hue-family-first palette allocation; no material labels or image-specific hues."""
import numpy as np
from sklearn.cluster import KMeans
from threadpoolctl import threadpool_limits


def family_features(rgb, cie_lab):
    lab = cie_lab(rgb)
    chroma = np.linalg.norm(lab[:, 1:], axis=-1)
    # Normalize chroma so shades of a saturated material stay together. Hue is
    # unreliable near gray and black, so taper its influence there.
    radius = (chroma/(chroma+5))*np.clip(lab[:, 0]/15, 0, 1)
    return np.c_[lab[:, 0]*.008, lab[:, 1:]/np.maximum(chroma[:, None], 1e-8)*radius[:, None]]


def family_palette(rgb, count, seed, cie_lab, source_colors=False,
                   protect=True, threshold=90):
    colors, weights = np.unique(np.round(np.clip(rgb.reshape(-1, 3), 0, 1)*255).astype(np.uint8),
                                axis=0, return_counts=True)
    colors = colors.astype(np.float32)/255
    if len(colors) <= count:
        return colors
    lab = cie_lab(colors)
    chroma = np.linalg.norm(lab[:, 1:], axis=-1)
    features = family_features(colors, cie_lab)
    # Coarse chromatic families compare hue independently of saturation. The
    # neutral branch below already separates genuinely weak-chroma colors.
    chromatic = chroma >= 12
    features[:, 0] *= 2
    features[chromatic, 1:] = lab[chromatic, 1:]/chroma[chromatic, None]
    groups = []
    remaining = np.ones(len(colors), bool)
    # A dark backdrop and neutral armor must not compete as merely weak hues.
    if count >= 4:
        for mask in ((lab[:, 0] < 8), (chroma < 12) & (lab[:, 0] >= 8)):
            if weights[mask].sum() >= weights.sum()*.005:
                groups.append(np.flatnonzero(mask))
                remaining[mask] = False
    ids = np.flatnonzero(remaining)
    fit_weights = weights.astype(np.float64)**.7
    with threadpool_limits(limits=1):
        if len(ids):
            k = min(len(ids), max(1, min(8, count-len(groups))))
            fit = KMeans(k, random_state=seed, n_init=3, max_iter=100).fit(features[ids], sample_weight=fit_weights[ids])
            families = [ids[fit.labels_ == i] for i in range(k) if np.any(fit.labels_ == i)]
            # Coalesce nearby shade clusters before distributing extra slots.
            while len(families) > 1:
                centers = np.array([np.average(features[g], axis=0, weights=fit_weights[g]) for g in families])
                distance = ((centers[:, None]-centers)**2).sum(-1)
                np.fill_diagonal(distance, np.inf)
                i, j = np.unravel_index(distance.argmin(), distance.shape)
                if distance[i, j] > .38**2:
                    break
                families[i] = np.r_[families[i], families[j]]
                del families[j]
            groups.extend(families)
        # Every retained family gets one slot first. Only the remainder can buy
        # shading; a small white glint cannot displace the entire gray family.
        slots = np.ones(len(groups), int)
        reserved = []
        if protect and len(groups) < count:
            bright = (lab[:, 0] >= threshold) & (chroma < 12)
            if bright.any():
                reserved.append(np.flatnonzero(bright))
                groups = [g[~bright[g]] for g in groups]
                groups = [g for g in groups if len(g)]
                slots = np.ones(len(groups), int)
        while slots.sum()+len(reserved) < count:
            scores=[]
            for g, n in zip(groups, slots):
                center=np.average(lab[g],axis=0,weights=fit_weights[g])
                spread=np.average(((lab[g]-center)**2).sum(-1),weights=fit_weights[g])
                scores.append(spread*weights[g].sum()**.3/n**2 if len(g)>n else -1)
            if not scores or max(scores) <= 0:
                break
            slots[np.argmax(scores)] += 1
        bands=list(reserved)
        for g, n in zip(groups, slots):
            if n == 1:
                bands.append(g)
            else:
                fit=KMeans(int(n), random_state=seed, n_init=3, max_iter=100).fit(lab[g],sample_weight=fit_weights[g])
                bands.extend(g[fit.labels_==i] for i in range(n) if np.any(fit.labels_==i))
    palette=[]
    for g in bands:
        # Exact darkest background colors deserve their actual frequency vote.
        w=weights[g] if np.max(lab[g,0]) < 8 else fit_weights[g]
        if np.max(lab[g,0]) >= 8 and len(g)>1:
            order=np.argsort(lab[g,0]); cumulative=np.cumsum(w[order])
            level=lab[g[order[np.searchsorted(cumulative,cumulative[-1]*(.90 if np.average(chroma[g], weights=w)<12 else .65))]],0]
            # A representative lit midtone retains a material's base color;
            # averaging its darkest shadows with highlights muddies that base.
            w=w*np.exp(-((lab[g,0]-level)/12)**2)
        center=np.average(colors[g],axis=0,weights=w)
        if source_colors:
            center=colors[g[((lab[g]-cie_lab(center)[0])**2).sum(-1).argmin()]]
        palette.append(center)
    return np.unique(np.asarray(palette,np.float32),axis=0)


def family_indices(rgb, palette, oklab, cie_lab):
    lab, plab = oklab(rgb).reshape(-1,3), oklab(palette)
    f, pf = family_features(rgb, cie_lab), family_features(palette, cie_lab)
    indices=np.empty(len(lab),np.int32)
    for start in range(0,len(lab),4096):
        # Preserve family identity as well as perceived lightness. Plain OkLab
        # nearest assignment can turn neutral armor into olive or brown.
        error=((lab[start:start+4096,None]-plab)**2).sum(-1)
        error += .12*((f[start:start+4096,None]-pf)**2).sum(-1)
        indices[start:start+4096]=error.argmin(-1)
    return indices.reshape(rgb.shape[:-1])



