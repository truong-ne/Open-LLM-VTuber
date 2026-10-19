import test from 'node:test';
import assert from 'node:assert/strict';
import {CurtainTimeline,CURTAIN_TIMING,curtainEase} from '../web_tool/mao-5070/draco/scene-transition.mjs';
import {curtainVertex} from '../web_tool/mao-5070/draco/curtain-cloth.mjs';
const {close,hold,open}=CURTAIN_TIMING;

test('curtains cover the old scene before switching and reveal only after preparation',()=>{
  const t=new CurtainTimeline();t.request('studio',0);
  assert.equal(t.advance(close-1).scene,'lounge');
  const covered=t.advance(close);assert.equal(covered.commit,true);assert.equal(covered.progress,1);assert.equal(covered.scene,'studio');
  assert.equal(t.advance(close+hold+500,false).phase,'covered');
  const revealStart=close+hold+501;
  assert.equal(t.advance(revealStart,true).phase,'opening');
  assert.equal(t.advance(revealStart+open-1).revealed,false);
  const revealed=t.advance(revealStart+open);assert.equal(revealed.phase,'idle');assert.equal(revealed.progress,0);assert.equal(revealed.revealed,true);
  // Repeated state polling never replays the effect.
  for(let n=0;n<20;n++){t.request('studio',5000+n);assert.equal(t.advance(5000+n).phase,'idle');}
});

test('rapid commands are coalesced while closed and returns use the same curtains',()=>{
  const t=new CurtainTimeline();t.request('studio',0);t.request('concert',200);
  assert.equal(t.advance(close).scene,'concert');
  t.request('lounge',close+50);const updated=t.advance(close+50);assert.equal(updated.commit,true);assert.equal(updated.progress,1);assert.equal(updated.scene,'lounge');
  let now=close+50+hold;t.advance(now);now+=open;t.advance(now);assert.equal(t.phase,'idle');
  now+=100;t.request('studio',now);now+=close;t.advance(now);now+=hold;t.advance(now);
  t.request('concert',now+100);assert.equal(t.advance(now+200).scene,'studio','must not change while the curtain is opening');
  now+=open;t.advance(now);t.request('concert',now+1);assert.equal(t.phase,'closing');
});

test('a fresh round in the same scene does not need a second transition',()=>{
  const t=new CurtainTimeline('studio');t.request('studio',100);
  assert.equal(t.advance(100).phase,'idle');
  t.request('lounge',200);assert.equal(t.advance(200+close).commit,true);
});

test('heavy drape easing has no velocity or acceleration jump at its endpoints',()=>{
  const h=.0001;assert.equal(curtainEase(0),0);assert.equal(curtainEase(1),1);
  assert.ok(curtainEase(h)/h<.00001);assert.ok((1-curtainEase(1-h))/h<.00001);
  let previous=0;for(let i=0;i<=100;i++){const x=curtainEase(i/100);assert.ok(x>=previous&&x<=1);previous=x;}
});

test('cloth closes with central overlap, stays closed edge to edge, and gathers out of view',()=>{
  for(let row=0;row<=16;row++){
    const v=row/16,left=curtainVertex('left',1,v,1),right=curtainVertex('right',0,v,1);
    assert.ok(left.x>=right.x,'there is a hole at the central cut');
    assert.ok(curtainVertex('left',0,v,1).x<-1);assert.ok(curtainVertex('right',1,v,1).x>1);
    for(const u of [0,.5,1]){assert.ok(curtainVertex('left',u,v,0).x<-1);assert.ok(curtainVertex('right',u,v,0).x>1);}
  }
  const top=curtainVertex('left',1,1,.5,'opening'),bottom=curtainVertex('left',1,0,.5,'opening');
  assert.ok(top.x<bottom.x,'the hem should follow the carrier rather than move as a rigid card');
});
