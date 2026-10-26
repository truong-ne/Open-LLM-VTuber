import test from 'node:test';
import assert from 'node:assert/strict';
import {replyComments,createReplyPopup} from '../web_tool/mao-5070/draco/reply-popup.mjs';

const input=(id='one')=>({type:'user-input-transcription',source:'youtube-live',batch_id:id,text:'Reply instructions\n'+JSON.stringify({comment_groups:[{comment:'Chào Mao!',nicknames:['Lan']}]})});
function setup(){const timers=new Map(),changes=[];let id=0;const popup=createReplyPopup({onChange:(rows,visible)=>changes.push({rows,visible}),setTimer:(fn,delay)=>{timers.set(++id,{fn,delay});return id;},clearTimer:id=>timers.delete(id)});return {popup,timers,changes};}
test('queued comments stay hidden until actual playback, then hide after reply end',()=>{
  const {popup,timers,changes}=setup();
  popup.input(input());assert.equal(changes.at(-1).visible,false);
  popup.playing();assert.equal(changes.at(-1).visible,true);assert.equal(changes.at(-1).rows[0].nickname,'Lan');
  popup.end();assert.equal(changes.at(-1).visible,true);
  const hide=[...timers.values()].find(t=>t.delay===1200);assert.ok(hide);
  popup.playing();assert.equal(changes.at(-1).visible,true);
  hide.fn();assert.equal(changes.at(-1).visible,false);
  popup.playing();assert.equal(changes.at(-1).visible,false);
});
test('host and game scripts never open viewer popups; a new turn cancels old hide timers',()=>{
  const {popup,timers,changes}=setup();popup.input(input());popup.playing();popup.end();
  popup.input({...input('two'),source:'mao-idle-host'});popup.playing();assert.equal(changes.at(-1).visible,false);assert.equal(timers.size,0);
  popup.input({...input('three'),source:'vua-tieng-viet'});popup.playing();assert.equal(changes.at(-1).visible,false);
  popup.input(input('four'));popup.playing();assert.equal(changes.at(-1).visible,true);
  const count=changes.length;popup.input(input('four'));assert.equal(changes.length,count);
  popup.reset();assert.equal(changes.at(-1).visible,false);assert.equal(timers.size,0);
});
test('parser keeps viewer text literal, bounds groups, and rejects unrelated events',()=>{
  assert.deepEqual(replyComments({type:'live-comment',text:'Incoming only'}),[]);
  assert.deepEqual(replyComments({...input(),text:'not a batch'}),[]);
  const groups=Array.from({length:8},()=>({comment:'<img onerror=bad>',nicknames:['<script>']}));
  const rows=replyComments({...input(),text:'Instructions\n'+JSON.stringify({comment_groups:groups})});
  assert.equal(rows.length,3);assert.equal(rows[0].text,'<img onerror=bad>');assert.equal(rows[0].nickname,'<script>');
});
