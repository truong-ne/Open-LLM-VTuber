import test from 'node:test';
import assert from 'node:assert/strict';
import {anglesToVector,changedFrames,danceModuleText,editArm,editValue,falloff,neighbourhood,readArm,vectorToAngles} from '../web_tool/mao-5070/draco/dance-edit.mjs';
import {sampleDance,validateDance} from '../web_tool/mao-5070/draco/dance-body.mjs';

const ARMS=['R','L'].flatMap(side=>['u','f'].flatMap(part=>['X','Y','Z'].map(axis=>side+part+axis)));
const columns=[...ARMS,'roll','hip'];
const down=[0,-1,0];
const rows=Array.from({length:40},(_,i)=>[...down,...down,...down,...down,i/4,0]);
const near=(a,b,t=1e-3)=>assert.ok(a.every((v,i)=>Math.abs(v-b[i])<t),`${a.map(v=>v.toFixed(3))} ≠ ${b}`);
const angle=(a,b)=>Math.acos(Math.max(-1,Math.min(1,a[0]*b[0]+a[1]*b[1]+a[2]*b[2])))*180/Math.PI;

test('arm angles read the way a person describes an arm',()=>{
  near(anglesToVector('L',90,0),[1,0,0]);near(anglesToVector('R',90,0),[-1,0,0]);
  near(anglesToVector('L',180,0),[0,1,0]);near(anglesToVector('R',0,0),[0,-1,0]);
  near(anglesToVector('L',0,90),[0,0,1]);
  for(const side of ['L','R'])for(const [a,f] of [[30,10],[120,-20],[200,40],[300,5]]){
    const back=vectorToAngles(side,anglesToVector(side,a,f));
    assert.ok(Math.abs(back.angle-a)<1e-6&&Math.abs(back.forward-f)<1e-6,`${side} ${a},${f}`);
  }
});

test('falloff is full at the edit and fades to nothing at the radius',()=>{
  assert.equal(falloff(0,6),1);assert.equal(falloff(7,6),0);
  assert.ok(falloff(3,6)>0&&falloff(3,6)<1&&falloff(2,6)>falloff(3,6));
  const around=neighbourhood(0,3,40,true).map(n=>n.index).sort((a,b)=>a-b);
  assert.deepEqual(around,[0,1,2,3,37,38,39],'a loop wraps around the ends');
  assert.deepEqual(neighbourhood(0,3,40,false).map(n=>n.index).sort((a,b)=>a-b),[0,1,2,3]);
});

test('editing an arm hits the target and eases the neighbours',()=>{
  const target=anglesToVector('L',150,20);
  const edited=editArm(rows,columns,'Lu',20,target,{radius:5});
  near(readArm(edited,columns,'Lu',20),target);
  near(readArm(edited,columns,'Lu',26),down,1e-9);                     // outside the radius
  const mid=angle(readArm(edited,columns,'Lu',23),down);
  assert.ok(mid>5&&mid<angle(target,down)-5,'a neighbour moves part of the way');
  near(readArm(edited,columns,'Ru',20),down,1e-9);                     // other segments untouched
  near(readArm(rows,columns,'Lu',20),down,1e-9);                       // the input is not changed
  assert.deepEqual(changedFrames(rows,edited),[15,16,17,18,19,20,21,22,23,24,25]);
});

test('editing a number eases the change and respects the format limits',()=>{
  const edited=editValue(rows,columns,'roll',10,20,{radius:4});
  assert.equal(edited[10][12],20);
  assert.ok(edited[12][12]>rows[12][12]&&edited[12][12]<rows[12][12]+(20-rows[10][12]));
  assert.equal(edited[15][12],rows[15][12]);
  const clamped=editValue(rows,columns,'hip',10,5,{radius:0});
  assert.equal(clamped[10][13],.3,'hip is capped at the dance limit');
});

test('an edited dance saves as a valid module that keeps the edit',async()=>{
  const def={id:'edit-test',label:'Thử chỉnh',bpm:120,fps:10,loop:true,overlay:{bounce:0,sway:0},reference:{offset:3.5,crop:[115,415,150,213]},columns,frames:rows};
  const edited=editArm(rows,columns,'Rf',5,anglesToVector('R',90,0),{radius:2});
  const source=danceModuleText(def,edited,'// edited\n');
  const module=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  const saved=validateDance(module.default);
  assert.equal(saved.label,'Thử chỉnh');assert.deepEqual(saved.reference,def.reference);
  near(sampleDance(saved,.5).arms.R.fore,[-1,0,0],1e-3);
});
