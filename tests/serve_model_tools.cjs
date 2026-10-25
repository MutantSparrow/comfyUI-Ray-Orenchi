const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
http.createServer((req,res)=>{
    const url=new URL(req.url,'http://localhost');let file;
    if(url.pathname==='/')file=path.join(__dirname,'model_tools_browser.html');
    else if(url.pathname==='/scripts/app.js')file=path.join(__dirname,'analog_fixture.js');
    else if(url.pathname==='/scripts/api.js')file=path.join(__dirname,'model_tools_api_fixture.js');
    else if(url.pathname.startsWith('/extensions/ray/'))file=path.join(root,'web',path.basename(url.pathname));
    else if(url.pathname.startsWith('/tests/'))file=path.join(__dirname,path.basename(url.pathname));
    if(!file||!fs.existsSync(file)){res.writeHead(404);return res.end();}
    res.setHeader('Content-Type',file.endsWith('.html')?'text/html':'text/javascript');res.setHeader('Cache-Control','no-store');res.end(fs.readFileSync(file));
}).listen(8203,'127.0.0.1',()=>console.log('Model Tools harness: http://127.0.0.1:8203'));
