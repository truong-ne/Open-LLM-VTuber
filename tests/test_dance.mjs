import test from 'node:test';
import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {COLUMNS,DanceBodyActor,pushOutOfTorso,sampleDance,torsoDepth,validateDance} from '../web_tool/mao-5070/draco/dance-body.mjs';
import whiteTop from '../web_tool/mao-5070/draco/dances/white-top-dance.mjs';
import {createDracoRig} from './helpers/draco_fixture.mjs';

const def=validateDance(whiteTop);
const cycle=def.frames.length/def.fps;
const ARMS=['R','L'].flatMap(side=>['u','f'].flatMap(part=>['X','Y','Z'].map(axis=>side+part+axis)));
const HANGING=[0,-1,0,0,-1,0,0,-1,0,0,-1,0];
const custom=(extra,...rows)=>validateDance({id:'test-dance',bpm:120,fps:10,loop:false,columns:[...ARMS,...extra],frames:rows});
const settle=(actor,seconds)=>{for(let i=0;i<Math.round(seconds*120);i++)actor.update(1/120);};
const world=(actor,name)=>actor.joints[name].getWorldPosition(new T.Vector3());
const degrees=(a,b)=>T.MathUtils.radToDeg(a.angleTo(b));
const turn=(a,b)=>degrees(new T.Vector3(...a),new T.Vector3(...b));
const torsoDepthAt=point=>pushOutOfTorso(point.clone(),0,false);
const argmax=pick=>{let best=0,bestValue=-Infinity;for(let t=0;t<cycle;t+=.05){const v=pick(sampleDance(def,t));if(v>bestValue){best=t;bestValue=v;}}return best;};

test('choreography data is valid, loops and has no jumps',()=>{
  assert.equal(def.id,'white-top-dance');
  assert.ok(def.frames.length>=300&&cycle>11.5&&cycle<13);
  // No arm segment turns faster than a person could (the fastest throw in the source,
  // a forearm flung up, is about 1,800 deg/s), at the data rate or interpolated at 120 Hz.
  const dataTurn=(r,prefix)=>turn(['X','Y','Z'].map(a=>def.tracks[prefix+a][r]),['X','Y','Z'].map(a=>def.tracks[prefix+a][r-1]));
  for(let r=1;r<def.frames.length;r++)for(const prefix of ['Ru','Rf','Lu','Lf'])assert.ok(dataTurn(r,prefix)<=70,`${prefix} turns ${dataTurn(r,prefix).toFixed(0)}° between rows ${r-1} and ${r}`);
  const speed=t=>{const a=sampleDance(def,t),b=sampleDance(def,t+1/120);return Math.max(...['R','L'].flatMap(s=>[turn(a.arms[s].upper,b.arms[s].upper),turn(a.arms[s].fore,b.arms[s].fore)]))*120;};
  let interior=0;for(let t=0;t<cycle-.5;t+=.01)interior=Math.max(interior,speed(t));
  assert.ok(interior<2600,`fastest arm turn is ${interior.toFixed(0)} deg/s`);
  // The loop seam is no faster than the rest of the dance.
  for(let t=cycle-.3;t<cycle+.3;t+=.01)assert.ok(speed(t)<=interior*1.05,`seam too fast at ${t}`);
  assert.deepEqual(sampleDance(def,cycle+1.3).arms,sampleDance(def,1.3).arms);
});

test('legs and trunk are choreographed as well as the arms',()=>{
  const samples=Array.from({length:Math.round(cycle*20)},(_,i)=>sampleDance(def,i/20));
  const range=pick=>{const values=samples.map(pick);return Math.max(...values)-Math.min(...values);};
  assert.ok(range(s=>s.feet.L.x)>.15&&range(s=>s.feet.R.x)>.15,'the stance widens and narrows');
  assert.ok(Math.max(...samples.map(s=>Math.max(s.feet.L.y,s.feet.R.y)))>.08,'a foot lifts clear of the ground');
  assert.ok(range(s=>s.body.hip)>.1,'the pelvis shifts side to side');
  assert.ok(range(s=>s.body.drop)>.04,'the knees bend and straighten');
  assert.ok(range(s=>s.body.roll)>10,'the trunk leans');
  assert.ok(range(s=>s.arms.R.upper[1])>1&&range(s=>s.arms.L.upper[1])>1,'both arms go from low to high');
});

