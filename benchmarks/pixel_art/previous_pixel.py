"""Grid-aware pixel sampling, perceptual palettes and palette-constrained effects.

The edge-profile / cell-voting approach is inspired by Spritefusion Pixel Snapper
(https://github.com/Hugo-Dz/spritefusion-pixel-snapper). Implementation is independent.
"""
from math import gcd
import logging

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.cluster import MiniBatchKMeans
from threadpoolctl import threadpool_limits
try:
    from ._common import normalize_image
except ImportError:
    from _common import normalize_image


def linear_rgb(rgb):
    return np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)


def oklab(rgb):
    x = linear_rgb(np.asarray(rgb, dtype=np.float32))
    lms = x @ np.array([[.4122214708, .2119034982, .0883024619],
                        [.5363325363, .6806995451, .2817188376],
                        [.0514459929, .1073969566, .6299787005]], dtype=np.float32)
    return np.cbrt(lms) @ np.array([[.2104542553, 1.9779984951, .0259040371],
                                  [.7936177850, -2.4285922050, .7827717662],
                                  [-.0040720468, .4505937099, -.8086757660]], dtype=np.float32)


def exact_size(h, w, longest):
    """All integer resolutions on the original aspect-ratio lattice; never crop."""
    g = gcd(h, w)
    unit_h, unit_w = h // g, w // g
    k = max(1, min(g, int(np.floor(longest / max(unit_h, unit_w) + .5))))
    return unit_h * k, unit_w * k


def nearest_indices(colors, palette_lab):
    flat = colors.reshape(-1, 3)
    out = np.empty(len(flat), dtype=np.int32)
    for start in range(0, len(flat), 4096):
        d = ((flat[start:start + 4096, None] - palette_lab) ** 2).sum(-1)
        out[start:start + len(d)] = d.argmin(-1)
    return out.reshape(colors.shape[:-1])


def make_palette(rgb, count, seed, source_colors=False):
    # Bound fitting cost without allowing artificial dither colors into the fit.
    flat = rgb.reshape(-1, 3)
    rng = np.random.default_rng(seed)
    if len(flat) > 131072:
        flat = flat[rng.choice(len(flat), 131072, replace=False)]
    colors, weights = np.unique(np.round(flat * 255).astype(np.uint8), axis=0, return_counts=True)
    colors = colors.astype(np.float32) / 255
    if len(colors) <= count:
        return colors
    lab = oklab(colors)
    with threadpool_limits(limits=1):
        fit = MiniBatchKMeans(n_clusters=count, random_state=seed, n_init=3,
                             batch_size=4096, max_iter=80, reassignment_ratio=0)
        fit.fit(lab, sample_weight=weights.astype(np.float64))
    # Source-color representatives avoid out-of-gamut centroids; refit each
    # cluster's perceptual center with the full histogram before selecting it.
    labels = nearest_indices(lab, fit.cluster_centers_)
    palette = []
    for i in range(count):
        mask = labels == i
        if not mask.any():
            continue
        group = colors[mask]
        if source_colors:
            center = fit.cluster_centers_[i]
        else:
            center = np.average(lab[mask], axis=0, weights=weights[mask])
        palette.append(group[((oklab(group) - center) ** 2).sum(-1).argmin()])
    return np.unique(np.asarray(palette, dtype=np.float32), axis=0)


def edge_profiles(rgb):
    lab = oklab(rgb)
    return (np.linalg.norm(np.diff(lab, axis=1), axis=-1).mean(0),
            np.linalg.norm(np.diff(lab, axis=0), axis=-1).mean(1))


