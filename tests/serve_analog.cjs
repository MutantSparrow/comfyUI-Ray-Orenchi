// Dependency-free browser regression harness: node tests/serve_analog.cjs [port]
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
http.createServer((req, res) => {
    const pathname = new URL(req.url, 'http://localhost').pathname;
    let file;
    if (pathname === '/') file = path.join(__dirname, 'analog_browser.html');
    else if (pathname === '/scripts/app.js') file = path.join(__dirname, 'analog_fixture.js');
    else if (pathname.startsWith('/extensions/ray/')) file = path.join(root, 'web', path.basename(pathname));
    else if (pathname.startsWith('/tests/')) file = path.join(__dirname, path.basename(pathname));
    if (!file || !fs.existsSync(file)) { res.writeHead(404); return res.end(); }
    res.setHeader('Content-Type', file.endsWith('.html') ? 'text/html' : 'text/javascript');
    res.setHeader('Cache-Control', 'no-store');
    res.end(fs.readFileSync(file));
}).listen(Number(process.argv[2] || 8199), '127.0.0.1', () => console.log('Analog test harness: http://127.0.0.1:' + (process.argv[2] || 8199)));
