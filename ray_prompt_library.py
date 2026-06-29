"""Ray's LLM: Local Prompt Library.

SQLite-backed prompt archive with optional sentence-transformers similarity.
Single node with Save / Fetch modes (pass-through STRING in + STRING out so
the library inlines between any prompt source and any consumer).

Storage: <pack>/prompt_library.db (gitignored)
Embeddings: lazy-loaded sentence-transformers (model `all-MiniLM-L6-v2`).
            Optional — node fails gracefully when not installed.

Outputs harmonize to the RayPromptFetcher shape:
  (prompt_single, prompt_multiline, image, image_path)   all OUTPUT_IS_LIST=True
"""

from __future__ import annotations

import hashlib
import pathlib
import random
import re
import sqlite3
import threading
from collections import deque
from typing import Optional

import numpy as np

try:
    import torch
except ImportError:
    torch = None


_PACK_DIR = pathlib.Path(__file__).resolve().parent
_DB_PATH = _PACK_DIR / "prompt_library.db"
_RECENT_BY_NODE: dict = {}
_CACHE_MAX = 20

MODE_SAVE = "Save"
MODE_FETCH = "Fetch"
MODES = [MODE_SAVE, MODE_FETCH]

SORT_RANDOM = "random"
SORT_RECENT = "most_recent"
SORT_LONGEST = "longest"
SORTS = [SORT_RANDOM, SORT_RECENT, SORT_LONGEST]

_EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
_EMBED_MODEL = None
_EMBED_LOCK = threading.Lock()
_EMBED_DISABLED = False


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------


