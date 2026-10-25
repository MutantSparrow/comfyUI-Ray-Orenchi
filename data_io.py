"""Shared JSON parsing and atomic file commits without model dependencies."""
import json
import os
from pathlib import Path


def parse_metadata_json(text):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=object_pairs)


def commit_file(temp, destination, overwrite=False):
    destination = Path(str(destination).strip().strip('"').strip("'")).expanduser().resolve()
    if overwrite:
        os.replace(temp, destination)
    elif os.name == "nt":
        # Windows rename is atomic and refuses existing files, including on exFAT.
        os.rename(temp, destination)
    else:
        os.link(temp, destination)
        os.unlink(temp)
