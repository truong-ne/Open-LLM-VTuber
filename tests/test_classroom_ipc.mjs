import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import vm from 'node:vm';
import desktop from '../scripts/draco-desktop-main.cjs';

test('TikTok window fits a portrait 9:16 stage plus the desktop title bar',()=>{
  for(const area of [{x:0,y:0,width:1920,height:1040},{x:-1280,y:0,width:1280,height:720},{x:0,y:0,width:1080,height:1920}]){
    const bounds=desktop.classroomBounds({x:100,y:50,width:900,height:670},area);
    assert.ok(bounds.width<bounds.height);
    assert.ok(Math.abs(bounds.width/(bounds.height-30)-9/16)<.002);
    assert.ok(bounds.x>=area.x&&bounds.x+bounds.width<=area.x+area.width);
    assert.ok(bounds.y>=area.y&&bounds.y+bounds.height<=area.y+area.height);
  }
});

test('desktop IPC keeps the host secret in main, validates options and owns the caller', async()=>{
  const handlers=new Map(),events=new Map(),calls=[],key=Buffer.alloc(32,7),main={exports:{}};
  let bounds={x:100,y:50,width:900,height:670};const aspect=[],assetEvents=[];
  const window={getBounds:()=>({...bounds}),setBounds:value=>{bounds={...value};},isMaximized:()=>false,setAspectRatio:value=>aspect.push(value),webContents:{session:{async clearCache(){assetEvents.push("clearCache");}},setBackgroundThrottling(){},on(){}},once(){},setTitle(){},loadFile(){assetEvents.push("loadFile");}};
  const mockedFs={writeFileSync(){},readFileSync(filename){if(filename.endsWith('mao-ingress.key'))return key;throw Error('Not found');}};
  const source=fs.readFileSync(new URL('../scripts/draco-desktop-main.cjs',import.meta.url),'utf8').replace('__MAO_WORKSPACE__',JSON.stringify('C:/fixture'));
  vm.runInNewContext(source,{__dirname:'C:/fixture',exports:main.exports,require(name){return {'fs':mockedFs,'path':path,'crypto':crypto,'electron':{ipcMain:{removeHandler(){},handle:(name,fn)=>handlers.set(name,fn),on:(name,fn)=>events.set(name,fn)},screen:{getDisplayMatching:()=>({workArea:{x:0,y:0,width:1920,height:1040}})}}}[name];},process:{env:{}},Buffer,Date,JSON,Number,Error,String,setInterval:()=>({unref(){}}),clearInterval(){},AbortSignal,fetch:async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({classroom:{enabled:true}})};}});
  main.exports.loadDraco(window);
  await Promise.resolve();
  assert.deepEqual(assetEvents,["clearCache","loadFile"],"clear stale rig assets before loading the desktop");
  assert.ok(bounds.width<bounds.height,'normal room must open portrait by default');
  const handle=handlers.get('mao-classroom-control'),options={enabled:true,account:'@thanhoathirty6'};
  await assert.rejects(()=>handle({sender:{}},options),/Desktop owner/);
  assert.match((await handle({sender:window.webContents},{...options,account:'bad handle'})).error,/không hợp lệ/);
  const response=await handle({sender:window.webContents},options);
  assert.equal(response.classroom.enabled,true);
  assert.equal(calls.length,1);
  assert.equal(calls[0].options.headers['X-Mao-Control'],crypto.createHmac('sha256',key).update('local-control:v1:local_companion').digest('hex'));
  assert.deepEqual(JSON.parse(calls[0].options.body),options);
  const status=events.get('mao-draco-status');
  status({sender:window.webContents},{model:'draco',mode:'window',classroom:true});
  assert.ok(bounds.width<bounds.height);
  bounds={x:100,y:50,width:900,height:670};
  status({sender:window.webContents},{model:'draco',mode:'window',classroom:true});
  assert.ok(Math.abs(bounds.width/(bounds.height-30)-9/16)<.002,'upstream resize must not leave the classroom landscape');
  status({sender:window.webContents},{model:'draco',mode:'window',classroom:false});
  assert.ok(Math.abs(bounds.width/(bounds.height-30)-9/16)<.002,'returning to the room must preserve portrait size');assert.equal(aspect.at(-1),9/16);
  status({sender:window.webContents},{model:'draco',mode:'pet',classroom:false});assert.equal(aspect.at(-1),0);
  status({sender:window.webContents},{model:'draco',mode:'window',classroom:false});assert.ok(bounds.width<bounds.height);assert.equal(aspect.at(-1),9/16);
});