def estimate_grid(profile, max_step=64):
    if len(profile) < 8 or profile.max() < 1e-5:
        return None
    # Sparse repeated edge peaks are evidence of a grid; broad photographic
    # texture is deliberately rejected. Favor the smallest convincing period.
    p = np.maximum(profile - np.median(profile), 0)
    peaks = np.flatnonzero((p > max(p.max() * .15, p.mean() * 1.4)) &
                          (p >= np.r_[0, p[:-1]]) & (p > np.r_[p[1:], 0])) + 1
    if len(peaks) < 4:
        return None
    gaps = np.diff(peaks)
    for step in range(2, min(max_step, len(profile) // 4) + 1):
        phase = np.exp(2j * np.pi * peaks / step)
        coherence = abs(np.average(phase, weights=p[peaks - 1]))
        near = np.mean(np.abs(gaps - step) <= max(.5, step * .15))
        if coherence > .82 and near > .25:
            return step
    return None


def grid_cuts(profile, length, cells):
    cuts = np.rint(np.linspace(0, length, cells + 1)).astype(int)
    step = length / cells
    radius = int(step * .35)
    if radius < 1:
        return cuts
    for i in range(1, cells):
        center = cuts[i]
        lo, hi = max(cuts[i - 1] + 1, center - radius), min(length - (cells - i), center + radius)
        candidates = np.arange(lo, hi + 1)
        values = profile[candidates - 1]
        # Move a cut only when there is an actual edge, never on a flat tie.
        if values.max() > max(profile.mean() * 1.5, 1e-5):
            score = values - values.max() * .1 * abs(candidates - center) / max(radius, 1)
            cuts[i] = candidates[score.argmax()]
    return cuts


def sample_image(rgb, size, sampling):
    h, w = size
    if size == rgb.shape[:2]:
        return rgb.copy()
    if sampling == "nearest":
        y = np.minimum((np.arange(h) + .5) * rgb.shape[0] / h, rgb.shape[0] - 1).astype(int)
        x = np.minimum((np.arange(w) + .5) * rgb.shape[1] / w, rgb.shape[1] - 1).astype(int)
        return rgb[y[:, None], x]
    if sampling == "area":
        return F.interpolate(torch.from_numpy(rgb).permute(2, 0, 1)[None],
                             size=size, mode="area")[0].permute(1, 2, 0).numpy()
    px, py = edge_profiles(rgb)
    xs, ys = grid_cuts(px, rgb.shape[1], w), grid_cuts(py, rgb.shape[0], h)
    out = np.empty((h, w, 3), dtype=np.float32)
    # Vote in coarse RGB bins, return an actual source representative from the
    # winning bin. Fine shading doesn't outvote a coherent pixel-sized region.
    for y in range(h):
        for x in range(w):
            cell = rgb[ys[y]:ys[y + 1], xs[x]:xs[x + 1]].reshape(-1, 3)
            bins = np.minimum((cell * 15).astype(int), 15)
            keys = bins @ np.array([256, 16, 1])
            counts = np.bincount(keys, minlength=4096)
            center_key = keys[len(keys) // 2]
            winner = center_key if counts[center_key] == counts.max() else counts.argmax()
            group = cell[keys == winner]
            out[y, x] = group[((group - np.median(group, axis=0)) ** 2).sum(-1).argmin()]
    return out


def detail_mask(lab):
    edge = np.zeros(lab.shape[:2], dtype=np.float32)
    for axis in (0, 1):
        d = np.linalg.norm(np.diff(lab, axis=axis), axis=-1)
        if axis == 0:
            edge[1:] = np.maximum(edge[1:], d)
            edge[:-1] = np.maximum(edge[:-1], d)
        else:
            edge[:, 1:] = np.maximum(edge[:, 1:], d)
            edge[:, :-1] = np.maximum(edge[:, :-1], d)
    return np.clip(1 - edge / .12, 0, 1)


def quantize(rgb, palette, dither, strength):
    lab, plab = oklab(rgb), oklab(palette)
    ids = nearest_indices(lab, plab)
    if dither == "none" or strength <= 0 or len(palette) < 2:
        return palette[ids]
    smooth = detail_mask(lab)
    if dither == "error_diffusion":
        work = lab.copy()
        h, w = ids.shape
        for y in range(h):
            direction = 1 if y % 2 == 0 else -1
            for x in range(w) if direction == 1 else range(w - 1, -1, -1):
                idx = ((plab - work[y, x]) ** 2).sum(-1).argmin()
                ids[y, x] = idx
                err = (work[y, x] - plab[idx]) * strength * smooth[y, x]
                for dy, dx, weight in ((0, direction, 7/16), (1, -direction, 3/16),
                                       (1, 0, 5/16), (1, direction, 1/16)):
                    yy, xx = y + dy, x + dx
                    if yy < h and 0 <= xx < w:
                        work[yy, xx] += err * weight * smooth[yy, xx]
        return palette[ids]
    bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6],
                      [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32)
    threshold = (np.tile((bayer + .5) / 16, ((rgb.shape[0] + 3)//4, (rgb.shape[1] + 3)//4))
                 [:rgb.shape[0], :rgb.shape[1]]).ravel()
    # Palette-pair mixing is evaluated in linear light. Only use a pair when
    # its mixture improves perceptual error over the nearest single color.
    flat, lin = lab.reshape(-1, 3), linear_rgb(rgb).reshape(-1, 3)
    lp = linear_rgb(palette)
    out = ids.ravel().copy()
    for start in range(0, len(flat), 2048):
        z, target = flat[start:start+2048], lin[start:start+2048]
        first = out[start:start+len(z)]
        base = lp[first]
        delta = lp[None] - base[:, None]
        t = np.clip(((target[:, None] - base[:, None]) * delta).sum(-1) /
                    np.maximum((delta * delta).sum(-1), 1e-10), 0, 1)
        mix = base[:, None] + t[..., None] * delta
        srgb = np.where(mix <= .0031308, mix * 12.92, 1.055 * np.maximum(mix, 0)**(1/2.4) - .055)
        # Penalize distant pairs so a near color isn't replaced with salt/pepper.
        error = ((oklab(srgb) - z[:, None])**2).sum(-1)
        error += .02 * t * (1 - t) * ((plab[None] - plab[first, None])**2).sum(-1)
        second = error.argmin(-1)
        row = np.arange(len(z))
        # Stable palette-index ordering avoids inverting the Bayer pattern
        # whenever the nearest color changes at a quantization boundary.
        second_is_high = second > first
        high, low = np.maximum(first, second), np.minimum(first, second)
        prob = np.where(second_is_high, t[row, second], 1 - t[row, second])
        amount = strength * smooth.ravel()[start:start+len(z)]
        prob = amount * prob + (1 - amount) * (first == high)
        use = threshold[start:start+len(z)] < prob
        out[start:start+len(z)] = np.where(use, high, low)
    return palette[out.reshape(ids.shape)]


def outline_image(rgb, palette, mode):
    if mode == "none":
        return rgb
    from scipy.ndimage import binary_propagation, binary_erosion
    lab = oklab(rgb)
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]))
    colors, counts = np.unique(border, axis=0, return_counts=True)
    if counts.max() < len(border) * .35:
        return rgb  # No trustworthy solid backdrop: don't outline texture.
    bg = colors[counts.argmax()]
    eligible = np.linalg.norm(lab - oklab(bg), axis=-1) < .035
    seeds = np.zeros(eligible.shape, bool)
    seeds[[0, -1], :] = eligible[[0, -1], :]
    seeds[:, [0, -1]] = eligible[:, [0, -1]]
    background = binary_propagation(seeds, mask=eligible)
    subject = ~background
    contour = subject & ~binary_erosion(subject, border_value=1)
    if not contour.any():
        return rgb
    plab = oklab(palette)
    pix = lab[contour]
    darker = plab[None, :, 0] < pix[:, None, 0] - .06
    cost = ((plab[None, :, 1:] - pix[:, None, 1:])**2).sum(-1)
    cost += .3 * (plab[None, :, 0] - (pix[:, None, 0] - .22))**2
    cost[~darker] = np.inf
    ids = cost.argmin(-1)
    out = rgb.copy()
    out[contour] = np.where(darker.any(-1)[:, None], palette[ids], rgb[contour])
    return out


class RayPixelArtDetector:
    CATEGORY = "👑 Ray/✨ VFX"
    FUNCTION = "process"
    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("image", "preview")
    OUTPUT_TOOLTIPS = ("Pixel-resolution image with the exact source aspect ratio.",
                       "Nearest-neighbor preview at the original input dimensions.")
    DESCRIPTION = "Snap a pixel grid, choose a perceptual palette and optionally dither or outline. Preserve the exact aspect ratio."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE", {"tooltip": "Connect the source image or batch."}),
            "mode": (["manual_resize", "auto_pixel_size", "pixel_size"], {"default": "manual_resize", "tooltip": "Choose target size, detected grid size, or source pixels per output pixel."}),
            "target_resolution": ("INT", {"default": 128, "min": 1, "max": 4096, "tooltip": "Choose the longest side; snap to the nearest exact-aspect integer resolution. Also used when auto detection finds no grid."}),
            "pixel_size": ("INT", {"default": 8, "min": 1, "max": 128, "tooltip": "Choose source pixels per output pixel in pixel_size mode."}),
            "sampling": (["grid_snap", "nearest", "area"], {"tooltip": "Use cell color voting for pixel-like art, nearest for a crisp baseline, or area for photos and gradients."}),
            "reduce_palette": ("BOOLEAN", {"default": True, "tooltip": "Reduce colors and enable palette-based dithering. A connected palette always takes precedence."}),
            "max_colors": ("INT", {"default": 32, "min": 2, "max": 256, "tooltip": "Limit generated palettes. Connected palettes with at most 256 distinct colors are preserved in full."}),
            "dither": (["none", "ordered", "error_diffusion"], {"tooltip": "Choose no dither, a stable ordered pattern, or serpentine error diffusion. Protect strong edges automatically."}),
            "dither_strength": ("FLOAT", {"default": .7, "min": 0, "max": 1, "step": .05, "tooltip": "Control dither intensity without changing the palette."}),
            "outline": (["none", "silhouette"], {"tooltip": "Add a one-pixel inner contour using darker palette colors. Requires a recognizable solid border background."}),
            "seed": ("INT", {"default": -1, "min": -1, "max": 2**31-1, "tooltip": "-1 for random; any >=0 value is reproducible."}),
        }, "optional": {"palette_image": ("IMAGE", {"tooltip": "Connect clean color swatches. Preserve up to 256 exact RGB colors; larger images are reduced to max_colors."})}}

    def process(self, image, mode="manual_resize", target_resolution=128, pixel_size=8,
                sampling="grid_snap", reduce_palette=True, max_colors=32, dither="none",
                dither_strength=.7, outline="none", seed=0, palette_image=None):
        batch = torch.nan_to_num(normalize_image(image).detach().cpu()).numpy()
        if min(batch.shape[:3]) < 1:
            raise ValueError("Connect a nonempty image batch.")
        h, w = batch.shape[1:3]
        seed = int(np.random.default_rng().integers(2**31)) if seed < 0 else int(seed)
        longest = target_resolution
        if mode == "pixel_size":
            longest = max(h, w) / pixel_size
        elif mode == "auto_pixel_size":
            steps = []
            for rgb in batch:
                steps.extend(s for p in edge_profiles(rgb) if (s := estimate_grid(p)) is not None)
            if steps:
                longest = max(h, w) / float(np.median(steps))
            else:
                logging.info("[Ray Pixel Art] No reliable grid; using target_resolution.")
        size = exact_size(h, w, longest)
        if max(size) != round(longest):
            logging.info("[Ray Pixel Art] Exact aspect ratio: requested longest side %s, using %sx%s.", longest, size[1], size[0])
        sampled = np.stack([sample_image(rgb, size, sampling) for rgb in batch])
        palette = None
        if palette_image is not None:
            swatches = torch.nan_to_num(normalize_image(palette_image).detach().cpu()).numpy()
            if min(swatches.shape[:3]) < 1:
                raise ValueError("Connect a nonempty palette image.")
            colors = np.unique(swatches.reshape(-1, 3), axis=0)
            palette = colors if len(colors) <= 256 else make_palette(swatches, max_colors, seed, True)
        elif reduce_palette:
            palette = make_palette(sampled, max_colors, seed)
        outputs = []
        for rgb in sampled:
            result = quantize(rgb, palette, dither, dither_strength) if palette is not None else rgb
            if outline != "none":
                contour_palette = palette if palette is not None else make_palette(sampled, max_colors, seed)
                result = outline_image(result, contour_palette, outline)
            outputs.append(torch.from_numpy(result.copy()))
        output = torch.stack(outputs)
        preview = F.interpolate(output.permute(0, 3, 1, 2), size=(h, w), mode="nearest").permute(0, 2, 3, 1)
        return output, preview
