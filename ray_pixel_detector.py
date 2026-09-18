"""Pixel-art repair and illustration abstraction with palette-constrained effects.

Grid detection uses the attributed MIT-licensed ray_pixel_fixer package.
Reconstruction and artistic controls are implemented in ray_pixel_structure.
"""
from math import gcd
import logging

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.cluster import MiniBatchKMeans
from threadpoolctl import threadpool_limits
try:
    from .ray_pixel_structure import reconstruct, detect_size, abstract_image, dither_regions, distinct_palette, clean_clusters
except ImportError:
    from ray_pixel_structure import reconstruct, detect_size, abstract_image, dither_regions, distinct_palette, clean_clusters
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


try:
    from .ray_pixel_palette import build_palette, cie_lab
    from .ray_pixel_families import family_indices, family_features
except ImportError:
    from ray_pixel_palette import build_palette, cie_lab
    from ray_pixel_families import family_indices, family_features


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


def make_palette(rgb, count, seed, source_colors=False, strategy="kmeans_lab",
                 protect_highlights=True, highlight_threshold=90, ramp_levels=4,
                 palette_allocation="area_preserving"):
    return build_palette(rgb, count, seed, oklab, nearest_indices, strategy,
                         protect_highlights, highlight_threshold, ramp_levels, source_colors,
                         palette_allocation)


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
    return reconstruct(rgb, size, oklab, make_palette, nearest_indices)


def quantize(rgb, palette, dither, strength, preserve_families=False):
    lab, plab = oklab(rgb), oklab(palette)
    ids = family_indices(rgb, palette, oklab, cie_lab) if preserve_families else nearest_indices(lab, plab)
    pf = family_features(palette, cie_lab) if preserve_families else None
    if dither == "none" or strength <= 0 or len(palette) < 2:
        return palette[ids]
    smooth = dither_regions(lab)
    # A source ramp must actually lose a visible amount of tone to quantization.
    loss = np.linalg.norm(lab-plab[ids], axis=-1)
    smooth *= np.clip((loss-.008)/.02, 0, 1)
    if dither == "error_diffusion":
        work = lab.copy()
        h, w = ids.shape
        anchors = ids.copy()
        partners = ids.copy()
        for y, x in np.argwhere(smooth > 0):
            base = plab[anchors[y, x]]
            delta = plab-base
            t = np.clip(((lab[y, x]-base)*delta).sum(-1)/np.maximum((delta*delta).sum(-1), 1e-10), 0, 1)
            error = ((base+t[:, None]*delta-lab[y, x])**2).sum(-1)
            compatible = np.linalg.norm(delta[:, 1:], axis=-1) <= np.maximum(.04, np.abs(delta[:, 0])*.65)
            if pf is not None:
                compatible &= np.linalg.norm(pf[:, 1:]-pf[anchors[y, x], 1:], axis=-1) < .25
            error += .02*t*(1-t)*(delta*delta).sum(-1)
            error[~compatible] = np.inf
            second = error.argmin()
            gain = 1-error[second]/max(loss[y, x]**2, 1e-10)
            smooth[y, x] *= np.clip((gain-.25)/.5, 0, 1)
            partners[y, x] = second
        for y in range(h):
            direction = 1 if y % 2 == 0 else -1
            for x in range(w) if direction == 1 else range(w - 1, -1, -1):
                if smooth[y, x] <= 0:
                    continue
                candidates = np.array([anchors[y, x], partners[y, x]])
                idx = candidates[((plab[candidates] - work[y, x]) ** 2).sum(-1).argmin()]
                ids[y, x] = idx
                err = (work[y, x] - plab[idx]) * strength * smooth[y, x]
                for dy, dx, weight in ((0, direction, 7/16), (1, -direction, 3/16),
                                       (1, 0, 5/16), (1, direction, 1/16)):
                    yy, xx = y + dy, x + dx
                    if (yy < h and 0 <= xx < w and
                            np.linalg.norm(lab[yy, xx]-lab[y, x]) < .045):
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
        pair = plab[None] - plab[first, None]
        # Avoid mixing unrelated hues merely because their average fits.
        compatible = np.linalg.norm(pair[..., 1:], axis=-1) <= np.maximum(.04, np.abs(pair[..., 0])*.65)
        if pf is not None:
            compatible &= np.linalg.norm(pf[None, :, 1:]-pf[first, None, 1:], axis=-1) < .25
        error = np.where(compatible, error, np.inf)
        second = error.argmin(-1)
        row = np.arange(len(z))
        # Stable palette-index ordering avoids inverting the Bayer pattern
        # whenever the nearest color changes at a quantization boundary.
        second_is_high = second > first
        high, low = np.maximum(first, second), np.minimum(first, second)
        prob = np.where(second_is_high, t[row, second], 1 - t[row, second])
        single_error = ((z-plab[first])**2).sum(-1)
        gain = np.clip((single_error-error[row, second])/np.maximum(single_error, 1e-10), 0, 1)
        amount = strength * smooth.ravel()[start:start+len(z)] * np.clip((gain-.25)/.5, 0, 1)
        prob = amount * prob + (1 - amount) * (first == high)
        use = threshold[start:start+len(z)] < prob
        out[start:start+len(z)] = np.where(use, high, low)
    return palette[out.reshape(ids.shape)]


