// Metadata stays a string map until a user explicitly chooses JSON for a value.
export function parseMetadataJSON(text) {
    const parsed = JSON.parse(text), stack = [];
    const tokens = text.match(/"(?:\\.|[^"\\])*"|[{}\[\]:,]|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null/g) || [];
    for (const token of tokens) {
        const top = stack.at(-1);
        if (token === "{") stack.push({ keys: new Set(), key: true });
        else if (token === "[") stack.push({ key: false });
        else if (token === "}" || token === "]") stack.pop();
        else if (token === "," && top?.keys) top.key = true;
        else if (token.startsWith('"') && top?.keys && top.key) {
            const key = JSON.parse(token);
            if (top.keys.has(key)) throw new Error(`Duplicate metadata key: ${key}`);
            top.keys.add(key); top.key = false;
        } else if (/^-?\d+$/.test(token) && !Number.isSafeInteger(Number(token))) {
            throw new Error("This integer exceeds the editor's safe range. Preserve it as text or process the sidecar without editing.");
        }
    }
    return parsed;
}

export function metadataRows(object) {
    if (!object || Array.isArray(object) || typeof object !== "object") throw new Error("Metadata must be an object.");
    return Object.entries(object).map(([key, value]) => ({ key, type: typeof value === "string" ? "text" : "json",
        value: typeof value === "string" ? value : JSON.stringify(value, null, 2) }));
}

export function rowsToMetadata(rows) {
    const result = Object.create(null);
    for (const row of rows) {
        if (Object.hasOwn(result, row.key)) throw new Error(`Duplicate metadata key: ${row.key}`);
        result[row.key] = row.type === "json" ? parseMetadataJSON(row.value) : row.value;
    }
    return result;
}

export function mergeFields(strategy) {
    return { density: /^(TIES|DARE|DELLA)/.test(strategy), lambda: strategy.startsWith("DELLA"),
        top_trim: strategy.startsWith("Breadcrumbs"), bottom_trim: strategy.startsWith("Breadcrumbs"),
        seed: /^(DARE|DELLA)/.test(strategy), base: !["LERP", "SLERP"].includes(strategy) };
}

export function filterTensors(rows, query, page = 0, pageSize = 100) {
    const q = query.toLowerCase();
    const filtered = rows.filter(row => `${row.name} ${row.dtype} ${row.shape}`.toLowerCase().includes(q));
    const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
    page = Math.max(0, Math.min(pages - 1, page));
    return { rows: filtered.slice(page * pageSize, (page + 1) * pageSize), total: filtered.length, page, pages };
}
