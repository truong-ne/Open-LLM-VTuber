#!/usr/bin/env node
// Local server for the dance editor (web_tool/mao-5070/draco/dance-editor.html).
// Serves web_tool/, streams a reference video, and saves edited dances into the
// project after validating them. Only listens on 127.0.0.1; loads no AI models.
//
//   node scripts/serve_dance_editor.mjs [--port 12394] [--video path/to/reference.mp4]
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const WEB=path.join(ROOT,'web_tool');
const DANCES=path.join(WEB,'mao-5070','draco','dances');
const BACKUPS=path.join(ROOT,'private','dance-backups');
const TYPES={'.html':'text/html; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8',
  '.json':'application/json','.png':'image/png','.jpg':'image/jpeg','.glb':'model/gltf-binary','.wav':'audio/wav','.ogg':'audio/ogg','.txt':'text/plain; charset=utf-8',
  '.md':'text/plain; charset=utf-8','.mp4':'video/mp4','.webm':'video/webm'};
const MAX_BODY=8*1024*1024;

export function parseArgs(argv){
  const value=name=>{const i=argv.indexOf('--'+name);return i>=0?argv[i+1]:undefined;};
  return {port:Number(value('port')||12394),video:value('video')?path.resolve(value('video')):null};
}

// A saved dance must be a module whose default export passes validateDance and whose
// id matches the file it replaces.
export async function checkDance(source,id){
  if(!/^[a-z0-9-]{1,64}$/.test(id))throw new Error('Tên vũ đạo không hợp lệ');
  const {validateDance}=await import(pathToFileURL(path.join(WEB,'mao-5070','draco','dance-body.mjs')).href);
  const temp=path.join(os.tmpdir(),`dance-check-${process.pid}-${Date.now()}.mjs`);
  fs.writeFileSync(temp,source);
  try{
    const module=await import(pathToFileURL(temp).href);
    const def=validateDance(module.default);
    if(def.id!==id)throw new Error(`id trong file (${def.id}) khác tên lưu (${id})`);
    return def;
  }finally{fs.rmSync(temp,{force:true});}
}

export async function saveDance(source,id,{dances=DANCES,backups=BACKUPS,now=new Date()}={}){
  await checkDance(source,id);
  const target=path.join(dances,`${id}.mjs`);
  let backup=null;
  if(fs.existsSync(target)){
    fs.mkdirSync(backups,{recursive:true});
    backup=path.join(backups,`${id}-${now.toISOString().replace(/[:.]/g,'-')}.mjs`);
    fs.copyFileSync(target,backup);
  }
  fs.mkdirSync(dances,{recursive:true});
  fs.writeFileSync(target,source);
  return {target,backup};
}

function sendFile(req,res,file,type){
  const size=fs.statSync(file).size,range=/bytes=(\d*)-(\d*)/.exec(req.headers.range||'');
  // Video seeking needs byte ranges.
  if(range){
    const start=range[1]?Number(range[1]):0,end=range[2]?Math.min(Number(range[2]),size-1):size-1;
    if(start>=size||start>end){res.writeHead(416,{'Content-Range':`bytes */${size}`}).end();return;}
    res.writeHead(206,{'Content-Type':type,'Content-Range':`bytes ${start}-${end}/${size}`,'Accept-Ranges':'bytes','Content-Length':end-start+1,'Cache-Control':'no-store'});
    fs.createReadStream(file,{start,end}).pipe(res);return;
  }
  res.writeHead(200,{'Content-Type':type,'Content-Length':size,'Accept-Ranges':'bytes','Cache-Control':'no-store'});
  fs.createReadStream(file).pipe(res);
}

export function createServer({port,video}){
  const allowedOrigins=new Set([`http://127.0.0.1:${port}`,`http://localhost:${port}`]);
  return http.createServer((req,res)=>{
    const url=new URL(req.url,`http://127.0.0.1:${port}`);
    const json=(status,body)=>res.writeHead(status,{'Content-Type':'application/json; charset=utf-8'}).end(JSON.stringify(body));
    if(url.pathname==='/api/dance'){
      if(req.method!=='POST')return json(405,{error:'POST only'});
      // Only the editor page itself may write files, never another site in the browser.
      if(!allowedOrigins.has(req.headers.origin||''))return json(403,{error:'Chỉ trang chỉnh vũ đạo trên máy này được lưu'});
      const id=url.searchParams.get('id')||'',chunks=[];let size=0;
      req.on('data',c=>{size+=c.length;if(size<=MAX_BODY)chunks.push(c);});
      req.on('end',async()=>{
        if(size>MAX_BODY)return json(413,{error:'File quá lớn'});
        try{const {target,backup}=await saveDance(Buffer.concat(chunks).toString('utf8'),id);json(200,{ok:true,file:path.relative(ROOT,target),backup:backup&&path.relative(ROOT,backup)});}
        catch(error){json(400,{error:String(error.message||error)});}
      });
      return;
    }
    if(url.pathname==='/reference-video'){
      if(!video||!fs.existsSync(video))return json(404,{error:'Chưa chỉ định clip gốc (--video)'});
      return sendFile(req,res,video,TYPES[path.extname(video).toLowerCase()]||'video/mp4');
    }
    if(req.method!=='GET'&&req.method!=='HEAD')return json(405,{error:'GET only'});
    let file=path.join(WEB,decodeURIComponent(url.pathname));
    if(!file.startsWith(WEB))return json(403,{error:'forbidden'});
    if(fs.existsSync(file)&&fs.statSync(file).isDirectory())file=path.join(file,'index.html');
    if(!fs.existsSync(file))return json(404,{error:'not found'});
    sendFile(req,res,file,TYPES[path.extname(file).toLowerCase()]||'application/octet-stream');
  });
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  const options=parseArgs(process.argv.slice(2));
  createServer(options).listen(options.port,'127.0.0.1',()=>{
    console.log(`Dance editor: http://127.0.0.1:${options.port}/mao-5070/draco/dance-editor.html`);
    if(options.video)console.log(`Reference video: ${options.video}`);
  });
}