def _connect(db_path: pathlib.Path = None) -> sqlite3.Connection:
    """Open the library DB and ensure schema exists. One row per unique prompt."""
    path = db_path or _DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT NOT NULL,
            prompt_single TEXT,
            source TEXT,
            image_path TEXT,
            model TEXT,
            seed INTEGER,
            tags TEXT,
            embedding BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sha256 TEXT UNIQUE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON prompts(source)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON prompts(created_at)")
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS prompts_fts
            USING fts5(prompt, tags, content='prompts', content_rowid='id')
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS prompts_ai AFTER INSERT ON prompts BEGIN
              INSERT INTO prompts_fts(rowid, prompt, tags) VALUES (new.id, new.prompt, new.tags);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS prompts_ad AFTER DELETE ON prompts BEGIN
              INSERT INTO prompts_fts(prompts_fts, rowid, prompt, tags)
                VALUES ('delete', old.id, old.prompt, old.tags);
            END
        """)
    except sqlite3.OperationalError:
        # FTS5 not compiled in — keyword search degrades to LIKE.
        pass
    conn.commit()
    return conn


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Embeddings (optional)
# ---------------------------------------------------------------------------


def _get_embed_model():
    """Lazy-load sentence-transformers. Returns None if unavailable."""
    global _EMBED_MODEL, _EMBED_DISABLED
    if _EMBED_DISABLED:
        return None
    if _EMBED_MODEL is not None:
        return _EMBED_MODEL
    with _EMBED_LOCK:
        if _EMBED_MODEL is not None:
            return _EMBED_MODEL
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            _EMBED_MODEL = SentenceTransformer(_EMBED_MODEL_NAME)
            return _EMBED_MODEL
        except Exception as e:
            print(f"[RayPromptLibrary] embeddings disabled: {e}")
            _EMBED_DISABLED = True
            return None


def _embed(text: str) -> Optional[bytes]:
    model = _get_embed_model()
    if model is None or not text:
        return None
    try:
        vec = model.encode([text], normalize_embeddings=True)[0]
        return np.asarray(vec, dtype=np.float32).tobytes()
    except Exception as e:
        print(f"[RayPromptLibrary] embed failed: {e}")
        return None


def _cosine_argsort(query_emb: np.ndarray, mat: np.ndarray) -> np.ndarray:
    """Return indices into `mat` sorted by descending cosine similarity to query."""
    if mat.size == 0:
        return np.array([], dtype=np.int64)
    # Embeddings are already L2-normalized → dot product == cosine.
    sims = mat @ query_emb
    return np.argsort(-sims)


# ---------------------------------------------------------------------------
# Save / Fetch
# ---------------------------------------------------------------------------


def save_prompt(
    prompt: str,
    source: str = "manual",
    tags: str = "",
    image_path: str = "",
    model: str = "",
    seed: Optional[int] = None,
    db_path: Optional[pathlib.Path] = None,
) -> dict:
    """Insert a prompt into the library. Idempotent on sha256."""
    prompt = (prompt or "").strip()
    if not prompt:
        return {"ok": False, "reason": "empty prompt"}
    prompt_single = re.sub(r"\s+", " ", prompt).strip()
    sha = _sha256(prompt)
    emb = _embed(prompt)

    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO prompts "
            "(prompt, prompt_single, source, image_path, model, seed, tags, embedding, sha256) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (prompt, prompt_single, source or "", image_path or "",
             model or "", seed, tags or "", emb, sha),
        )
        conn.commit()
        return {"ok": True, "inserted": cur.rowcount == 1, "sha256": sha}
    finally:
        conn.close()


def _build_filter_sql(
    tag: str,
    source: str,
    min_length: int,
    contains: str,
    exclude: str,
) -> tuple:
    """Compose WHERE clauses + params from filter widgets."""
    where = []
    params: list = []
    if tag:
        # tag widget is comma-separated; match if ANY tag substring is in the
        # comma-list field.
        for t in [s.strip() for s in tag.split(",") if s.strip()]:
            where.append("tags LIKE ?")
            params.append(f"%{t}%")
    if source:
        where.append("source = ?")
        params.append(source)
    if min_length and min_length > 0:
        where.append("length(prompt) >= ?")
        params.append(int(min_length))
    if contains:
        where.append("prompt LIKE ?")
        params.append(f"%{contains}%")
    if exclude:
        where.append("prompt NOT LIKE ?")
        params.append(f"%{exclude}%")
    sql = ""
    if where:
        sql = " WHERE " + " AND ".join(where)
    return sql, params


def fetch_prompt(
    tag: str = "",
    source: str = "",
    min_length: int = 0,
    contains: str = "",
    exclude: str = "",
    sort: str = SORT_RANDOM,
    similar_to: str = "",
    seed: Optional[int] = None,
    recent: Optional[deque] = None,
    db_path: Optional[pathlib.Path] = None,
) -> Optional[dict]:
    """Pull a single row matching the filters. Returns None if no match."""
    conn = _connect(db_path)
    try:
        # Similarity branch: load all candidates, rank by cosine.
        if similar_to.strip():
            query_emb = _embed(similar_to.strip())
            if query_emb is None:
                raise RuntimeError(
                    "similar_to requires sentence-transformers — `pip install sentence-transformers`"
                )
            where_sql, params = _build_filter_sql(
                tag, source, min_length, contains, exclude
            )
            cur = conn.execute(
                f"SELECT * FROM prompts {where_sql} AND embedding IS NOT NULL"
                if where_sql else
                "SELECT * FROM prompts WHERE embedding IS NOT NULL",
                params,
            )
            rows = cur.fetchall()
            if not rows:
                return None
            mat = np.vstack([
                np.frombuffer(r["embedding"], dtype=np.float32) for r in rows
            ])
            q_arr = np.frombuffer(query_emb, dtype=np.float32)
            order = _cosine_argsort(q_arr, mat)
            for idx in order:
                row = rows[int(idx)]
                if recent is None or row["id"] not in recent:
                    if recent is not None:
                        recent.append(row["id"])
                    return dict(row)
            return dict(rows[int(order[0])])

        # Plain filtered fetch.
        where_sql, params = _build_filter_sql(
            tag, source, min_length, contains, exclude
        )
        order_sql = {
            SORT_RECENT: "ORDER BY created_at DESC",
            SORT_LONGEST: "ORDER BY length(prompt) DESC",
            SORT_RANDOM: "ORDER BY RANDOM()",
        }.get(sort, "ORDER BY RANDOM()")

        if seed is not None and sort == SORT_RANDOM:
            # Deterministic random: fetch all matching ids, pick via seeded RNG.
            cur = conn.execute(
                f"SELECT id FROM prompts {where_sql}", params
            )
            ids = [r["id"] for r in cur.fetchall()
                   if recent is None or r["id"] not in recent]
            if not ids:
                # All exhausted via recent — fall back to full pool
                cur = conn.execute(
                    f"SELECT id FROM prompts {where_sql}", params
                )
                ids = [r["id"] for r in cur.fetchall()]
            if not ids:
                return None
            rng = random.Random(int(seed))
            pick_id = rng.choice(ids)
            cur = conn.execute("SELECT * FROM prompts WHERE id = ?", (pick_id,))
            row = cur.fetchone()
            if row and recent is not None:
                recent.append(row["id"])
            return dict(row) if row else None

        cur = conn.execute(
            f"SELECT * FROM prompts {where_sql} {order_sql} LIMIT 200",
            params,
        )
        rows = cur.fetchall()
        for r in rows:
            if recent is None or r["id"] not in recent:
                if recent is not None:
                    recent.append(r["id"])
                return dict(r)
        return dict(rows[0]) if rows else None
    finally:
        conn.close()


def stats(db_path: Optional[pathlib.Path] = None) -> dict:
    conn = _connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) as n FROM prompts").fetchone()["n"]
        sources = [r["source"] for r in conn.execute(
            "SELECT DISTINCT source FROM prompts WHERE source != '' ORDER BY source"
        ).fetchall()]
        latest = conn.execute(
            "SELECT MAX(created_at) as ts FROM prompts"
        ).fetchone()["ts"]
        return {
            "total": total,
            "sources": sources,
            "latest_ts": latest,
            "embeddings_available": _get_embed_model() is not None,
        }
    finally:
        conn.close()


def clear_library(db_path: Optional[pathlib.Path] = None) -> int:
    conn = _connect(db_path)
    try:
        n = conn.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
        conn.execute("DELETE FROM prompts")
        try:
            conn.execute("INSERT INTO prompts_fts(prompts_fts) VALUES('rebuild')")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        return n
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Node class
# ---------------------------------------------------------------------------


def _empty_tensor():
    if torch is None:
        return None
    return torch.zeros((1, 1, 1, 3), dtype=torch.float32)


class RayPromptLibrary:
    """Save/fetch prompts to a local SQLite library."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (MODES, {"default": MODE_FETCH}),
                "prompt_in": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "placeholder": "passthrough — written to DB in Save mode",
                }),
                "seed": ("INT", {"default": -1, "min": -1, "max": 2**31 - 1}),

                # Save mode widgets
                "save__source": ("STRING", {
                    "default": "manual",
                    "placeholder": "manual / local / dexter / civitai / ollama",
                }),
                "save__tags": ("STRING", {
                    "default": "",
                    "placeholder": "comma-separated tags",
                }),
                "save__image_path": ("STRING", {"default": ""}),
                "save__model": ("STRING", {"default": ""}),

                # Fetch mode widgets
                "fetch__tag": ("STRING", {"default": ""}),
                "fetch__source": ("STRING", {"default": ""}),
                "fetch__min_length": ("INT", {"default": 0, "min": 0, "max": 100000}),
                "fetch__contains": ("STRING", {"default": ""}),
                "fetch__exclude": ("STRING", {"default": ""}),
                "fetch__sort": (SORTS, {"default": SORT_RANDOM}),
                "fetch__similar_to": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "placeholder": "when set, ranks by similarity (needs sentence-transformers)",
                }),
            },
            "hidden": {"node_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING", "STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("prompt_single", "prompt_multiline", "image", "image_path")
    OUTPUT_IS_LIST = (True, True, True, True)
    FUNCTION = "process"
    CATEGORY = "Ray/Prompts📝"

    @classmethod
    def IS_CHANGED(cls, *args, **kwargs):
        return float("nan")

    def process(
        self,
        mode,
        prompt_in,
        seed,
        save__source,
        save__tags,
        save__image_path,
        save__model,
        fetch__tag,
        fetch__source,
        fetch__min_length,
        fetch__contains,
        fetch__exclude,
        fetch__sort,
        fetch__similar_to,
        node_id=None,
    ):
        node_key = str(node_id) if node_id is not None else "_default"
        seed_int = int(seed)
        seed_arg: Optional[int] = seed_int if seed_int >= 0 else None
        recent = _RECENT_BY_NODE.setdefault(node_key, deque(maxlen=_CACHE_MAX))

        mode = (mode or MODE_FETCH).strip()
        if mode == MODE_SAVE:
            return self._do_save(
                prompt_in=prompt_in,
                source=save__source,
                tags=save__tags,
                image_path=save__image_path,
                model=save__model,
                seed=seed_arg,
            )
        return self._do_fetch(
            tag=fetch__tag,
            source=fetch__source,
            min_length=fetch__min_length,
            contains=fetch__contains,
            exclude=fetch__exclude,
            sort=fetch__sort,
            similar_to=fetch__similar_to,
            seed=seed_arg,
            recent=recent,
        )

    def _do_save(self, prompt_in, source, tags, image_path, model, seed):
        res = save_prompt(
            prompt=prompt_in,
            source=source,
            tags=tags,
            image_path=image_path,
            model=model,
            seed=seed,
        )
        single = re.sub(r"\s+", " ", (prompt_in or "")).strip()
        return ([single], [prompt_in or ""], [_empty_tensor()], [image_path or ""])

    def _do_fetch(
        self, tag, source, min_length, contains, exclude, sort,
        similar_to, seed, recent,
    ):
        row = fetch_prompt(
            tag=tag,
            source=source,
            min_length=int(min_length),
            contains=contains,
            exclude=exclude,
            sort=sort,
            similar_to=similar_to,
            seed=seed,
            recent=recent,
        )
        if row is None:
            return ([""], [""], [_empty_tensor()], [""])
        multi = row["prompt"] or ""
        single = row.get("prompt_single") or re.sub(r"\s+", " ", multi).strip()
        return (
            [single],
            [multi],
            [_empty_tensor()],
            [row.get("image_path") or ""],
        )