test('invalid choreography is rejected before it reaches the skeleton',()=>{
  const row=HANGING;
  const bad=patch=>()=>validateDance({id:'test-dance',bpm:120,fps:10,columns:ARMS,frames:[row,row],...patch});
  assert.throws(bad({id:'../escape'}),/id/);
  assert.throws(bad({bpm:0}),/bpm/);
  assert.throws(bad({fps:0}),/fps/);
  assert.throws(bad({columns:ARMS.slice(1),frames:[row.slice(1),row.slice(1)]}),/columns/);
  assert.throws(bad({columns:[...ARMS,'toes'],frames:[[...row,0],[...row,0]]}),/columns/);
  assert.throws(bad({columns:[...ARMS,'RuX'],frames:[[...row,0],[...row,0]]}),/columns/);
  assert.throws(bad({frames:[row]}),/frames/);
  assert.throws(bad({frames:[row,row.slice(1)]}),/length/);
  assert.throws(bad({frames:[row,row.map(()=>Number.NaN)]}),/frame 1/);
  assert.throws(bad({frames:[row,row.map((v,i)=>i===0?9:v)]}),/RuX/);
  assert.throws(bad({frames:[row,row.map((v,i)=>i<3?0:v)]}),/direction/);
  assert.throws(bad({overlay:{bounce:3}}),/overlay/);
  assert.throws(()=>custom(['hip'],[...HANGING,.9],[...HANGING,0]),/hip/);
});

test('arm directions are normalised and optional columns leave the rig alone',()=>{
  const pose=sampleDance(custom([],HANGING.map(v=>v*.5),HANGING.map(v=>v*.5)),0);
  for(const side of ['R','L'])for(const part of ['upper','fore'])assert.ok(Math.abs(Math.hypot(...pose.arms[side][part])-1)<1e-9);
  assert.equal(pose.feet.L.x,null,'no foot column means the rest stance');
  assert.deepEqual(pose.body,{roll:0,yaw:0,turn:0,pitch:0,hip:0,drop:0});
  assert.ok(Object.keys(COLUMNS).every(name=>Array.isArray(COLUMNS[name])));
});

test('dance aims the arms along the sampled directions and keeps the feet on the floor',()=>{
  const actor=new DanceBodyActor(createDracoRig());settle(actor,1.5);
  for(const time of [0,1.2,2.4,3.6,5.1,6.2,7.5,8.9,10.3,11.6]){
    actor.setDance(def,time);settle(actor,1.2);actor.setDance(def,time);settle(actor,.05);
    const pose=sampleDance(def,time);
    assert.ok(actor.danceAmount>.95,'dance blend reaches full strength');
    for(const side of ['L','R']){
      const shoulder=world(actor,'upper'+side),elbow=world(actor,'elbow'+side);
      const measured=elbow.clone().sub(shoulder).normalize();
      const error=degrees(measured,new T.Vector3(...pose.arms[side].upper));
      assert.ok(error<28,`t=${time} ${side} upper arm off by ${error.toFixed(1)}°`);
    }
    assert.ok(actor.audit.footDrift<.03,`t=${time} foot drift ${actor.audit.footDrift}`);
  }
  assert.ok(actor.bones.every(b=>[...b.position.toArray(),...b.quaternion.toArray()].every(Number.isFinite)),'every bone transform stays finite');
});

