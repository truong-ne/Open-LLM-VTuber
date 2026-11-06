import assert from 'node:assert/strict';
import {selectPerformance,performanceCommand,faceForAction,planPerformanceStory,lookFor} from '../web_tool/mao-5070/draco/performance-context.mjs';
import {createNativeBridge} from '../web_tool/mao-5070/draco/native-bridge.mjs';
const pick=({action,face})=>({action,face});
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
])assert.deepEqual(pick(selectPerformance(text)),{action,face},text);
assert.deepEqual(pick(selectPerformance('Một câu bình thường.',[3])),{action:'talk',face:'smile'});
assert.equal(selectPerformance('Mao giật mình!',[3]).face,'surprised','content must beat ambiguous legacy expression index');
assert.equal(faceForAction('tongue'),'neutral');
for(const [motion,action,face] of [['refuse','refuse','flat'],['squint','chuckle','squint'],['flat','shrug','flat'],['surprised','surprise','surprised']]){
  assert.deepEqual(pick(selectPerformance('Một đoạn kể chuyện.',[],[motion])),{action,face});
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

assert.equal(selectPerformance("Á, sợ quá! Kaito lại chọc Mao rồi!").action,"surprise");

// Mao picks the gesture that fits what she is saying.
for(const [text,action,extra={}] of [
  ['Mao chỉ biết lắc hông thôi, mọi người xem nè!','hipSway',{mood:'happy'}],
  ['Nhảy hả? Mao nhảy thử cho xem nhé!','hipSway'],
  ['Hông chịu đâu, Mao không hát bài đó đâu!','refuse',{face:'flat',mood:'annoyed'}],
  ['Còn lâu Mao mới làm!','refuse'],
  ['Không đâu nha, Mao mệt rồi.','refuse'],
  ['Không sao đâu, Mao ổn mà.','reassure'],
  ['Mao không biết đâu nè.','shrug'],
  ['Á! Sau lưng Mao có gì hả?','surprise',{look:'behind'}],
  ['Bên trái hả? Đâu, Mao nhìn rồi mà.','talk',{look:'left'}],
  ['Ơ, bên phải có ai vậy?','talk',{look:'right'}],
  ['Tiếng gì vậy ta?','turn',{look:'around'}],
  ['Đúng rồi, Mao cũng nghĩ thế.','nod'],
  ['Hehe, Mao giỏi chưa!','talk',{mood:'smug'}],
  ['Buồn ngủ quá đi mất...','talk',{mood:'sleepy'}],
  ['Tạm biệt mọi người nha!','greet']
]){
  const got=selectPerformance(text);assert.equal(got.action,action,text);
  for(const [key,value] of Object.entries(extra))assert.equal(got[key],value,`${text}: ${key}`);
}
// Feedback, negation and look-alike words do not trigger gestures or looks.
for(const text of ['Bạn bảo Mao đừng lắc hông nữa, Mao nhớ rồi.','Đừng nhảy nữa nhé.','Mà thôi, kể tiếp nha.','Đã đến lúc học bài rồi.','Thời gian trôi nhanh ghê.','Ai đó vừa tặng quà cho Mao.']){
  const got=selectPerformance(text);
  assert.ok(!['hipSway','surprise','nod','refuse'].includes(got.action),`${text} -> ${got.action}`);assert.equal(got.look,null,text);
}
assert.equal(lookFor('Phía sau Mao hả?'),'behind');assert.equal(lookFor('Mao ở đây nè'),null);
const story=planPerformanceStory('Á! Sau lưng Mao có gì hả?\nHông chịu đâu!');assert.deepEqual(story.map(b=>[b.action,b.look]),[['surprise','behind'],['refuse',null]]);
console.log('Performance: speech-fitting gestures, refusals, dance offer, looks and moods passed.');
