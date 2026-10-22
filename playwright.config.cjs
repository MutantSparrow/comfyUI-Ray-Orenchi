const {defineConfig} = require('@playwright/test');
module.exports = defineConfig({
    testDir: './tests/browser',
    timeout: 180000,
    workers: 1,
    retries: 0,
    reporter: 'list',
    use: {browserName: 'chromium', headless: true, viewport: {width: 1280, height: 900}, trace: 'retain-on-failure'},
    webServer: [
        {command: 'python tests/serve_folders.py 8200', url: 'http://127.0.0.1:8200/fixture', reuseExistingServer: false},
        {command: 'node tests/serve_analog.cjs 8199', url: 'http://127.0.0.1:8199/', reuseExistingServer: false},
        {command: 'node tests/serve_save_image.cjs', url: 'http://127.0.0.1:8202/', reuseExistingServer: false},
    ],
});
