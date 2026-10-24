// Pure workflow planning; never edits the live graph or the caller's snapshot.
export const LOADER_ID = "RayQueuedModelLoader";
export const PLACEHOLDER = "Select a diffusion model…";
// Match the native API's JSON boundary, including Vue-backed workflow properties.
const clone = value => JSON.parse(JSON.stringify(value));

export function parseModels(first, additional = "[]") {
    let rest;
    try { rest = JSON.parse(additional || "[]"); }
    catch { throw Error("The queued model list is invalid. Reselect the models before running."); }
    if (!Array.isArray(rest)) throw Error("The queued model list must be an array.");
    const models = [first, ...rest];
    if (models.some(name => typeof name !== "string" || !name.trim() || name === PLACEHOLDER))
        throw Error("Choose a model for every row, or remove the empty row.");
    return models;
}

function reachableNodes(output, roots) {
    const visited = new Set(), pending = [...roots];
    while (pending.length) {
        const id = String(pending.pop());
        if (visited.has(id) || !output[id]) continue;
        visited.add(id);
        for (const input of Object.values(output[id].inputs || {}))
            if (Array.isArray(input) && input.length === 2 && output[String(input[0])]) pending.push(input[0]);
    }
    return visited;
}

function savedWidget(workflow, id, name, value, widgetNames) {
    const saved = workflow?.nodes?.find(node => String(node.id) === id);
    if (!saved?.widgets_values) return;
    if (!Array.isArray(saved.widgets_values)) { saved.widgets_values[name] = value; return; }
    const names = widgetNames?.[id] || (name === "model_name" || name === "queued_models" ? ["model_name", "queued_models"] : []);
    const index = names.indexOf(name);
    if (index >= 0) saved.widgets_values[index] = value;
}

export function planSweep(prompt, { outputTypes, partialExecutionTargets, widgetNames } = {}) {
    const output = prompt.output || {};
    const roots = partialExecutionTargets?.length ? partialExecutionTargets
        : Object.keys(output).filter(id => outputTypes?.has(output[id].class_type));
    const reachable = reachableNodes(output, roots);
    const loaders = [...reachable].filter(id => output[id].class_type === LOADER_ID);
    const selections = loaders.map(id => {
        const inputs = output[id].inputs;
        if (Array.isArray(inputs.queued_models)) throw Error("Keep the queued model list unlinked; edit models on the loader.");
        if (Array.isArray(inputs.model_name)) {
            if (JSON.parse(inputs.queued_models || "[]").length)
                throw Error("Unlink the first model before adding model rows.");
            return { id, models: null };
        }
        return { id, models: parseModels(inputs.model_name, inputs.queued_models) };
    });
    const sweeps = selections.filter(item => item.models?.length > 1);
    if (!sweeps.length) return null;
    if (sweeps.length > 1) throw Error("Use one Queued Model Loader with multiple rows per sweep. Other loaders can each select one model.");
    const { id, models } = sweeps[0];
    if (!prompt.workflow?.nodes?.some(node => String(node.id) === id))
        throw Error("Place the multi-model Queued Model Loader on the main canvas, outside subgraphs.");
    for (const nodeId of reachable) {
        const node = output[nodeId];
        if (node.class_type === "RayModelCard" && node.inputs.seed_mode === "randomize")
            throw Error("Set Model Card's seed mode to Fixed, Increment or Decrement so every model uses the same seeds.");
    }
    const base = clone(prompt);
    // Resolve conventional server-side random seeds once for the entire sweep.
    for (const nodeId of reachable) {
        for (const [key, value] of Object.entries(base.output[nodeId].inputs || {})) {
            if ((key === "seed" || key === "noise_seed") && value === -1) {
                const seed = new Uint32Array(1);
                globalThis.crypto.getRandomValues(seed);
                base.output[nodeId].inputs[key] = seed[0];
                savedWidget(base.workflow, nodeId, key, seed[0], widgetNames);
            }
        }
    }
    const jobs = models.map(model => {
        const job = clone(base);
        job.output[id].inputs.model_name = model;
        job.output[id].inputs.queued_models = "[]";
        savedWidget(job.workflow, id, "model_name", model, widgetNames);
        savedWidget(job.workflow, id, "queued_models", "[]", widgetNames);
        return job;
    });
    return { id, models, jobs };
}

export async function submitSweep(plan, number, options, submit, progress = () => {}) {
    const accepted = [];
    try {
        for (let index = 0; index < plan.jobs.length; index++) {
            // Inserting repeatedly at the front would reverse the row order.
            const position = index && number !== 0
                ? accepted[0].number + index / (plan.jobs.length + 1) : number;
            const result = await submit(position, plan.jobs[index], options);
            if (!result?.prompt_id) throw Error("ComfyUI did not accept the queued job.");
            accepted.push(result);
            progress(index + 1, plan.jobs.length);
        }
    } catch (error) {
        if (accepted.length) error.message = `${accepted.length} of ${plan.jobs.length} model jobs were queued. ${error.message}`;
        throw error;
    }
    return { ...accepted[0], queued_model_jobs: accepted.map(result => result.prompt_id) };
}