test('feet stand where the choreography puts them, lift and stay planted in a squat',()=>{
  const actor=new DanceBodyActor(createDracoRig());settle(actor,1.5);
  const rest={L:world(actor,'ankleL'),R:world(actor,'ankleR')};
  const centre=(rest.L.x+rest.R.x)/2,bh=actor.bodyHeight;
  const standAt=time=>{actor.setDance(def,time);settle(actor,1.5);actor.setDance(def,time);settle(actor,.05);return {L:world(actor,'ankleL'),R:world(actor,'ankleR'),pose:sampleDance(def,time)};};
  const wide=standAt(argmax(s=>Math.min(s.feet.L.x,s.feet.R.x)));
  assert.ok(wide.pose.feet.L.x>.1&&wide.pose.feet.R.x>.1);
  assert.ok(Math.abs(wide.L.x-(centre+wide.pose.feet.L.x*bh))<.03*bh+.01,'left foot reaches its goal');
  assert.ok(Math.abs(wide.R.x-(centre-wide.pose.feet.R.x*bh))<.03*bh+.01,'right foot reaches its goal');
  assert.ok(wide.L.x-wide.R.x>rest.L.x-rest.R.x+.03,'stance is wider than at rest');
  const lifted=standAt(argmax(s=>s.feet.L.y));
  assert.ok(lifted.pose.feet.L.y>.06);
  assert.ok(lifted.L.y>rest.L.y+.04,'the lifted foot leaves the floor');
  // The deepest squat with both feet down (the deepest point overall can coincide with a lifted foot).
  const squat=standAt(argmax(s=>s.body.drop-10*(s.feet.L.y+s.feet.R.y)));
  assert.ok(squat.pose.body.drop>.03&&squat.pose.feet.L.y<.02&&squat.pose.feet.R.y<.02);
  const planted=side=>squat[side].y-rest[side].y;
  assert.ok(planted('L')<.06&&planted('R')<.06,'both feet stay planted in the squat');
});

test('knees bend and hips lower when the dance asks for it',()=>{
  const actor=new DanceBodyActor(createDracoRig());settle(actor,1.5);
  const hips=()=>world(actor,'pelvis').y;
  const high=argmax(s=>-s.body.drop),low=argmax(s=>s.body.drop);
  actor.setDance(def,high);settle(actor,1.5);const upright=hips();
  actor.setDance(def,low);settle(actor,1.5);const squatting=hips();
  assert.ok(upright-squatting>.03*actor.bodyHeight,`the squat is lower than the upright pose (${(upright-squatting).toFixed(4)})`);
});

test('the trunk leans toward the dancer’s left for a positive roll',()=>{
  const lean=roll=>{
    const actor=new DanceBodyActor(createDracoRig());settle(actor,1.2);
    actor.setDance(custom(['roll'],[...HANGING,roll],[...HANGING,roll]),0);settle(actor,1.5);
    return world(actor,'head').x-world(actor,'pelvis').x;
  };
  assert.ok(lean(15)>lean(0)+.01,'positive roll moves the head toward +x');
  assert.ok(lean(-15)<lean(0)-.01,'negative roll moves it the other way');
});

test('the whole body turns and leans forward while the feet stay planted',()=>{
  const pose=(turn,pitch)=>{
    const actor=new DanceBodyActor(createDracoRig());settle(actor,1.2);
    const feet=[world(actor,'ankleL'),world(actor,'ankleR')];
    actor.setDance(custom(['turn','pitch'],[...HANGING,turn,pitch],[...HANGING,turn,pitch]),0);settle(actor,1.5);
    return {shoulders:world(actor,'upperL').sub(world(actor,'upperR')),lean:world(actor,'head').z-world(actor,'pelvis').z,
      moved:Math.max(world(actor,'ankleL').distanceTo(feet[0]),world(actor,'ankleR').distanceTo(feet[1]))};
  };
  const still=pose(0,0),turned=pose(30,0),leaning=pose(0,15);
  // Turned toward her own left: the left shoulder swings back (away from the audience).
  assert.ok(turned.shoulders.z<still.shoulders.z-.05,'a positive turn faces the dancer’s left');
  assert.ok(leaning.lean>still.lean+.03,'a positive pitch leans the trunk toward the audience');
  for(const p of [turned,leaning])assert.ok(p.moved<.02,'the feet stay where they were');
});