def outline_image(rgb, palette, mode, foreground_mask=None):
    if mode == "none":
        return rgb
    from scipy.ndimage import binary_propagation, binary_erosion
    lab = oklab(rgb)
    if foreground_mask is not None:
        subject = foreground_mask > .5
    else:
        border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]))
        colors, counts = np.unique(border, axis=0, return_counts=True)
        if counts.max() < len(border) * .35:
            return rgb
        bg = colors[counts.argmax()]
        eligible = np.linalg.norm(lab - oklab(bg), axis=-1) < .035
        seeds = np.zeros(eligible.shape, bool)
        seeds[[0, -1], :] = eligible[[0, -1], :]
        seeds[:, [0, -1]] = eligible[:, [0, -1]]
        subject = ~binary_propagation(seeds, mask=eligible)
    contour = subject & ~binary_erosion(subject, border_value=1)
    if not contour.any():
        return rgb
    plab = oklab(palette)
    pix = lab[contour]
    if mode == "selective":
        # Use nearby interior shading to color the outline, retaining the
        # source's light/dark ordering rather than inventing a light direction.
        from scipy.ndimage import distance_transform_edt
        interior = subject & ~contour
        if not interior.any():
            return rgb
        distances, indices = distance_transform_edt(~interior, return_indices=True)
        near = lab[indices[0], indices[1]][contour]
        light = lab[interior, 0]
        lo, hi = np.percentile(light, [10, 90])
        level = np.clip((near[:, 0] - lo) / max(hi - lo, .1), 0, 1)
        target = near.copy()
        target[:, 0] -= .08 + .12 * (1 - level)
        cost = ((plab[None] - target[:, None]) ** 2).sum(-1)
        cost[plab[None, :, 0] > near[:, None, 0]] = np.inf
        colors = palette[cost.argmin(-1)]
        out = rgb.copy()
        valid = (distances[contour] <= 2) & np.isfinite(cost).any(-1)
        out[contour] = np.where(valid[:, None], colors, rgb[contour])
        return out
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
                       "Nearest-neighbor preview, or labeled method comparison when color grid is enabled.")
    DESCRIPTION = "Repair a pixel grid or abstract an illustration/photo. Preserve exact aspect ratio, select perceptual colors and optionally dither or outline."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE", {"tooltip": "Connect the source image or batch."}),
            "input_kind": (["repair_pixel_art", "illustration_photo"], {"tooltip": "Recover an existing pixel grid, or abstract an illustration/photo into a smaller set of readable regions."}),
            "mode": (["manual_resize", "auto_pixel_size", "pixel_size"], {"default": "manual_resize", "tooltip": "Choose target size, detected grid size, or source pixels per output pixel."}),
            "target_resolution": ("INT", {"default": 128, "min": 1, "max": 4096, "tooltip": "Choose the longest side; snap to the nearest exact-aspect integer resolution. Also used when auto detection finds no grid."}),
            "pixel_size": ("INT", {"default": 8, "min": 1, "max": 128, "tooltip": "Choose source pixels per output pixel in pixel_size mode."}),
            "sampling": (["grid_snap", "nearest", "area"], {"tooltip": "Use structure reconstruction for repair, region abstraction for illustration/photo, nearest for crisp sampling, or area for averaging."}),
            "reduce_palette": ("BOOLEAN", {"default": True, "tooltip": "Reduce colors and enable palette-based dithering. A connected palette always takes precedence."}),
            "max_colors": ("INT", {"default": 32, "min": 2, "max": 256, "tooltip": "Limit generated palettes. Connected palettes with at most 256 distinct colors are preserved in full."}),
            "palette_style": (["source", "distinct"], {"tooltip": "Keep source shading, or merge near-duplicate generated shades for clearer color clusters. Supplied palettes stay unchanged."}),
            "dither": (["none", "ordered", "error_diffusion"], {"tooltip": "Choose no dither, a stable ordered pattern, or serpentine error diffusion. Protect strong edges automatically."}),
            "dither_strength": ("FLOAT", {"default": .7, "min": 0, "max": 1, "step": .05, "tooltip": "Control dither intensity without changing the palette."}),
            "outline": (["none", "silhouette", "selective"], {"tooltip": "Use a dark inner contour or a colored contour guided by nearby shading. Connect foreground_mask for complex backgrounds."}),
            "palette_strategy": (["color_families", "kmeans_lab", "quantize_simple", "kmeans_rgb", "oklab_source", "ramps_oklab"], {"tooltip": "color_families prioritizes distinct hue/lightness groups and neutral colors before extra shades; assignment also protects family identity. Other methods retain their previous behavior. This is not semantic material recognition."}),
            "protect_highlights": ("BOOLEAN", {"default": True, "tooltip": "Reserve bright source colors inside the color budget. color_families preserves main families first and protects neutral glints only with spare slots. Other methods can reserve neutral and warm highlights. Supplied palettes are unchanged."}),
            "highlight_threshold": ("INT", {"default": 90, "min": 50, "max": 100, "tooltip": "CIE Lab lightness cutoff, matching the original node. Lower this if important highlights are less bright."}),
            "color_grid": ("BOOLEAN", {"default": False, "tooltip": "Replace only preview with a labeled 3-by-3 grid: the exact current image output followed by all six generated color methods. Uses max_colors and the same seed/effects. Main image stays unchanged. Integer nearest-neighbor tile scaling; extra processing required."}),
            "ramp_levels": ("INT", {"default": 4, "min": 2, "max": 8, "tooltip": "Lightness bands per chroma family for ramps_oklab; total palette still respects max_colors."}),
            "palette_allocation": (["area_preserving", "frequency"], {"tooltip": "Favor coherent color areas and spend fewer shades on busy texture, or use ordinary color frequency. Highlight protection applies to both. No semantic recognition."}),
            "seed": ("INT", {"default": -1, "min": -1, "max": 2**31-1, "tooltip": "-1 for random; any >=0 value is reproducible."}),
        }, "optional": {"palette_image": ("IMAGE", {"tooltip": "Connect clean color swatches. Preserve up to 256 exact RGB colors; larger images are reduced to max_colors."}),
            "foreground_mask": ("MASK", {"tooltip": "Optional outline mask: 1 is subject, 0 is background. Invert Load Image alpha masks before connecting."})}}

    def process(self, image, mode="manual_resize", target_resolution=128, pixel_size=8,
                sampling="grid_snap", reduce_palette=True, max_colors=32, dither="none",
                dither_strength=.7, outline="none", seed=0, palette_image=None,
                input_kind="repair_pixel_art", foreground_mask=None, palette_style="source",
                palette_strategy="kmeans_lab", protect_highlights=True,
                highlight_threshold=90, ramp_levels=4, palette_allocation="area_preserving",
                color_grid=False):
        batch = torch.nan_to_num(normalize_image(image).detach().cpu()).numpy()
        if min(batch.shape[:3]) < 1:
            raise ValueError("Connect a nonempty image batch.")
        h, w = batch.shape[1:3]
        seed = int(np.random.default_rng().integers(2**31)) if seed < 0 else int(seed)
        longest = target_resolution
        if mode == "pixel_size":
            longest = max(h, w) / pixel_size
        size = exact_size(h, w, longest)
        if mode == "auto_pixel_size" and input_kind == "repair_pixel_art":
            predictions=[]
            for rgb in batch:
                detected, reason = detect_size(rgb, size)
                predictions.append(max(detected))
                logging.info("[Ray Pixel Art] Grid %sx%s (%s).", detected[1], detected[0], reason)
            size=exact_size(h, w, float(np.median(predictions)))
        elif mode == "auto_pixel_size":
            logging.info("[Ray Pixel Art] Illustration/photo uses target_resolution; it has no assumed pixel grid.")
        if max(size) != round(longest) and mode != "auto_pixel_size":
            logging.info("[Ray Pixel Art] Exact aspect ratio: requested longest side %s, using %sx%s.", longest, size[1], size[0])
        palette = None
        if palette_image is not None:
            swatches = torch.nan_to_num(normalize_image(palette_image).detach().cpu()).numpy()
            if min(swatches.shape[:3]) < 1:
                raise ValueError("Connect a nonempty palette image.")
            colors = np.unique(swatches.reshape(-1, 3), axis=0)
            palette = colors if len(colors) <= 256 else make_palette(swatches, max_colors, seed, True)
        def generated_palette(pixels):
            return make_palette(pixels, max_colors, seed, strategy=palette_strategy,
                                protect_highlights=protect_highlights,
                                highlight_threshold=highlight_threshold, ramp_levels=ramp_levels,
                                palette_allocation=palette_allocation)
        draft = palette
        if input_kind == "illustration_photo" and reduce_palette and draft is None:
            draft = generated_palette(batch)
        if input_kind == "illustration_photo" and sampling == "grid_snap":
            sampled = np.stack([abstract_image(rgb, size, oklab, nearest_indices, draft) for rgb in batch])
        elif sampling == "grid_snap":
            sampled = np.stack([reconstruct(rgb, size, oklab, make_palette, nearest_indices, seed) for rgb in batch])
        else:
            sampled = np.stack([sample_image(rgb, size, sampling) for rgb in batch])
        if palette is None and reduce_palette:
            palette = generated_palette(sampled)
            if palette_style == "distinct" and palette_strategy != "color_families":
                # Merge only ordinary shades; reserved highlights remain available.
                bright = cie_lab(palette)[:, 0] >= highlight_threshold if protect_highlights else np.zeros(len(palette), bool)
                ordinary = distinct_palette(palette[~bright], sampled, oklab, nearest_indices) if (~bright).any() else palette[:0]
                palette = np.concatenate((ordinary, palette[bright]))
        masks = None
        if foreground_mask is not None:
            masks = foreground_mask.detach().float().cpu()
            if masks.ndim == 2: masks = masks.unsqueeze(0)
            if masks.ndim != 3 or masks.shape[0] not in (1, len(batch)) or min(masks.shape[-2:]) < 1:
                raise ValueError("foreground_mask must be HW or BHW, with one mask or one per image.")
            masks = F.interpolate(masks[:, None], size=size, mode="nearest")[:, 0].numpy()
        outputs = []
        for index, rgb in enumerate(sampled):
            result = quantize(rgb, palette, dither, dither_strength, palette_strategy == "color_families" and palette_image is None) if palette is not None else rgb
            if palette is not None and palette_image is None and palette_style == "distinct" and palette_strategy != "color_families" and input_kind == "illustration_photo" and dither == "none":
                result = clean_clusters(result, rgb, palette, oklab, nearest_indices)
            if outline != "none":
                contour_palette = palette if palette is not None else make_palette(sampled, max_colors, seed)
                result = outline_image(result, contour_palette, outline, None if masks is None else masks[index % len(masks)])
            outputs.append(torch.from_numpy(result.copy()))
        output = torch.stack(outputs)
        if color_grid:
            methods = self.INPUT_TYPES()["required"]["palette_strategy"][0]
            comparisons = [output]
            labels = ["current output"]
            if palette_image is not None:
                current_note = "supplied palette"
            elif not reduce_palette:
                current_note = "palette reduction off"
            else:
                current_note = f"{palette_strategy} · selected"
            notes = [current_note]
            for method in methods:
                if method == palette_strategy and reduce_palette and palette_image is None:
                    comparisons.append(output)
                else:
                    result, _ = self.process(
                        image, mode="manual_resize", target_resolution=max(size), pixel_size=pixel_size,
                        sampling=sampling, reduce_palette=True, max_colors=max_colors,
                        dither=dither, dither_strength=dither_strength, outline=outline, seed=seed,
                        input_kind=input_kind, foreground_mask=foreground_mask, palette_style=palette_style,
                        palette_strategy=method, protect_highlights=protect_highlights,
                        highlight_threshold=highlight_threshold, ramp_levels=ramp_levels,
                        palette_allocation=palette_allocation, color_grid=False)
                    comparisons.append(result)
                labels.append(method)
                notes.append(f"{max_colors} colors max")
            return output, color_grid_preview(comparisons, labels, notes, (h, w))
        preview = F.interpolate(output.permute(0, 3, 1, 2), size=(h, w), mode="nearest").permute(0, 2, 3, 1)
        return output, preview


