import fs from 'node:fs';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {BodyActor,ACTIONS} from '../web_tool/mao-5070/draco/motion.mjs';
import {ACTION_META} from '../web_tool/mao-5070/draco/actions.mjs';
import {createDracoRig} from '../tests/helpers/draco_fixture.mjs';

const report={};
for(const action of ACTIONS){
  const a=new BodyActor(createDracoRig());for(let f=0;f<180;f++)a.update(1/120);
  a.play(action);for(let f=0;f<Math.round((ACTION_META[action].at||2.4)*120);f++)a.update(1/120);
  report[action]={};
  for(const side of ['L','R']){
    const p=n=>a.asset.getObjectByName(n).getWorldPosition(new T.Vector3());
    const wrist=p(`draco_wrist${side}`),forearm=wrist.clone().sub(p(`draco_elbow${side}`)).normalize();
    const along=p(`draco_finger${side}2_0`).sub(wrist).normalize();
    const normal=a.palms[side].normal.clone().applyQuaternion(a.joints['wrist'+side].getWorldQuaternion(new T.Quaternion()).multiply(a.rest.get(a.joints['wrist'+side]).worldInverse));
    const thumb=p(`draco_finger${side}0_0`).sub(wrist);
    report[action][side]={wristBend:T.MathUtils.radToDeg(Math.acos(T.MathUtils.clamp(forearm.dot(along),-1,1))),normal:normal.toArray(),along:along.toArray(),thumb:thumb.toArray()};
  }
}
fs.writeFileSync(process.argv[2]||'private/draco-hand-inspection.json',JSON.stringify(report,null,2));
console.log(JSON.stringify(Object.fromEntries(Object.entries(report).map(([a,s])=>[a,{L:s.L.wristBend,R:s.R.wristBend}]))));
