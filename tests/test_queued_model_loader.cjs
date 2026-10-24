const assert = require('node:assert/strict');
(async () => {
    const {planSweep, submitSweep, parseModels, LOADER_ID} = await import('../web/queued_model_loader.mjs');
    const outputTypes = new Set(['SaveImage']);
    const snapshot = () => ({output: {
        '1': {class_type: LOADER_ID, inputs: {model_name: 'a.safetensors', queued_models: '["b.safetensors","c.safetensors"]'}},
        '2': {class_type: 'KSampler', inputs: {model: ['1', 0], seed: 42, cfg: 7, steps: 20, positive: 'same prompt'}},
        '3': {class_type: 'SaveImage', inputs: {images: ['2', 0]}},
        '4': {class_type: LOADER_ID, inputs: {model_name: '', queued_models: '[""]'}},
    }, workflow: {nodes: [{id: 1, widgets_values: ['a.safetensors', '["b.safetensors","c.safetensors"]']} ]}});
    const original = snapshot(), before = structuredClone(original), plan = planSweep(original, {outputTypes});
    assert.deepEqual(plan.models, ['a.safetensors', 'b.safetensors', 'c.safetensors']);
    assert.deepEqual(original, before);
    const proxied = snapshot(); proxied.workflow.extra = new Proxy({saved: true}, {});
    assert.equal(planSweep(proxied, {outputTypes}).jobs[0].workflow.extra.saved, true);
    for (const [index, job] of plan.jobs.entries()) {
        assert.deepEqual(job.output['2'], original.output['2']);
        assert.equal(job.output['1'].inputs.model_name, plan.models[index]);
        assert.equal(job.output['1'].inputs.queued_models, '[]');
        assert.deepEqual(job.workflow.nodes[0].widgets_values, [plan.models[index], '[]']);
    }
    plan.jobs[0].output['2'].inputs.steps = 100;
    assert.equal(plan.jobs[1].output['2'].inputs.steps, 20);
    assert.equal(original.output['2'].inputs.steps, 20);
    assert.throws(() => parseModels('a', '[""]'), /every row/);
    assert.throws(() => parseModels('a', '{}'), /array/);
    assert.throws(() => parseModels('', '[]'), /every row/);
    const single = snapshot(); single.output['1'].inputs.queued_models = '[]';
    assert.equal(planSweep(single, {outputTypes}), null);
    assert.equal(planSweep(original, {outputTypes, partialExecutionTargets: ['unknown']}), null);
    const linked = snapshot(); linked.output['1'].inputs.model_name = ['5', 0];
    assert.throws(() => planSweep(linked, {outputTypes}), /Unlink/);
    const multiple = snapshot(); multiple.output['4'].inputs = {...multiple.output['1'].inputs};
    multiple.output['2'].inputs.second_model = ['4', 0];
    assert.throws(() => planSweep(multiple, {outputTypes}), /one Queued/);
    const randomized = snapshot(); randomized.output['2'].inputs.seed = -1;
    randomized.workflow.nodes.push({id: 2, widgets_values: [-1, 7, 20]});
    const randomPlan = planSweep(randomized, {outputTypes, widgetNames: {'2': ['seed', 'cfg', 'steps']}});
    assert.ok(randomPlan.jobs[0].output['2'].inputs.seed >= 0);
    assert.equal(new Set(randomPlan.jobs.map(job => job.output['2'].inputs.seed)).size, 1);
    assert.equal(randomPlan.jobs[0].workflow.nodes[1].widgets_values[0], randomPlan.jobs[0].output['2'].inputs.seed);
    for (const number of [0, -1, 50]) {
        const submitted = [], options = {previewMethod: 'none'};
        const result = await submitSweep(plan, number, options, async (position, job, received) => {
            assert.equal(received, options); submitted.push({position, model: job.output['1'].inputs.model_name});
            return {prompt_id: `job-${submitted.length}`, number: position === -1 ? -10 : position};
        });
        assert.deepEqual(submitted.map(item => item.model), plan.models);
        if (number !== 0) assert.ok(submitted[1].position < submitted[2].position);
        assert.equal(result.queued_model_jobs.length, 3);
    }
    let accepted = 0;
    await assert.rejects(submitSweep(plan, 0, undefined, async () => {
        if (accepted++) throw Error('connection lost');
        return {prompt_id: 'first', number: 1};
    }), /1 of 3 model jobs were queued/);
    console.log('Queued model workflow planning and submission tests passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
