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
MODE_BROWSE = "Browse"
# Legacy name — old workflows serialized "Fetch"; normalized to Browse in
# process(). Kept as a constant so external tests / imports don't break.
MODE_FETCH = "Fetch"
MODES = [MODE_SAVE, MODE_BROWSE]

SORT_RANDOM = "random"
SORT_RECENT = "most_recent"
SORT_OLDEST = "oldest"
SORT_LONGEST = "longest"
SORT_SHORTEST = "shortest"
SORT_SOURCE = "source"
SORT_SIMILARITY = "similarity"
SORTS = [SORT_RANDOM, SORT_RECENT, SORT_LONGEST]
BROWSE_SORTS = [
    SORT_RECENT, SORT_OLDEST, SORT_LONGEST, SORT_SHORTEST,
    SORT_SOURCE, SORT_SIMILARITY,
]

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


def fetch_by_id(
    row_id: int,
    db_path: Optional[pathlib.Path] = None,
) -> Optional[dict]:
    """Direct-load a single row by primary key. Returns None if absent."""
    try:
        rid = int(row_id)
    except (TypeError, ValueError):
        return None
    if rid < 0:
        return None
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM prompts WHERE id = ?", (rid,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _fts_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1 FROM prompts_fts LIMIT 1")
        return True
    except sqlite3.OperationalError:
        return False


def _fts_escape(q: str) -> str:
    """Escape a keyword query for FTS5 MATCH. Wrap each bare token in double
    quotes so punctuation/operators are treated as literals; join with AND."""
    tokens = re.findall(r"[A-Za-z0-9_]+", q or "")
    if not tokens:
        return ""
    return " AND ".join(f'"{t}"' for t in tokens)


def _row_to_dict(row) -> dict:
    """sqlite3.Row → JSON-safe dict. Truncates prompt to 240 chars for listing."""
    d = dict(row)
    full = d.get("prompt") or ""
    d["prompt_preview"] = full[:240] + ("…" if len(full) > 240 else "")
    d["length"] = len(full)
    # Strip embedding blob — not JSON-serializable and never needed by UI.
    d.pop("embedding", None)
    return d


