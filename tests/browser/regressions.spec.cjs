const {test, expect} = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
for (const [name, url] of [
    ['Folders: scrolling, lazy loading, large folders, search, media and deletion', 'http://127.0.0.1:8200/'],
    ['Folders: multiple prompt cards and clipboard', 'http://127.0.0.1:8200/tests/folders_prompts_browser.html'],
    ['Analog controls', 'http://127.0.0.1:8199/'],
    ['Input connector alignment', 'http://127.0.0.1:8199/tests/panel_links_browser.html'],
    ['Save Image comparison interactions', 'http://127.0.0.1:8202/'],
    ['Model Card name builder, settings, clipboard and reload', 'http://127.0.0.1:8202/tests/model_card_browser.html'],
    ['Model Tools metadata, reports and source dialogs', 'http://127.0.0.1:8203/'],
    ['Folders refresh after workflow completion', 'http://127.0.0.1:8200/tests/folders_execution_browser.html'],
]) {
    test(name, async ({page, request}) => {
        if (name.startsWith('Folders:')) {
            const reset = await request.post('http://127.0.0.1:8200/fixture/reset');
            expect(reset.ok()).toBe(true);
        }
        await page.goto(url);
        const summary = page.locator('summary').first();
        await expect(summary).toHaveText(/checks passed|Regression failed/, {timeout: 290000});
        const results = await page.locator('#results').textContent();
        expect(await summary.textContent(), results).toMatch(/\d+ checks passed/);
    });
}

test('Offline blinded pixel-art review and exported judgments', async ({page}) => {
    const template = fs.readFileSync(path.join(__dirname, '../../benchmarks/pixel_art/pairwise.html'), 'utf8');
    const image = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII=';
    const pairs = ['one', 'two'].map(id => ({case: id, source: image,
        left: {method: 'hidden-method-a', image}, right: {method: 'hidden-method-b', image}}));
    await page.setContent(template.replace('/* PAIRS */ []', JSON.stringify(pairs)));
    await expect(page.locator('#progress')).toContainText('Pair 1 of 2');
    await expect(page.locator('body')).not.toContainText('hidden-method-a');
    await page.locator('#reviewer').fill('test reviewer');
    await page.locator('#notes').fill('cleaner contours');
    await page.locator('#left').click();
    await expect(page.locator('#progress')).toContainText('Pair 2 of 2');
    await page.locator('#tie').click();
    await expect(page.locator('#status')).toContainText('Review complete');
    const downloadPromise = page.waitForEvent('download');
    await page.locator('#export').click();
    const download = await downloadPromise;
    const result = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
    expect(result.reviewer).toBe('test reviewer');
    expect(result.votes.map(vote => vote.choice)).toEqual(['left', 'tie']);
    expect(result.votes[0].notes).toBe('cleaner contours');
    expect(result.votes[0].winner).toBe('hidden-method-a');
    await page.locator('#back').click();
    await expect(page.locator('#notes')).toHaveValue('cleaner contours');
});

for (const [surface, index] of [['classic', 0], ['Nodes 2.0', 1]]) {
    test(`Model Card picker accepts pointer input (${surface})`, async ({page}) => {
        await page.goto('http://127.0.0.1:8202/tests/model_card_browser.html');
        await expect(page.locator('#summary')).toHaveText(/\d+ checks passed/);
        await page.locator('details').evaluate(element => { element.open = false; });
        const card = page.locator('.card').nth(index);
        const source = card.getByLabel('Card name', {exact:true});
        await source.fill('');
        const choose = card.getByRole('button', {name:'Build card name',exact:true});
        await choose.click();
        const dialog = page.getByRole('dialog', {name:'Build card name',exact:true});
        await dialog.getByRole('button', {name:'Widget value…',exact:true}).click();
        const picker = dialog.locator('.ray-name-widgets').last();
        await expect(picker).toBeVisible();
        // Real pointer clicks check hit testing; HTMLElement.click() bypasses it.
        await picker.locator('button[title="{widget:13.ckpt_name}"]').click({timeout:3000});
        const editor = dialog.getByRole('textbox', {name:'Card name',exact:true});
        await expect(editor).toHaveValue('{widget:13.ckpt_name}');
        await expect(dialog.locator('.ray-name-preview')).toHaveText('My SDXL');
        await editor.fill('Benchmark');
        await dialog.getByRole('button', {name:'Widget value…',exact:true}).click();
        const filter = picker.getByRole('textbox', {name:'Filter widgets'});
        await filter.click();
        await filter.fill('unet_name');
        await expect(picker.locator('button[title="{widget:13.ckpt_name}"]')).toHaveCount(0);
        await picker.locator('button[title="{widget:12.unet_name}"]').click();
        await expect(editor).toHaveValue('Benchmark {widget:12.unet_name}');
        await expect(dialog.locator('.ray-name-preview')).toHaveText('Benchmark Flux Dev.v1');
        await dialog.getByRole('button', {name:'Done',exact:true}).click();
        await expect(dialog).toHaveCount(0);
        await expect(source).toHaveValue('Benchmark {widget:12.unet_name}');
        await choose.click();
        await expect(editor).toHaveValue('Benchmark {widget:12.unet_name}');
        await page.keyboard.press('Escape');
        await expect(dialog).toHaveCount(0);
    });
}
