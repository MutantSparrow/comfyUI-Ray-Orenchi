import { cleanValue, finishStem } from "./save_name.js";

export function sourceStem(value, fallback = "Model") {
    let name = String(value || "").trim().replace(/^"|"$/g, "").replaceAll("\\", "/").replace(/\/+$/, "")
        .replace(/^(checkpoints|diffusion_models|loras): /, "").split("/").pop() || "";
    name = name.replace(/\.(safetensors\.index\.json|safetensors|ckpt|gguf|pth|pt|bin|sft)$/i, "");
    return cleanValue(name, 28) || fallback;
}
const settingText = value => typeof value === "number" ? Number.isInteger(value) ? value.toFixed(0) : value.toFixed(10).replace(/0+$/, "").replace(/\.$/, "") : String(value ?? "");
export function nameSignature(settings = {}) {
    const values = [["components", "diffusion"], ["mismatch", "forbid"], ["seed", 0], ["density", .5],
        ["lambda", 1], ["top_trim", .1], ["bottom_trim", .01], ["block_weights", "{}"], ["fast_merge", false]]
        .map(([key, fallback]) => settingText(settings[key] ?? fallback));
    try {
        const block = JSON.parse(values[7]);
        values[7] = JSON.stringify(block && !Array.isArray(block) && typeof block === "object"
            ? Object.fromEntries(Object.keys(block).sort().map(key => [key, settingText(block[key])])) : block);
    } catch { /* Backend validation reports malformed block weights at execution. */ }
    let digest = 2166136261;
    for (const byte of new TextEncoder().encode(values.join("\x1f"))) digest = Math.imul(digest ^ byte, 16777619) >>> 0;
    return digest.toString(16).padStart(8, "0");
}
export function mergeName({ a = "", b = "", base = "", strategy = "LERP", weight_a = .5,
    weight_format = "bf16", settings = {}, now = new Date() } = {}) {
    const names = [];
    if (!["LERP", "SLERP"].includes(strategy)) names.push(`Base-${sourceStem(base, "Base")}`);
    const ratio = value => (Number(value) * 100).toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
    const two = value => String(value).padStart(2, "0");
    const time = `${now.getFullYear()}${two(now.getMonth() + 1)}${two(now.getDate())}-${two(now.getHours())}${two(now.getMinutes())}${two(now.getSeconds())}`;
    names.push(`A-${sourceStem(a, "A")}`, `B-${sourceStem(b, "B")}`, strategy, `${ratio(weight_a)}-${ratio(1 - weight_a)}`,
        weight_format, nameSignature(settings), time);
    return finishStem(names.join("_"));
}

const widget = (node, name) => node?.widgets?.find(item => item.name === name);
const linkedNode = (node, name) => {
    const input = node?.inputs?.find(input => input.name === name || input.widget?.name === name);
    const link = node?.graph?.links?.get?.(input?.link) || node?.graph?.links?.[input?.link];
    return link ? node.graph.getNodeById(link.origin_id) : null;
};
export function stringValue(node, name) {
    const source = linkedNode(node, name);
    if (!source) return widget(node, name)?.value ?? "";
    for (const key of ["value", "text", "string"]) if (typeof widget(source, key)?.value === "string") return widget(source, key).value;
    return source._rayMergeName?.name || "[connected]";
}
export function graphSourceName(node, seen = new Set()) {
    if (!node || seen.has(node) || seen.size >= 64) return "";
    seen.add(node);
    if (node._rayMergeName?.name) return node._rayMergeName.name;
    let connected = false;
    for (const name of ["model", "model_data", "data_a", "model_a"]) {
        const upstream = linkedNode(node, name), found = upstream && graphSourceName(upstream, seen);
        connected ||= !!upstream;
        if (found) return found;
    }
    if (connected) return "";
    // A connected legacy path takes precedence over Load Model As's local picker.
    const fields = linkedNode(node, "path") ? ["path"] : ["model_name", "unet_name", "ckpt_name", "model_path", "path"];
    for (const name of fields) { const value = stringValue(node, name); if (value) return value; }
    return "";
}
export function mergeSources(node) {
    const source = (names, fallback) => {
        for (const name of names) { const upstream = linkedNode(node, name); if (upstream) return graphSourceName(upstream) || fallback; }
        return stringValue(node, names.at(-1)) || "";
    };
    return { a: source(["model_a", "data_a", "path_a"], "A"), b: source(["model_b", "data_b", "path_b"], "B"),
        base: source(["base_model", "base_data", "base_path"], "Base") };
}
