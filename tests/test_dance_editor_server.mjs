import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {checkDance,createServer,saveDance} from '../scripts/serve_dance_editor.mjs';
import {danceModuleText} from '../web_tool/mao-5070/draco/dance-edit.mjs';

const ARMS=['R','L'].flatMap(side=>['u','f'].flatMap(part=>['X','Y','Z'].map(axis=>side+part+axis)));
const def={id:'server-test',label:'Thử',bpm:120,fps:10,loop:true,columns:ARMS,frames:[Array(4).fill([0,-1,0]).flat(),Array(4).fill([0,-1,0]).flat()]};
const good=danceModuleText(def,def.frames);

test('only a valid dance whose id matches its file name can be saved',async()=>{
  assert.equal((await checkDance(good,'server-test')).id,'server-test');
  await assert.rejects(checkDance(good,'other-name'),/khác tên/);
  await assert.rejects(checkDance(good,'../escape'),/không hợp lệ/);
  await assert.rejects(checkDance(good.replace('"RuX"','"toes"'),'server-test'),/columns/);
  await assert.rejects(checkDance('export default 1;','server-test'),/Invalid dance/);
});

test('saving replaces the dance and keeps a backup of the old file',async()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'dance-save-'));
  const dances=path.join(dir,'dances'),backups=path.join(dir,'backups');fs.mkdirSync(dances);
  fs.writeFileSync(path.join(dances,'server-test.mjs'),'// old\n'+good);
  const result=await saveDance(good,'server-test',{dances,backups,now:new Date('2026-10-20T10:00:00Z')});
  assert.equal(fs.readFileSync(result.target,'utf8'),good);
  assert.ok(fs.readFileSync(result.backup,'utf8').startsWith('// old'));
  const first=await saveDance(good,'server-test',{dances:path.join(dir,'empty'),backups});
  assert.equal(first.backup,null,'a new file needs no backup');
  fs.rmSync(dir,{recursive:true,force:true});
});

test('the server refuses writes from other sites and streams the reference video in ranges',async()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'dance-video-'));
  const video=path.join(dir,'clip.mp4');fs.writeFileSync(video,Buffer.from([...Array(100).keys()]));
  const server=createServer({port:0,video});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const port=server.address().port,base=`http://127.0.0.1:${port}`;
  try{
    const foreign=await fetch(`${base}/api/dance?id=server-test`,{method:'POST',headers:{Origin:'https://example.com'},body:good});
    assert.equal(foreign.status,403);
    const noOrigin=await fetch(`${base}/api/dance?id=server-test`,{method:'POST',body:good});
    assert.equal(noOrigin.status,403,'a request without an Origin is not trusted either');
    const part=await fetch(`${base}/reference-video`,{headers:{Range:'bytes=10-19'}});
    assert.equal(part.status,206);
    assert.deepEqual([...new Uint8Array(await part.arrayBuffer())],[10,11,12,13,14,15,16,17,18,19]);
    assert.equal((await fetch(`${base}/../package.json`)).status===200,false,'nothing outside web_tool is served');
    assert.equal((await fetch(`${base}/mao-5070/draco/dance-editor.html`)).status,200);
  }finally{server.close();fs.rmSync(dir,{recursive:true,force:true});}
});
