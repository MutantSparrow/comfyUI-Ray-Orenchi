"""Filename templates for Save Image: a prefix such as ``Ray_{date}_{counter}`` becomes ``Ray_2026-10-16_0001``.

The saved file is exactly ``<stem>.<extension>``. The stem is built from literal text and tokens, then made safe to
use as a filename on Windows, macOS and Linux. web/save_name.js implements the same rules for the live preview, and
tests/filename_cases.json is run against both so they cannot drift apart.

Tokens (in braces):
  {date}              2026-10-16
  {time}              14-32-05            (colons are not allowed in filenames)
  {datetime}          2026-10-16T14-32-05
  {timestamp}         1792162325          (seconds since 1970)
  {counter} {counter:N}   next unused number in the folder, zero-padded to N digits (default 4)
  {index} {index:N}       position in the batch, from 1 (default no padding)
  {input}             1 or 2: which image input the file came from
  {hash} {hash:N}         N random hex characters (default 8, 4 to 32) so names never clash
  {widget:ID.NAME}        the value of widget NAME on node ID; add |N to keep at most N characters
"""

from __future__ import annotations

import os
import re
import secrets
import unicodedata

DEFAULT_TEMPLATE = "Ray_{date}_{counter}"
FALLBACK_STEM = "Ray"
MAX_STEM = 180             # leaves room for an extension and a collision suffix inside every filesystem's limit
VALUE_LIMIT = 60           # characters kept from a widget value unless the token says otherwise
NAMES = ("date", "time", "datetime", "timestamp", "counter", "index", "input", "hash", "widget")

# Shared with web/save_name.js: keep the two character classes identical.
ILLEGAL = re.compile('[<>:"/\\\\|?*\\x00-\\x1f\\x7f-\\x9f]')
SPACE = re.compile("[ \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+")
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_TOKEN = re.compile(r"\{([^{}]*)\}")


class TemplateError(ValueError):
    """The template cannot be turned into a filename; the message says what to fix."""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _number(text, name, low, high, default):
    if text == "":
        return default
    if not re.fullmatch(r"\d{1,3}", text) or not low <= int(text) <= high:
        raise TemplateError(f"{{{name}:{text}}} needs a number from {low} to {high}.")
    return int(text)


def _token(body):
    base, bar, limit = body.partition("|")
    name, _, arg = base.partition(":")
    name = name.strip().lower()
    if name not in NAMES:
        raise TemplateError(f"Unknown filename token {{{body}}}. Tokens: " + ", ".join("{" + n + "}" for n in NAMES) + ".")
    if bar and name != "widget":
        raise TemplateError(f"{{{name}}} does not take a |length.")
    if name in ("date", "time", "datetime", "timestamp", "input"):
        if arg:
            raise TemplateError(f"{{{name}}} takes no options.")
        return ("token", name, {})
    if name == "counter":
        return ("token", name, {"width": _number(arg.strip(), name, 1, 12, 4)})
    if name == "index":
        return ("token", name, {"width": _number(arg.strip(), name, 1, 12, 1)})
    if name == "hash":
        return ("token", name, {"length": _number(arg.strip(), name, 4, 32, 8)})
    node_id, dot, widget = arg.strip().rpartition(".")
    if not dot or not node_id or not widget or re.search(r"[\s{}|]", node_id + widget):
        raise TemplateError("{widget:...} needs a node id and a widget name, like {widget:12.seed}.")
    return ("token", name, {"node": node_id, "widget": widget, "limit": _number(limit.strip(), "widget|", 1, 200, VALUE_LIMIT) if bar else VALUE_LIMIT})


def parse(template):
    """The template as a list of ("text", str) and ("token", name, options) parts. Raises TemplateError."""
    template = str(template)
    parts, position = [], 0
    for match in _TOKEN.finditer(template):
        parts.append(("text", _plain(template[position:match.start()])))
        parts.append(_token(match.group(1)))
        position = match.end()
    parts.append(("text", _plain(template[position:])))
    if sum(1 for p in parts if p[0] == "token" and p[1] == "counter") > 1:
        raise TemplateError("Use {counter} only once.")
    return [p for p in parts if p != ("text", "")]


def _plain(text):
    if "{" in text or "}" in text:
        raise TemplateError("A { or } is not part of a token. Write tokens like {date} or {counter:4}.")
    return text


def has_counter(parts):
    return any(p[0] == "token" and p[1] == "counter" for p in parts)


# ---------------------------------------------------------------------------
# Making text safe
# ---------------------------------------------------------------------------

