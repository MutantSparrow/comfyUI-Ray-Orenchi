"""Load complete text files as paired prompt and filename lists."""
from pathlib import Path


class RayTextFolder:
    DESCRIPTION = (
        "Read .txt files alphabetically from a local folder. Emit one complete "
        "prompt and matching save prefix per non-empty file. Connect both list "
        "outputs to the same generation/save chain. Re-read files on every run."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "directory": ("STRING", {"default": "", "tooltip": "Enter the absolute path to a folder of .txt prompts."}),
            "start_index": ("INT", {"default": 0, "min": 0, "tooltip": "Skip this many files in alphabetical filename order, counting empty files."}),
            "limit": ("INT", {"default": -1, "min": -1, "tooltip": "Read at most this many files after start_index; use -1 for all remaining files. Empty files count toward this limit."}),
            "output_prefix": ("STRING", {"default": "RayKrea2_FromTXT", "tooltip": "Set the Save Image subfolder or prefix; append each source filename without its .txt extension."}),
        }}

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt", "filename_prefix")
    OUTPUT_TOOLTIPS = (
        "Complete text from each non-empty file, in alphabetical filename order.",
        "Matching save prefix for each prompt, using the source filename stem.",
    )
    OUTPUT_IS_LIST = (True, True)
    FUNCTION = "load"
    CATEGORY = "👑 Ray/📝 Prompts"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def load(self, directory, start_index, limit, output_prefix):
        if not str(directory).strip():
            raise ValueError("Enter a folder containing .txt prompts.")
        folder = Path(directory).expanduser().resolve(strict=True)
        if not folder.is_dir():
            raise ValueError(f"Not a directory: {folder}")
        if start_index < 0 or limit < -1:
            raise ValueError("Use start_index >= 0 and limit >= -1.")
        files = sorted(
            (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".txt"),
            key=lambda p: p.name,
        )[start_index:]
        if limit >= 0:
            files = files[:limit]
        prompts, prefixes = [], []
        prefix = output_prefix.rstrip("/\\")
        for path in files:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                text = handle.read()
            if not text.strip():
                print(f"[RayTextFolder] Skipping empty file: {path.name}")
                continue
            prompts.append(text)
            prefixes.append(f"{prefix}/{path.stem}" if prefix else path.stem)
        if not prompts:
            raise ValueError("No non-empty .txt files in the selected range.")
        print(f"[RayTextFolder] Loaded {len(prompts)} prompts from {folder}")
        return (prompts, prefixes)
