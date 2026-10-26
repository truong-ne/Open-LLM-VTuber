"""Persistent expression state shared by dialogue and study, with input priority.

This describes how the character communicates, not a diagnosis of a viewer or a
biological need. Only finite application events can update it; no raw chat is saved.
"""
import math
import re
import time

MODES={
    'calm':(0.0,0.2), 'curious':(0.2,0.45), 'warm':(0.4,0.35),
    'thoughtful':(0.05,0.25), 'attentive':(0.0,0.15),
}
EVENTS={'audience_input','study_started','source_explained','lesson_saved'}


def cue_from_text(text):
    text=str(text or '')[:3000]
    if re.search(r'buồn|lo lắng|khó chịu|nghiêm túc|đừng đùa|dung dua|serious|sad|worried',text,re.I):
        return 'listen'
    if re.search(r'cảm ơn|cam on|xin chào|hello|thank',text,re.I):
        return 'welcome'
    return 'question' if '?' in text else 'conversation'


def normalize_state(value,now=None):
    now=time.time() if now is None else now
    value=value if isinstance(value,dict) else {}
    mode=value.get('mode','calm')
    if mode not in MODES:mode='calm'
    def number(key,default,low,high):
        n=value.get(key,default)
        return min(high,max(low,float(n))) if type(n) in (int,float) and math.isfinite(n) else default
    updated=number('updated_at',0,0,now)
    if updated and now-updated>1800:mode='calm'
    valence,arousal=MODES[mode]
    return {'mode':mode,'valence':valence,'arousal':arousal,
            'event':value.get('event') if value.get('event') in EVENTS else None,
            'updated_at':updated,'hold_until':number('hold_until',0,0,now+90),
            'revision':int(number('revision',0,0,1_000_000_000))}


def transition(value,event,*,cue='',now=None):
    if event not in EVENTS:raise ValueError('Unsupported expression event')
    now=time.time() if now is None else now
    state=normalize_state(value,now)
    if event!='audience_input' and state['hold_until']>now:
        return state
    if event=='audience_input':
        mode={'listen':'attentive','welcome':'warm','question':'curious'}.get(cue,'attentive')
        hold=now+90
    else:
        mode={'study_started':'thoughtful','source_explained':'curious','lesson_saved':'thoughtful'}[event]
        hold=state['hold_until']
    return {'mode':mode,'valence':MODES[mode][0],'arousal':MODES[mode][1],
            'event':event,'updated_at':now,'hold_until':hold,'revision':state['revision']+1}


def expression_prompt(value):
    mode=normalize_state(value)['mode']
    instruction={
        'calm':'Nói bình tĩnh và tự nhiên.',
        'curious':'Thể hiện sự tò mò vừa phải, tập trung điều đang được nói tới.',
        'warm':'Đáp lại gần gũi và gọn, không tự bịa mức thân thiết.',
        'thoughtful':'Diễn đạt suy ngẫm rõ ràng, phân biệt điều biết và điều chưa rõ.',
        'attentive':'Ưu tiên lắng nghe và trả lời ý chính; giảm đùa, không ép người nói phải vui hay đoán chắc cảm xúc của họ.',
    }[mode]
    return ('\n[Character expression]\n'+instruction+
        '\nKhi nói lời của Mao, có thể dùng [joy], [sadness], [shy], [surprise] '
        'để chọn sắc thái đúng với câu; không cần gắn mọi câu. '
        'VieNeu chỉ có hiệu ứng [cười], [thở dài], [hắng giọng]; '
        'chỉ dùng tối đa một hiệu ứng khi tự nhiên và phù hợp. '
        'Không chèn hiệu ứng vào nội dung trích dẫn hay tóm tắt nguồn. '
        'Không dùng tiếng cười khi người xem đang buồn hoặc với chủ đề mất mát.'
        '\n[/Character expression]\n')
