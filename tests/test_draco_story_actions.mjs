import assert from 'node:assert/strict';
import {ACTIONS,ACTION_META,STORY_ACTIONS,SAMPLE_STORY,planStory,storyAction} from '../web_tool/mao-5070/draco/actions.mjs';

assert.equal(ACTIONS.length,17);assert.equal(STORY_ACTIONS.length,10);
assert.equal(new Set(ACTIONS).size,ACTIONS.length);
for(const action of ACTIONS)assert.ok(ACTION_META[action].label);
const cases=[
  ['Mao bật cười khi nghe chuyện đó.','laugh'],
  ['Hihi, vui thật đấy.','chuckle'],
  ['Bỗng cô bé giật mình!','surprise'],
  ['Mình đang nghĩ xem tại sao lại thế.','think'],
  ['Ôi ngại quá đi mất.','shy'],
  ['Cô bé thấy buồn và cô đơn.','sad'],
  ['Mình không biết phải làm sao.','shrug'],
  ['Điều cần nhớ là luôn tử tế nhé.','emphasize'],
  ['Đừng buồn nhé, không sao đâu.','reassure'],
  ['Hoan hô, làm được rồi!','celebrate'],
  ['Mao không cười nổi nữa.','sad'],
  ['[think] Mao bật cười nhưng đang cố hiểu câu đố.','think'],
  ['Một ngày bình thường ở nhà.','talk']
];
for(const [text,expected] of cases)assert.equal(storyAction(text),expected,text);
const beats=planStory(SAMPLE_STORY);assert.equal(beats.length,8);
assert.equal(beats[0].action,'think');assert.equal(beats[5].action,'laugh');
assert.ok(beats.every(b=>ACTIONS.includes(b.action)&&!b.text.startsWith('[')&&b.seconds>=7));
assert.deepEqual(planStory('\n   \r\n'),[]);
assert.equal(planStory('a\n'.repeat(100)).length,40);
assert.equal(planStory('a'.repeat(2000))[0].text.length,600);
assert.equal(planStory('<img onerror=alert(1)>')[0].text,'<img onerror=alert(1)>');
console.log('Story actions: 13 context cases, explicit tags, eight-beat sample and input bounds passed.');