def clean_text(text):
    """Literal text from the template: reserved characters and spaces become underscores, nothing else changes."""
    return SPACE.sub("_", ILLEGAL.sub("_", unicodedata.normalize("NFC", str(text))))


def clean_value(value, limit=VALUE_LIMIT):
    """A value taken from a widget: made safe, runs of underscores collapsed, trimmed and cut to `limit` characters."""
    # Braces are dropped too, so a value like "{hash}" is never mistaken for a token anywhere downstream.
    text = SPACE.sub("_", ILLEGAL.sub("_", unicodedata.normalize("NFC", _text(value)).replace("{", "_").replace("}", "_")))
    text = re.sub("_{2,}", "_", text).strip("_-. ")
    return text[:limit].rstrip("_-. ")


def _text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return str(int(value)) if value == int(value) and abs(value) < 1e15 else repr(value)
    return str(value)


def finish_stem(stem):
    """Last pass on a whole stem: no leading or trailing dots and spaces, no Windows device names, never empty."""
    stem = stem.lstrip(". ")[:MAX_STEM].rstrip(". ")
    if stem.split(".")[0].upper() in RESERVED:
        stem = "_" + stem
    return stem or FALLBACK_STEM


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _piece(part, ctx):
    kind, name, options = part
    now = ctx["now"]
    if name == "date":
        return now.strftime("%Y-%m-%d")
    if name == "time":
        return now.strftime("%H-%M-%S")
    if name == "datetime":
        return now.strftime("%Y-%m-%dT%H-%M-%S")
    if name == "timestamp":
        return str(int(now.timestamp()))
    if name == "input":
        return str(ctx.get("input", 1))
    if name == "index":
        return str(ctx.get("index", 1)).zfill(options["width"])
    if name == "hash":
        return (ctx.get("hash") or secrets.token_hex(16))[: options["length"]]
    if name == "widget":
        lookup = ctx.get("widgets")
        value = lookup(options["node"], options["widget"]) if lookup else None
        return clean_value(value, options["limit"])
    raise TemplateError(f"{{{name}}} cannot be used here.")


def render(parts, ctx, counter=None):
    """The finished stem. `ctx`: now (datetime), index, input, widgets(node, name) -> value, hash (fixed for tests).
    `counter` fills {counter}; without one a template that has it renders 0."""
    out = []
    for part in parts:
        if part[0] == "text":
            out.append(clean_text(part[1]))
        elif part[1] == "counter":
            out.append(str(counter or 0).zfill(part[2]["width"]))
        else:
            out.append(_piece(part, ctx))
    return finish_stem("".join(out))


def collision_stem(stem, attempt):
    """The stem for the nth try when a file already exists: `name`, `name-2`, `name-3`, ..."""
    return stem if attempt <= 1 else stem[: MAX_STEM - len(str(attempt)) - 1].rstrip(". ") + f"-{attempt}"


def _scan_pattern(parts, ctx, extension):
    pieces = []
    for part in parts:
        if part[0] == "text":
            pieces.append(re.escape(clean_text(part[1])))
        elif part[1] == "counter":
            pieces.append(r"(\d+)")
        elif part[1] == "hash":
            pieces.append(f"[0-9a-fA-F]{{{part[2]['length']}}}")
        else:
            pieces.append(re.escape(_piece(part, ctx)))
    flags = re.IGNORECASE if os.name == "nt" or os.uname().sysname == "Darwin" else 0
    return re.compile("^" + "".join(pieces) + re.escape(extension) + "$", flags)


def next_counter(directory, parts, ctx, extension):
    """One more than the highest number already used by files that match this template in `directory`."""
    pattern = _scan_pattern(parts, ctx, extension)
    highest = 0
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                match = pattern.match(entry.name)
                if match:
                    highest = max(highest, int(match.group(1)))
    except FileNotFoundError:
        pass
    return highest + 1


def create_unique(directory, parts, ctx, extension, attempts=10000):
    """Open a new file named from the template for writing in `directory` and return (path, stream). The file is
    created exclusively, so nothing is ever overwritten, even by a parallel run: if the name is taken the counter
    moves on, or a -2, -3... suffix is added when the template has none."""
    counter = next_counter(directory, parts, ctx, extension) if has_counter(parts) else None
    for attempt in range(1, attempts + 1):
        stem = render(parts, ctx, counter) if counter is not None else collision_stem(render(parts, ctx), attempt)
        path = directory / f"{stem}{extension}"
        try:
            return path, path.open("xb")
        except FileExistsError:
            if counter is not None:
                counter += 1
    raise OSError(f"Could not find an unused filename in {directory}.")
