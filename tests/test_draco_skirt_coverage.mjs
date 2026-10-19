import assert from 'node:assert/strict';
import {BodyActor} from '../web_tool/mao-5070/draco/motion.mjs';
import {DesktopSpace,FloorFeet,locomotionFrame} from '../web_tool/mao-5070/draco/desktop-space.mjs';
import {ROOM} from '../web_tool/mao-5070/draco/desktop-room.mjs';
import {createMeshFixture} from './helpers/draco_mesh_fixture.mjs';
import {skirtCoverageProbe} from './helpers/draco_skirt_coverage.mjs';
const report={};
for(const command of ['left','right','walk','spin']){
  const asset=createMeshFixture();let skirt,skin;asset.traverse(m=>{if(m.material?.name==='V10_Skirt_Gradient_And_AO_Paint')skirt=m;if(m.material?.name==='V16_Original_Leg_Texture_Local_Edge_Repair')skin=m;});
  const sourcePositions=skirt.geometry.attributes.position.array.slice(),skinPositions=skin.geometry.attributes.position.array.slice();
  const actor=new BodyActor(asset),space=new DesktopSpace({bounds:ROOM.walk,roam:'room',speed:.32}),feet=new FloorFeet(actor.feet),probe=skirtCoverageProbe(actor);
  for(let i=0;i<180;i++)actor.update(1/120);space.perform(command);
  let maxOutside=0,worst;
  for(let i=0;i<60*(command==='walk'?18:9);i++){
    space.update(1/60);actor.setLocomotion(locomotionFrame(space,feet,1/60));actor.update(1/60);
    if(i%12===0){const result=probe();if(result.maxOutside>maxOutside){maxOutside=result.maxOutside;worst={frame:i,phase:space.phase,...result};}for(const target of actor.skirtClearance.targets)assert.ok(target.delta.array.every(Number.isFinite),'cloth correction diverged');}
  }
  report[command]={maxOutside,worst};
  assert.deepEqual(skirt.geometry.attributes.position.array,sourcePositions,'source pleats were destructively reshaped');
  assert.deepEqual(skin.geometry.attributes.position.array,skinPositions,'leg geometry was hidden or altered');assert.ok(skin.visible);
}
console.log(JSON.stringify(report));
for(const [command,result] of Object.entries(report))assert.ok(result.maxOutside<.001,`${command}: upper thigh pierces the rendered skirt: ${JSON.stringify(result)}`);

// Negative control: ignoring skin below the real hem must not excuse a thigh
// actually piercing through the protected upper part of the garment.
{
  const actor=new BodyActor(createMeshFixture());for(let i=0;i<180;i++)actor.update(1/120);
  const target=actor.skirtClearance.targets[0],position=target.mesh.geometry.attributes.position;
  for(let i=0;i<position.count;i++)target.delta.setXYZ(i,-position.getX(i)*.65,0,-position.getZ(i)*.65);
  target.delta.needsUpdate=true;
  assert.ok(skirtCoverageProbe(actor)().maxOutside>.01,'coverage probe missed a deliberately shrunken skirt');
}
