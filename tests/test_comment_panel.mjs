import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeCommentFeed} from '../web_tool/mao-5070/draco/comment-panel.mjs';

test('incremental comment display deduplicates, orders newest first, and resets after backend restart',()=>{
  let state={session:'',revision:0,comments:[]};
  state=mergeCommentFeed(state,{session:'a',revision:2,comments:[{id:1,text:'Chào Mao',nickname:'Lan'},{id:2,text:'!vuatiengviet',nickname:'Minh'}]});
  state=mergeCommentFeed(state,{session:'a',revision:3,comments:[{id:2,text:'!vuatiengviet',nickname:'Minh'},{id:3,text:'Mao ơi!'}]});
  assert.deepEqual(state.comments.map(row=>row.id),[3,2,1]);
  assert.equal(mergeCommentFeed(state,{session:'a',revision:1,comments:[]}),state);
  state=mergeCommentFeed(state,{session:'b',revision:1,comments:[{id:1,text:'Mới kết nối'}]});
  assert.equal(state.comments.length,1);assert.equal(state.comments[0].text,'Mới kết nối');
});
test('viewer text stays literal and client storage remains bounded',()=>{
  const comments=Array.from({length:60},(_,i)=>({id:i+1,text:'<img onerror=bad>',nickname:'<script>',platform:'youtube'}));
  const state=mergeCommentFeed({session:'',revision:0,comments:[]},{session:'a',revision:60,comments:[...comments,null,{id:70,text:'future'}]});
  assert.equal(state.comments.length,20);assert.equal(state.comments[0].text,'<img onerror=bad>');assert.equal(state.comments[0].nickname,'<script>');assert.equal(state.comments[0].id,60);
});