def search_prompts(
    q: str = "",
    source: str = "",
    tag: str = "",
    sort: str = SORT_RECENT,
    limit: int = 200,
    offset: int = 0,
    db_path: Optional[pathlib.Path] = None,
) -> dict:
    """Search + sort + paginate the library. Returns {rows, total, has_embeddings}.

    Keyword `q` uses FTS5 MATCH when the virtual table is present, LIKE fallback
    otherwise. `sort=similarity` embeds `q` and ranks by cosine over rows that
    match the base filters and have an embedding blob — falls back to `most_recent`
    when embeddings unavailable.
    """
    limit = max(1, min(int(limit or 200), 2000))
    offset = max(0, int(offset or 0))
    conn = _connect(db_path)
    try:
        # Tag / source filter shared across paths.
        where_parts: list = []
        params: list = []
        if source:
            where_parts.append("source = ?")
            params.append(source)
        if tag:
            for t in [s.strip() for s in tag.split(",") if s.strip()]:
                where_parts.append("tags LIKE ?")
                params.append(f"%{t}%")

        # Similarity branch — embed q, cosine over candidate pool.
        if sort == SORT_SIMILARITY and q.strip():
            emb = _embed(q.strip())
            if emb is not None:
                candidate_sql = (
                    "SELECT * FROM prompts"
                    + (" WHERE " + " AND ".join(where_parts + ["embedding IS NOT NULL"])
                       if where_parts else " WHERE embedding IS NOT NULL")
                )
                rows = conn.execute(candidate_sql, params).fetchall()
                if rows:
                    mat = np.vstack([
                        np.frombuffer(r["embedding"], dtype=np.float32)
                        for r in rows
                    ])
                    q_arr = np.frombuffer(emb, dtype=np.float32)
                    order = _cosine_argsort(q_arr, mat)
                    total = len(rows)
                    picked = [rows[int(i)] for i in order[offset:offset + limit]]
                    return {
                        "rows": [_row_to_dict(r) for r in picked],
                        "total": total,
                        "has_embeddings": True,
                        "used": "similarity",
                    }
            # No embedder or no candidates — fall through to keyword ranking.

        # Keyword branch — FTS5 when available, LIKE otherwise.
        use_fts = bool(q.strip()) and _fts_available(conn)
        if use_fts:
            match_query = _fts_escape(q)
        else:
            match_query = ""

        order_sql = {
            SORT_RECENT: "ORDER BY p.created_at DESC",
            SORT_OLDEST: "ORDER BY p.created_at ASC",
            SORT_LONGEST: "ORDER BY length(p.prompt) DESC",
            SORT_SHORTEST: "ORDER BY length(p.prompt) ASC",
            SORT_SOURCE: "ORDER BY p.source ASC, p.created_at DESC",
            SORT_RANDOM: "ORDER BY RANDOM()",
            SORT_SIMILARITY: "ORDER BY p.created_at DESC",  # fallback
        }.get(sort, "ORDER BY p.created_at DESC")

        if use_fts and match_query:
            base = (
                "FROM prompts_fts f JOIN prompts p ON p.id = f.rowid "
                "WHERE prompts_fts MATCH ?"
            )
            local_params = [match_query]
            if where_parts:
                base += " AND " + " AND ".join(where_parts)
                local_params.extend(params)
            total = conn.execute(
                f"SELECT COUNT(*) as n {base}", local_params
            ).fetchone()["n"]
            rows = conn.execute(
                f"SELECT p.* {base} {order_sql} LIMIT ? OFFSET ?",
                local_params + [limit, offset],
            ).fetchall()
        else:
            base = "FROM prompts p"
            local_params = list(params)
            local_where = list(where_parts)
            if q.strip():
                local_where.append("p.prompt LIKE ?")
                local_params.append(f"%{q.strip()}%")
            if local_where:
                base += " WHERE " + " AND ".join(local_where)
            total = conn.execute(
                f"SELECT COUNT(*) as n {base}", local_params
            ).fetchone()["n"]
            rows = conn.execute(
                f"SELECT p.* {base} {order_sql} LIMIT ? OFFSET ?",
                local_params + [limit, offset],
            ).fetchall()

        return {
            "rows": [_row_to_dict(r) for r in rows],
            "total": int(total),
            "has_embeddings": _get_embed_model() is not None,
            "used": "fts" if use_fts else ("like" if q.strip() else "list"),
        }
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

    DESCRIPTION = (
        "Local SQLite prompt library. Two modes on the same node:\n"
        "  • `Save`   — write `prompt_in` to the DB with source, tags, "
        "image path, model.\n"
        "  • `Browse` — inline searchable table; pick a row and its "
        "prompt + image path flow onto the outputs.\n\n"
        "Browse panel supports full-text search, tag / source filters, "
        "and multiple sort orders (recent, longest, similarity by "
        "embedding). Right-click a row to select — the node then serves "
        "that row on every subsequent run."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (MODES, {
                    "default": MODE_BROWSE,
                    "tooltip": "Save writes prompt_in to the library. Browse serves rows from the table.",
                }),
                "prompt_in": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "placeholder": "Passthrough — written to DB in Save mode",
                    "tooltip": "Save mode: prompt text to store. Passed through on the outputs regardless of mode.",
                }),
                "seed": ("INT", {
                    "default": -1, "min": -1, "max": 2**31 - 1,
                    "tooltip": "-1 for random; any >=0 value is reproducible.",
                }),

                # Save mode widgets
                "save__source": ("STRING", {
                    "default": "manual",
                    "placeholder": "manual / local / dexter / civitai / ollama",
                    "tooltip": "Save mode: source label attached to this row.",
                }),
                "save__tags": ("STRING", {
                    "default": "",
                    "placeholder": "Comma-separated tags",
                    "tooltip": "Save mode: comma-separated tags stored with this row.",
                }),
                "save__image_path": ("STRING", {"default": "",
                                                 "tooltip": "Save mode: absolute path to the image this prompt produced (optional)."}),
                "save__model": ("STRING", {"default": "",
                                            "tooltip": "Save mode: model / checkpoint that produced the row (optional)."}),

                # Browse mode widgets. The JS renders a live table; this INT
                # captures the user's row selection so the graph run picks
                # the same row, and survives workflow save/load.
                "browse__selected_id": (
                    "INT",
                    {"default": -1, "min": -1, "max": 2**31 - 1,
                     "tooltip": "Browse mode: DB row id selected in the panel."},
                ),
                "browse__last_query": ("STRING", {"default": "",
                                                   "tooltip": "Browse mode: last search query (managed by the panel)."}),
            },
            "optional": {
                "show_preview": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Render the row's image inline in the node.",
                }),
            },
            "hidden": {"node_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING", "STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("prompt_single", "prompt_multiline", "image", "image_path")
    OUTPUT_TOOLTIPS = (
        "Whitespace-collapsed single-line prompt (list).",
        "Prompt with original newlines preserved (list).",
        "Image tensor stored with the selected row (BHWC float32 [0,1]).",
        "Path to the associated image on disk, if any.",
    )
    OUTPUT_IS_LIST = (True, True, True, True)
    FUNCTION = "process"
    CATEGORY = "👑 Ray/💬 LLM"

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
        browse__selected_id,
        browse__last_query="",
        show_preview=True,
        node_id=None,
        **_legacy,
    ):
        seed_int = int(seed)
        seed_arg: Optional[int] = seed_int if seed_int >= 0 else None

        mode = (mode or MODE_BROWSE).strip()
        if mode == MODE_SAVE:
            result = self._do_save(
                prompt_in=prompt_in,
                source=save__source,
                tags=save__tags,
                image_path=save__image_path,
                model=save__model,
                seed=seed_arg,
            )
        else:
            # Legacy "Fetch" mode from older workflows falls through to Browse.
            result = self._do_browse(selected_id=browse__selected_id)

        # Dispatch inline preview if the selected/saved row has an image path
        # and the user hasn't toggled the preview off.
        if show_preview:
            try:
                image_path_list = result[3] if len(result) >= 4 else [""]
                path = image_path_list[0] if image_path_list else ""
                if path:
                    try:
                        from _common import send_preview
                    except ImportError:
                        from ._common import send_preview  # type: ignore
                    send_preview(node_id, path)
            except Exception:
                pass

        return result

    def _do_save(self, prompt_in, source, tags, image_path, model, seed):
        save_prompt(
            prompt=prompt_in,
            source=source,
            tags=tags,
            image_path=image_path,
            model=model,
            seed=seed,
        )
        single = re.sub(r"\s+", " ", (prompt_in or "")).strip()
        return ([single], [prompt_in or ""], [_empty_tensor()], [image_path or ""])

    def _do_browse(self, selected_id):
        try:
            rid = int(selected_id)
        except (TypeError, ValueError):
            rid = -1
        if rid < 0:
            raise RuntimeError(
                "no prompt selected — pick a row in the Browse table"
            )
        row = fetch_by_id(rid)
        if row is None:
            raise RuntimeError(
                f"selected prompt id={rid} no longer in the library"
            )
        multi = row["prompt"] or ""
        single = row.get("prompt_single") or re.sub(r"\s+", " ", multi).strip()
        return (
            [single],
            [multi],
            [_empty_tensor()],
            [row.get("image_path") or ""],
        )
