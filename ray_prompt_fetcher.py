"""Ray's Prompt Fetcher.

Single ComfyUI node that unifies the three existing prompt scrapers:
  • Local   — Folder Image Scraper (ray_local_scraper)
  • Dexter  — PromptDexter web scraper (ray_promptdexter)
  • CivitAI — CivitAI gallery scraper (ray_civitai)

A `scraper_mode` dropdown selects which backend runs. All other widgets are
declared upfront with a mode prefix (`local__`, `dexter__`, `civitai__`); the
companion JS (`web/ray_prompt_fetcher.js`) hides widgets that don't belong
to the active mode so the node looks the same as the dedicated scrapers.

Outputs are harmonized to the local-scraper shape so any mode is drop-in
compatible with downstream wiring:
  (prompt_single, prompt_multiline, image, image_path)
All four declared OUTPUT_IS_LIST=True. Web modes emit a single-element list
with `image_path=""` (no on-disk source).
"""

from __future__ import annotations

import os
import pathlib
import random
import re
from collections import deque
from typing import Optional

import numpy as np
from PIL import Image

try:
    import torch
except ImportError:
    torch = None

try:
    from . import ray_local_scraper as _local
    from . import ray_promptdexter as _dexter
    from . import ray_civitai as _civit
except ImportError:
    import ray_local_scraper as _local  # type: ignore[no-redef]
    import ray_promptdexter as _dexter  # type: ignore[no-redef]
    import ray_civitai as _civit  # type: ignore[no-redef]


MODE_LOCAL = "Local Folder"
MODE_DEXTER = "PromptDexter"
MODE_CIVITAI = "CivitAI"
MODES = [MODE_LOCAL, MODE_DEXTER, MODE_CIVITAI]


def _empty_tensor():
    if torch is None:
        return None
    return torch.zeros((1, 1, 1, 3), dtype=torch.float32)