test('the robe flaps and cuffs swing less while dancing and loosen again after',()=>{
  const actor=new DanceBodyActor(createDracoRig());settle(actor,1);
  const of=type=>actor.dynamics.segments.filter(s=>s.type===type);
  const idle={coat:of('coat').map(s=>s.limit),cuff:of('cuff').map(s=>s.limit)};
  for(let n=0;n<4*120;n++){actor.setDance(def,n/120);actor.update(1/120);}
  for(const type of ['coat','cuff'])of(type).forEach((s,i)=>assert.ok(s.limit<idle[type][i]*.8,`${type} swing cone is narrower while dancing`));
  actor.clearDance();settle(actor,3);
  for(const type of ['coat','cuff'])of(type).forEach((s,i)=>assert.ok(Math.abs(s.limit-idle[type][i])<1e-3,`${type} is as loose as before once the dance has faded`));
});

test('a point inside the torso is moved out smoothly, a point clear of it is left alone',()=>{
  const inside=new T.Vector3(.02,1.15,.05),depth=pushOutOfTorso(inside,0);
  assert.ok(depth>.05&&torsoDepthAt(inside)<1e-9,'a deep point ends on the surface');
  const clear=new T.Vector3(.4,1.15,.05);assert.equal(pushOutOfTorso(clear,0),0);assert.equal(clear.x,.4);
  assert.equal(pushOutOfTorso(new T.Vector3(0,1.6,0),0),0,'above the shoulders there is no torso');
  // Approaching the surface from the front, and on into the front half of the torso, the
  // push grows without a jump (at the centre line it has to switch sides; arms never get there).
  let last=null;
  for(let z=.30;z>.08;z-=.002){
    const p=new T.Vector3(0,1.15,z);pushOutOfTorso(p,.02);
    if(last!==null)assert.ok(Math.abs(p.z-last)<.0021,`no jump near z=${z.toFixed(3)}`);
    last=p.z;
  }
});

test('hands, wrists, forearms and elbows stay outside the body for the whole dance',()=>{
  const actor=new DanceBodyActor(createDracoRig());settle(actor,1.5);
  let worst=0,at=0;
  for(let n=0;n<Math.round(cycle*60);n++){
    actor.setDance(def,n/60,def.bpm,{live:true});actor.update(1/120);actor.update(1/120);
    for(const side of ['L','R']){
      const elbow=world(actor,'elbow'+side),wrist=world(actor,'wrist'+side),along=wrist.clone().sub(elbow).normalize();
      for(const point of [elbow,elbow.clone().lerp(wrist,.5),wrist,wrist.clone().addScaledVector(along,.06)]){
        const d=torsoDepth(actor,point);if(d>worst){worst=d;at=n/60;}
      }
    }
  }
  assert.ok(worst<.005,`an arm sinks ${(worst*100).toFixed(1)} cm into the body at ${at.toFixed(2)} s`);
});

test('arms bend at the elbow without spinning the forearm',()=>{
  // The forearm turns about its own axis only as much as the shoulder carries it: no
  // invented twist, which used to read as a stuck, snapping arm.
  const actor=new DanceBodyActor(createDracoRig());settle(actor,1.5);
  let worst=0,last=null;
  for(let n=0;n<6*120;n++){
    actor.setDance(def,n/120,def.bpm,{live:true});actor.update(1/120);
    const elbow=actor.joints.elbowL,q=elbow.getWorldQuaternion(new T.Quaternion());
    const axis=world(actor,'wristL').sub(world(actor,'elbowL')).normalize();
    if(last){
      const d=q.clone().multiply(last.q.clone().invert());if(d.w<0)d.set(-d.x,-d.y,-d.z,-d.w);
      const total=2*Math.acos(Math.min(1,d.w))*180/Math.PI,swing=T.MathUtils.radToDeg(last.axis.angleTo(axis));
      if(n>240)worst=Math.max(worst,(total-swing)*120);
    }
    last={q,axis};
  }
  assert.ok(worst<700,`forearm twist peaks at ${worst.toFixed(0)} deg/s`);
});

