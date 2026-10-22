const {test, expect} = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
for (const [name, url] of [
    ['Folders: scrolling, lazy loading, large folders, search, media and deletion', 'http://127.0.0.1:8200/'],
    ['Folders: multiple prompt cards and clipboard', 'http://127.0.0.1:8200/tests/folders_prompts_browser.html'],
    ['Analog controls', 'http://127.0.0.1:8199/'],
    ['Input connector alignment', 'http://127.0.0.1:8199/tests/panel_links_browser.html'],
    ['Save Image comparison interactions', 'http://127.0.0.1:8202/'],
]) {
    test(name, async ({page, request}) => {
        if (name.startsWith('Folders:')) {
            const reset = await request.post('http://127.0.0.1:8200/fixture/reset');
            expect(reset.ok()).toBe(true);
        }
        await page.goto(url);
        const summary = page.locator('summary').first();
        await expect(summary).toHaveText(/checks passed|Regression failed/, {timeout: 170000});
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