class RayPromptFetcher:
    """All-in-one prompt fetcher with a mode-selector dropdown."""

    DESCRIPTION = (
        "One node, three prompt sources. Pick a mode and the JS hides "
        "widgets for the others.\n"
        "  • `Local Folder`  — random image + extracted prompt from a "
        "local folder (RayLocalScraper).\n"
        "  • `PromptDexter`  — random prompt + image from "
        "promptdexter.com (RayPromptDexter).\n"
        "  • `CivitAI`       — random prompt + image from civitai.com "
        "(RayCivitAI).\n\n"
        "Outputs are harmonized to `(prompt_single, prompt_multiline, "
        "image, image_path)` so any mode is drop-in compatible with "
        "downstream wiring. `image_path` is empty for web modes."
    )

    @classmethod
    def INPUT_TYPES(cls):
        try:
            dexter_cats = _dexter.get_categories(force_refresh=False, timeout=10)
        except Exception:
            dexter_cats = []
        dexter_category_choices = [_dexter.ANY_CATEGORY] + dexter_cats

        return {
            "required": {
                "scraper_mode": (MODES, {
                    "default": MODE_LOCAL,
                    "tooltip": "Which backend runs. The JS hides widgets for the other modes.",
                }),
                "seed": ("INT", {
                    "default": -1, "min": -1, "max": 2**31 - 1,
                    "tooltip": "-1 for random; any >=0 value is reproducible.",
                }),

                # --- Local mode widgets ---
                "local__folder": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "Absolute path to a folder of images",
                    "tooltip": "Local mode: absolute path to a folder of images.",
                }),
                "local__recurse_subfolders": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Local mode: walk every subdirectory.",
                }),
                "local__skip_no_prompt": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Local mode: skip images whose metadata yields no prompt.",
                }),
                "local__prompt_best_try": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Local mode: collapse to one prompt per image; skip repeats.",
                }),

                # --- PromptDexter mode widgets ---
                "dexter__category": (
                    dexter_category_choices,
                    {"default": _dexter.ANY_CATEGORY,
                     "tooltip": "PromptDexter mode: sitemap category slug, or (any)."},
                ),
                "dexter__clear_cache": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "PromptDexter mode: drop the recent-pick deque before selecting.",
                }),

                # --- CivitAI mode widgets ---
                "civitai__mode": (_civit.MODES, {
                    "default": _civit.MODE_BLUE,
                    "tooltip": "CivitAI mode: Blue = SFW; Red = all levels.",
                }),
                "civitai__base_model": (
                    _civit.BASE_MODELS,
                    {"default": _civit.BASE_MODELS_DEFAULT,
                     "tooltip": "CivitAI mode: restrict picks to this base model."},
                ),
                "civitai__period": (_civit.PERIODS, {
                    "default": "Week",
                    "tooltip": "CivitAI mode: time window.",
                }),
                "civitai__sort": (_civit.SORTS, {
                    "default": "Random",
                    "tooltip": "CivitAI mode: gallery sort order.",
                }),
                "civitai__username": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "CivitAI username (optional)",
                    "tooltip": "CivitAI mode: restrict pool to one uploader.",
                }),
            },
            "optional": {
                "local__refresh_listing": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Local mode: force a re-scan of the folder.",
                }),
                "dexter__timeout": (
                    "INT",
                    {"default": 10, "min": 2, "max": 60, "step": 1,
                     "tooltip": "PromptDexter mode: HTTP timeout per request."},
                ),
                "civitai__timeout": (
                    "INT",
                    {"default": 15, "min": 2, "max": 60, "step": 1,
                     "tooltip": "CivitAI mode: HTTP timeout per request."},
                ),
                "show_preview": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Render the fetched image inline in the node.",
                }),
            },
            "hidden": {"node_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING", "STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("prompt_single", "prompt_multiline", "image", "image_path")
    OUTPUT_TOOLTIPS = (
        "Whitespace-collapsed single-line prompt (list).",
        "Prompt with original newlines preserved (list).",
        "Image tensor (BHWC float32 [0,1]).",
        "For Local mode: absolute path of the source file. Empty for web modes.",
    )
    OUTPUT_IS_LIST = (True, True, True, True)
    FUNCTION = "process"
    CATEGORY = "👑 Ray/📝 Prompts"

    @classmethod
    def IS_CHANGED(cls, *args, **kwargs):
        return float("nan")

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def process(
        self,
        scraper_mode,
        seed,
        local__folder,
        local__recurse_subfolders,
        local__skip_no_prompt,
        local__prompt_best_try,
        dexter__category,
        dexter__clear_cache,
        civitai__mode,
        civitai__base_model,
        civitai__period,
        civitai__sort,
        civitai__username="",
        local__refresh_listing=False,
        dexter__timeout=10,
        civitai__timeout=15,
        show_preview=True,
        node_id=None,
    ):
        mode = (scraper_mode or MODE_LOCAL).strip()
        if mode == MODE_LOCAL:
            return self._run_local(
                folder=local__folder,
                recurse_subfolders=local__recurse_subfolders,
                skip_no_prompt=local__skip_no_prompt,
                prompt_best_try=local__prompt_best_try,
                seed=seed,
                refresh_listing=local__refresh_listing,
                show_preview=show_preview,
                node_id=node_id,
            )
        if mode == MODE_DEXTER:
            return self._run_dexter(
                seed=seed,
                category=dexter__category,
                clear_cache=dexter__clear_cache,
                timeout=dexter__timeout,
                show_preview=show_preview,
                node_id=node_id,
            )
        if mode == MODE_CIVITAI:
            return self._run_civitai(
                seed=seed,
                mode=civitai__mode,
                base_model=civitai__base_model,
                period=civitai__period,
                sort=civitai__sort,
                username=civitai__username,
                timeout=civitai__timeout,
                show_preview=show_preview,
                node_id=node_id,
            )
        raise RuntimeError(f"unknown scraper_mode: {scraper_mode!r}")

    # ------------------------------------------------------------------
    # Mode adapters
    # ------------------------------------------------------------------

    def _run_local(
        self,
        folder,
        recurse_subfolders,
        skip_no_prompt,
        prompt_best_try,
        seed,
        refresh_listing,
        show_preview,
        node_id,
    ):
        # Delegate verbatim to RayLocalScraper.process — it already returns
        # the 4-tuple of lists in the required shape.
        return _local.RayLocalScraper().process(
            folder=folder,
            recurse_subfolders=recurse_subfolders,
            skip_no_prompt=skip_no_prompt,
            prompt_best_try=prompt_best_try,
            seed=seed,
            refresh_listing=refresh_listing,
            show_preview=show_preview,
            node_id=node_id,
        )

    def _run_dexter(self, seed, category, clear_cache, timeout, show_preview, node_id):
        single, multi, image = _dexter.RayPromptDexter().process(
            seed=seed,
            category=category,
            clear_cache=clear_cache,
            timeout=timeout,
            show_preview=show_preview,
            node_id=node_id,
        )
        return self._lift_web(single, multi, image)

    def _run_civitai(
        self,
        seed,
        mode,
        base_model,
        period,
        sort,
        username,
        timeout,
        show_preview,
        node_id,
    ):
        single, multi, image = _civit.RayCivitAI().process(
            seed=seed,
            mode=mode,
            base_model=base_model,
            period=period,
            sort=sort,
            username=username,
            timeout=timeout,
            show_preview=show_preview,
            node_id=node_id,
        )
        return self._lift_web(single, multi, image)

    @staticmethod
    def _lift_web(single, multi, image):
        """Promote a web-scraper's 3-tuple of scalars into the 4-list shape
        used by the local scraper. Web sources have no on-disk path; emit
        an empty string so downstream nodes still see a length-1 list."""
        if image is None:
            image = _empty_tensor()
        return ([single], [multi], [image], [""])