test('the hand trails the forearm smoothly and never snaps',()=>{
  const actor=new DanceBodyActor(createDracoRig());settle(actor,1.5);
  let worst=0,last=null;
  for(let n=0;n<10*120;n++){
    actor.setDance(def,n/120,def.bpm,{live:true});actor.update(1/120);
    const q=actor.joints.wristL.getWorldQuaternion(new T.Quaternion());
    if(last&&n>240)worst=Math.max(worst,T.MathUtils.radToDeg(q.angleTo(last))*120);
    last=q;
  }
  assert.ok(worst<2600,`hand turns at most ${worst.toFixed(0)} deg/s`);
});

test('raising an arm lifts the shoulder a little',()=>{
  const shoulderHeight=up=>{
    const actor=new DanceBodyActor(createDracoRig());settle(actor,1.2);
    const arm=up?[1,0,0,1,0,0]:[0,-1,0,0,-1,0];
    actor.setDance(custom([],[...arm,...HANGING.slice(6)],[...arm,...HANGING.slice(6)]),0);settle(actor,1.5);
    return world(actor,'upperR').y;
  };
  // Right arm out sideways-up vs hanging: the shoulder joint ends up higher.
  assert.ok(shoulderHeight(true)>shoulderHeight(false)+.001);
});

test('stopping the dance fades the layer out and returns the idle pose',()=>{
  const actor=new DanceBodyActor(createDracoRig());settle(actor,1.5);
  const idle=world(actor,'wristL'),idleFoot=world(actor,'ankleL');
  actor.setDance(def,argmax(s=>s.arms.L.fore[1]));settle(actor,1.5);
  assert.ok(world(actor,'wristL').distanceTo(idle)>.1);
  actor.clearDance();settle(actor,3);
  assert.equal(actor.danceAmount,0);assert.equal(actor.dancing,false);
  assert.ok(world(actor,'wristL').distanceTo(idle)<.06,'arm returns to the idle pose');
  assert.ok(world(actor,'ankleL').distanceTo(idleFoot)<.02,'feet return to the rest stance');
});

test('song tempo scales the choreography within safe bounds',()=>{
  const actor=new DanceBodyActor(createDracoRig());
  actor.setDance(def,10,def.bpm*3);assert.equal(actor.dance.speed,1.35);
  actor.setDance(def,10,def.bpm/3);assert.equal(actor.dance.speed,.75);
  actor.setDance(def,10,undefined);assert.equal(actor.dance.speed,1);
  actor.setDance(def,Number.NaN,Number.NaN);assert.equal(actor.dance.time,0);assert.equal(actor.dance.speed,1);
});

test('a live clock rides out coarse, stale audio times and still resynchronises',()=>{
  // audio.currentTime is reported in uneven steps: here it only updates every third frame.
  const frame=1/60,run=live=>{
    const actor=new DanceBodyActor(createDracoRig()),clocks=[];
    let reported=0;
    for(let n=0;n<600;n++){
      const truth=n*frame;
      if(n%3===0)reported=truth;
      actor.setDance(def,reported,def.bpm,{live});
      for(let s=0;s<2;s++)actor.step(1/120);
      clocks.push(actor.danceClock);
    }
    const increments=clocks.slice(1).map((c,i)=>c-clocks[i]);
    return {clocks,spread:Math.max(...increments)-Math.min(...increments),error:Math.abs(clocks.at(-1)-599*frame)};
  };
  const exact=run(false),live=run(true);
  assert.ok(live.spread<exact.spread*.5,`live clock advances evenly (${live.spread.toFixed(4)} vs ${exact.spread.toFixed(4)})`);
  assert.ok(live.error<.05,'and stays close to the real time');
  const actor=new DanceBodyActor(createDracoRig());
  actor.setDance(def,1,def.bpm,{live:true});actor.step(1/120);
  actor.setDance(def,5,def.bpm,{live:true});actor.step(1/120);
  assert.ok(Math.abs(actor.danceClock-5)<.01,'a seek resynchronises at once');
});
