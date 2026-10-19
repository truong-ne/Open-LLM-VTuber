import assert from 'node:assert/strict';
import {selectPerformance,performanceCommand,faceForAction,planPerformanceStory} from '../web_tool/mao-5070/draco/performance-context.mjs';
import {createNativeBridge} from '../web_tool/mao-5070/draco/native-bridge.mjs';
for(const [text,action,face] of [
  ['Chào Bắp Yêu, cảm ơn bạn đã ghé!','greet','smile'],
  ['Hihi, chuyện này dễ thương thật.','chuckle','squint'],
  ['Mao bật cười khi nghe chuyện đó.','laugh','squint'],
  ['Trời ơi, bất ngờ thật!','surprise','surprised'],
  ['Không chịu đâu, mình muốn kể tiếp cơ.','refuse','flat'],
  ['Mao sẽ lắc hông nhẹ một chút nhé.','hipSway','smile'],
  ['Mao không cười nổi nữa.','sad','flat'],
  ['Đừng buồn nhé, mình vẫn ở đây.','reassure','smile'],
  ['[hipSway] Mình làm thử nhé.','hipSway','smile'],
  ['[refuse] Không đâu nhé.','refuse','flat'],
  ['Bạn bảo lắc hông mạnh quá, mình sẽ chỉnh lại.','talk','neutral']
])assert.deepEqual(selectPerformance(text),{action,face},text);
assert.deepEqual(selectPerformance('Một câu bình thường.',[3]),{action:'talk',face:'smile'});
assert.equal(selectPerformance('Mao giật mình!',[3]).face,'surprised','content must beat ambiguous legacy expression index');
assert.equal(faceForAction('tongue'),'neutral');
for(const [motion,action,face] of [['refuse','refuse','flat'],['squint','chuckle','squint'],['flat','shrug','flat'],['surprised','surprise','surprised']]){
  assert.deepEqual(selectPerformance('Một đoạn kể chuyện.',[],[motion]),{action,face});
}
for(const text of ['Mao lắc hông đi!','Lắc hông nhẹ đi','Mao thử lắc hông nhẹ nhé.'])assert.equal(performanceCommand(text),'hipSway',text);
assert.equal(performanceCommand('Mao làm động tác không chịu đâu đi!'),'refuse');
for(const text of ['Đừng lắc hông nữa','Mao lắc hông mạnh quá!','Mao chưa lắc hông','Sao Mao lắc hông?','Bạn có thể lắc hông không?','không chịu đâu','Mao lè lưỡi đi'])assert.equal(performanceCommand(text),null,text);
const beats=planPerformanceStory('[hipSway] Mình thử nhé.\n[refuse] Không đâu!');
assert.deepEqual(beats.map(b=>b.action),['hipSway','refuse']);assert.ok(beats.every(b=>!b.text.startsWith('[')));
const bridge=createNativeBridge(),seen=[];
assert.equal(bridge.command('Mao lắc hông đi'),true);assert.equal(bridge.pendingAction,'hipSway');
bridge.renderer={performAction:a=>{seen.push(a);return true;},perform:a=>{seen.push(a);return true;}};
assert.equal(bridge.command('Mao làm động tác không chịu đâu đi'),true);
assert.equal(bridge.command('Mao đi sang trái đi'),true);
assert.equal(bridge.command('Mao lắc hông mạnh quá'),false);
assert.deepEqual(seen,['refuse','left']);
console.log('Performance: speech/emotion selection, direct commands, negation, feedback, bridge dispatch and story playback passed.');
