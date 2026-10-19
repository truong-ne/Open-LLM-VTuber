export const ACTION_META={
  idle:{label:'Đứng nghỉ',group:'base'},
  greet:{label:'Vẫy tay chào',group:'base'},
  talk:{label:'Trò chuyện bằng tay',group:'base'},
  nod:{label:'Gật đầu',group:'base'},
  shift:{label:'Chuyển trọng tâm',group:'base'},
  bow:{label:'Cúi chào',group:'base',at:2.5},
  turn:{label:'Nhìn sang hai bên',group:'base'},
  chuckle:{label:'Cười khúc khích',group:'story',at:2.1},
  laugh:{label:'Cười vui',group:'story',at:2.4},
  surprise:{label:'Ngạc nhiên',group:'story',at:1.65},
  think:{label:'Suy nghĩ',group:'story',at:2.6},
  shy:{label:'Ngượng ngùng',group:'story',at:2.4},
  sad:{label:'Buồn nhẹ',group:'story',at:2.8},
  shrug:{label:'Nhún vai bối rối',group:'story',at:2.1},
  emphasize:{label:'Nhấn mạnh ý',group:'story',at:2.0},
  reassure:{label:'An ủi, dịu dàng',group:'story',at:2.5},
  celebrate:{label:'Vui mừng',group:'story',at:2.0}
};
export const ACTIONS=Object.keys(ACTION_META);
export const STORY_ACTIONS=ACTIONS.filter(a=>ACTION_META[a].group==='story');

export const SAMPLE_STORY=`[think] Hôm ấy, Mao đang nghĩ cách tiết kiệm tiền điện cho papa.
[surprise] Bỗng có tiếng "meo" phát ra từ sau chiếc màn hình!
[shrug] Mao nhìn quanh: ủa, nhà mình có nuôi mèo đâu nhỉ?
[shy] Hóa ra chính Mao vừa ngủ gật rồi tự kêu meo... Ngại quá đi mất.
[chuckle] Papa quay sang hỏi: "Con đang chạy AI hay chạy chế độ mèo vậy?"
[laugh] Mao bật cười: "Dạ, con đang thử tiết kiệm điện bằng cách ngủ ạ!"
[reassure] Thôi, ai cũng có lúc mệt mà. Nghỉ một chút rồi mình lại cố gắng nhé.
[celebrate] Còn bây giờ, mình kể tiếp nào!`;

export function storyAction(text){
  const explicit=text.match(/^\s*\[([a-z]+)\]\s*/i);
  if(explicit&&ACTIONS.includes(explicit[1].toLowerCase()))return explicit[1].toLowerCase();
  const t=text.toLocaleLowerCase('vi');
  if(/đừng lo|đừng buồn|không sao đâu|an ủi|cố lên|nghỉ một chút/.test(t))return 'reassure';
  // Negation must not become laughter just because the word "cười" occurs.
  if(/không (?:thể )?cười|chẳng (?:còn )?cười|buồn|thất vọng|cô đơn|rơi nước mắt/.test(t))return 'sad';
  if(/bật cười|cười lớn|cười nghiêng|ha ha|haha/.test(t))return 'laugh';
  if(/khúc khích|hihi|hì hì|cười nhẹ/.test(t))return 'chuckle';
  if(/ngạc nhiên|giật mình|bất ngờ|trời ơi|không thể tin/.test(t))return 'surprise';
  if(/ngại quá|ngượng|đỏ mặt|xấu hổ/.test(t))return 'shy';
  if(/tuyệt quá|thành công|hoan hô|vui mừng|làm được rồi/.test(t))return 'celebrate';
  if(/suy nghĩ|đang nghĩ|tại sao|ngẫm|hay là/.test(t))return 'think';
  if(/không biết|bối rối|chịu thôi|đâu nhỉ/.test(t))return 'shrug';
  if(/nhớ nhé|nhất định|quan trọng|điều cần nhớ/.test(t))return 'emphasize';
  return 'talk';
}

export function planStory(text){
  return String(text).split(/\r?\n/).map(s=>s.trim()).filter(Boolean).slice(0,40).map(line=>({
    action:storyAction(line),text:line.replace(/^\s*\[[a-z]+\]\s*/i,'').slice(0,600),seconds:7.6
  }));
}