def color_grid_preview(comparisons, labels, notes, source_size):
    """One labeled contact sheet per input; first tile is the exact main output."""
    from PIL import Image, ImageDraw, ImageFont
    ph, pw = comparisons[0].shape[1:3]
    zoom = max(1, min(512, max(source_size)) // max(ph, pw))
    tw, th = pw * zoom, ph * zoom
    cell_w, header, gap = max(240, tw), 48, 12
    cols, rows = 3, (len(labels)+2)//3
    try:
        font = ImageFont.load_default(size=16)
    except TypeError:
        font = ImageFont.load_default()
    previews = []
    for index in range(len(comparisons[0])):
        sheet = Image.new("RGB", (cols*cell_w+(cols+1)*gap, rows*(th+header)+(rows+1)*gap), (24,24,24))
        draw = ImageDraw.Draw(sheet)
        for tile, label, note, pixels in zip(range(len(labels)), labels, notes, comparisons):
            x, y = gap+(tile%cols)*(cell_w+gap), gap+(tile//cols)*(th+header+gap)
            draw.text((x+8, y+4), label, font=font, fill=(245,245,245))
            draw.text((x+8, y+25), note, font=font, fill=(175,175,175))
            array = np.round(np.clip(pixels[index].numpy(), 0, 1)*255).astype(np.uint8)
            panel = Image.fromarray(array).resize((tw, th), Image.Resampling.NEAREST)
            sheet.paste(panel, (x+(cell_w-tw)//2, y+header))
        previews.append(torch.from_numpy(np.asarray(sheet, dtype=np.float32)/255))
    return torch.stack(previews)
