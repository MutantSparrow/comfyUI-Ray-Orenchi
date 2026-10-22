const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const tests = fs.readdirSync(path.join(root, 'tests'))
    .filter(file => /^test_.*\.cjs$/.test(file) || file === 'folders_filters_test.mjs').sort();
for (const file of tests) {
    const result = spawnSync(process.execPath, [path.join(root, 'tests', file)], {cwd: root, stdio: 'inherit'});
    if (result.status !== 0) process.exit(result.status || 1);
}
console.log(`${tests.length} JS test suites passed`);
