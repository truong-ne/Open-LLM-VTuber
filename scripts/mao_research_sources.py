"""Rotating learning tracks and a persistent frontier of unread public articles."""
import hashlib
import re
import time
from urllib.parse import urlsplit, urlunsplit, urljoin

TRACKS = (
    dict(key='first_viewers', label='kiếm những người xem đầu tiên cho AI VTuber mới',
         query='new VTuber zero viewers first audience grow channel practical tips',
         sources=[
             'https://streamlabs.com/content-hub/post/zero-viewers-try-these-tips',
             'https://restream.io/blog/streaming-tips-for-everyone-from-beginners-to-pros/',
             'https://streamlabs.com/content-hub/post/how-to-build-community-VTuber']),
    dict(key='waifu', label='tính cách waifu dễ mến nhưng có nét riêng cho Mao',
         query='VTuber waifu character personality warm playful teasing original persona',
         sources=[
             'https://hololive.hololivepro.com/en/talents/ayunda-risu/',
             'https://hololive.hololivepro.com/en/talents/pavolia-reine/',
             'https://hololive.hololivepro.com/en/talents/mori-calliope/',
             'https://hololive.hololivepro.com/en/talents/gigi-murin/',
             'https://hololive.hololivepro.com/en/talents/natsuiro-matsuri/']),
    dict(key='discovery', label='Shorts, tiêu đề và thumbnail để người mới tìm thấy Mao',
         query='YouTube new channel discoverability livestream Shorts titles thumbnails',
         sources=[
             'https://support.google.com/youtube/answer/9314486?hl=en',
             'https://support.google.com/youtube/answer/72431?hl=en',
             'https://support.google.com/youtube/answer/10343433?hl=en',
             'https://support.google.com/youtube/answer/16391400?hl=en',
             'https://restream.io/blog/repurpose-with-restream/']),
    dict(key='conversation', label='ứng biến, hài hước và trả lời bình luận tự nhiên',
         query='VTuber chat conversation improv humor audience interaction beginner',
         sources=[
             'https://support.google.com/youtube/answer/11913117?hl=en',
             'https://support.google.com/youtube/answer/15268877?hl=en',
             'https://hololive.hololivepro.com/en/talents/shirakami-fubuki/']),
    dict(key='formats', label='nội dung và khoảnh khắc đáng xem khi kênh còn nhỏ',
         query='small VTuber stream content ideas recurring segments clips new audience',
         sources=[
             'https://support.google.com/youtube/answer/12917058?hl=en',
             'https://restream.io/blog/repurpose-with-restream/',
             'https://restream.io/blog/streaming-tips-for-everyone-from-beginners-to-pros/']),
    dict(key='identity', label='bản sắc, sở thích và nét đáng nhớ riêng của Mao',
         query='VTuber character branding consistent personality original character design',
         sources=[
             'https://blog.twitch.tv/en/2022/08/11/custom-tags-discovery-on-your-terms/',
             'https://hololive.hololivepro.com/en/talents/',
             'https://hololive.hololivepro.com/en/talents/shiranui-flare/']),
    dict(key='retention', label='giữ chân người mới và kiểm tra điều gì thật sự hiệu quả',
         query='YouTube live audience retention first minute new viewers analytics tips',
         sources=[
             'https://support.google.com/youtube/answer/9314415?hl=en',
             'https://support.google.com/youtube/answer/9314355?hl=en',
             'https://support.google.com/youtube/answer/9314486?hl=en']),
    dict(key='emotions', label='nhận biết cảm xúc, đồng cảm và biểu đạt phù hợp khi trò chuyện',
         query='emotional awareness empathy active listening feelings expressive communication',
         sources=[
             'https://greatergood.berkeley.edu/topic/empathy/definition',
             'https://greatergood.berkeley.edu/topic/compassion/definition',
             'https://greatergood.berkeley.edu/article/item/three_steps_to_understanding_your_partners_emotions']),
)
ORIGINS = {
    'arxiv.org': ('/abs/', '/html/'),
    'support.google.com': ('/youtube/answer/',),
    'www.youtube.com': ('/creators/',),
    'streamlabs.com': ('/content-hub/post/',),
    'restream.io': ('/blog/', '/learn/'),
    'blog.twitch.tv': ('/en/',),
    'www.twitch.tv': ('/creatorcamp/',),
    'hololive.hololivepro.com': ('/en/talents/', '/en/talents'),
    'greatergood.berkeley.edu': ('/topic/', '/article/item/'),
    'ggia.berkeley.edu': ('/practice/', '/bridging/practices/'),
}
PERSONAL_TRACKS=(
    dict(key='emotional_nuance',label='gọi tên và phân biệt những sắc thái cảm xúc của bản thân',
         query='emotional granularity naming emotions self awareness feelings',
         sources=['https://ggia.berkeley.edu/practice/naming_your_emotions']),
    dict(key='self_compassion',label='đối xử tử tế với bản thân khi sai, hụt hẫng hoặc chưa hiểu điều gì',
         query='self compassion self criticism understanding personal emotions',
         sources=['https://ggia.berkeley.edu/practice/self_compassion_break',
                  'https://greatergood.berkeley.edu/article/item/try_selfcompassion']),
    dict(key='perspective',label='hiểu nguyên nhân cảm xúc và nhìn lại một tình huống từ nhiều góc độ',
         query='self distancing reflection understanding difficult emotions perspective',
         sources=['https://ggia.berkeley.edu/bridging/practices/try-self-distancing/',
                  'https://ggia.berkeley.edu/practice/expressive_writing']),
    dict(key='personal_values',label='giá trị, điều mình trân trọng và con người Mao muốn phát triển thành',
         query='personal values self reflection meaningful life best possible self',
         sources=['https://ggia.berkeley.edu/practice/best_possible_self',
                  'https://ggia.berkeley.edu/practice/gratitude_journal']),
    dict(key='connection',label='đồng cảm, sự tin tưởng và ranh giới trong một mối gắn kết',
         query='empathy understanding others feelings personal boundaries connection',
         sources=['https://greatergood.berkeley.edu/topic/empathy/definition',
                  'https://ggia.berkeley.edu/practice/feeling_supported',
                  'https://greatergood.berkeley.edu/topic/compassion/definition']),
)
PERSONAL_HOSTS={'greatergood.berkeley.edu','ggia.berkeley.edu'}
TECHNICAL=re.compile(r'livestream|live.stream|streaming|4k|encoder|bitrate|thumbnail|monetiz|analytics|draft.*live|microphone|camera|obs.studio|equipment|software|resolution|streamlabs|restream|kiếm view|kỹ thuật|thiết bị|độ phân giải|bản nháp|quảng bá|tăng lượt xem|phát trực tiếp',re.I)
PERSONAL_TOPIC=re.compile(r'emotio|feeling|empath|compassion|gratitude|reflect|values|identity|self.|forgiv|curiosity|awe|mindful|connection|trust|boundar|meaning|resilien|belong|supported|kindness',re.I)


def curriculum_tracks(settings):
    return PERSONAL_TRACKS if settings.get('learning_curriculum')=='personal_growth' else TRACKS
TOPICAL = re.compile(r'vtub|waifu|personali|character|audience|viewer|grow|stream|shorts|thumbnail|title|chat|community|talent|brand|retention|discover|engag|content|clip|emotio|empath|compassion|listening|feeling', re.I)


def source_allowed(url):
    try:
        p=urlsplit(url)
        return bool(p.scheme=='https' and not p.username and not p.password and p.port is None
                    and p.hostname in ORIGINS
                    and any(p.path.startswith(prefix) for prefix in ORIGINS[p.hostname])
                    and not re.search(r'\.(pdf|zip|exe|mp4|mp3)$',p.path,re.I))
    except (ValueError,TypeError):
        return False


def canonical(url):
    p=urlsplit(url)
    return urlunsplit((p.scheme,p.netloc.lower(),p.path.rstrip('/'),'',''))


def article_candidate(url):
    p=urlsplit(url)
    if p.hostname=='greatergood.berkeley.edu' and p.path.startswith('/topic/'):
        return p.path.rstrip('/').endswith('/definition')
    if p.hostname=='hololive.hololivepro.com':
        return len(p.path.strip('/').split('/'))>=3
    return True


class SourcePool:
    def __init__(self,journal,tracks=None,personal=False):
        self.journal=journal
        self.tracks=tracks or TRACKS
        self.personal=personal
        self.seen=journal.setdefault('read_sources',{})
        for row in journal.get('history',[]):
            if row.get('source'):
                self.seen.setdefault(canonical(row['source']),row.get('at',time.time()))

    def fresh(self,url):
        return (source_allowed(url) and canonical(url) not in self.seen
                and (not self.personal or urlsplit(url).hostname in PERSONAL_HOSTS and not TECHNICAL.search(url))
                and self.journal.get('unreadable_sources',{}).get(canonical(url),0)<time.time())

    def reject(self,url):
        failed=self.journal.setdefault('unreadable_sources',{})
        failed[canonical(url)]=time.time()+3600
        self.journal['unreadable_sources']=dict(list(failed.items())[-200:])

    def choose(self,track,discovered=()):
        records=[{'url':u,'track':track['key']} for u in discovered if self.fresh(u)]
        records += [r for r in self.journal.get('frontier',[]) if r.get('track')==track['key']]
        records += [{'url':u,'track':track['key']} for u in track['sources']]
        records += self.journal.get('frontier',[])
        records += [{'url':u,'track':t['key']} for t in self.tracks for u in t['sources']]
        last_host=urlsplit(self.journal.get('last_result',{}).get('source','')).hostname
        fresh=[r['url'] for r in records if self.fresh(r.get('url','')) and article_candidate(r['url'])]
        # Prefer the requested subject; host diversity is a tie-breaker there.
        preferred=[u for u in fresh if any(canonical(u)==canonical(r['url']) for r in records[:len(discovered)+len(track['sources'])] if r.get('url'))]
        for values in (preferred,fresh):
            if values:
                return next((u for u in values if urlsplit(u).hostname!=last_host),values[0])
        return None

    def mark_read(self,url,text):
        digest=hashlib.sha256(text.encode()).hexdigest()
        self.seen[canonical(url)]=time.time()
        self.journal['read_sources']=dict(list(self.seen.items())[-1000:])
        hashes=self.journal.setdefault('read_hashes',[])
        if digest in hashes:
            return None
        self.journal['read_hashes']=(hashes+[digest])[-1000:]
        return digest

    def discover(self,base,anchors,track):
        frontier=self.journal.setdefault('frontier',[])
        known={canonical(r['url']) for r in frontier}
        added=0
        for item in anchors:
            url=urljoin(base,item.get('href',''))
            label=item.get('title','')
            if self.personal and (TECHNICAL.search(url+' '+label) or not PERSONAL_TOPIC.search(url+' '+label)):
                continue
            if not self.fresh(url) or canonical(url) in known or not TOPICAL.search(url+' '+label):
                continue
            if len(label.strip())<5:
                continue
            host=urlsplit(url).hostname
            key=track['key'] if self.personal else 'waifu' if host=='hololive.hololivepro.com' else 'emotions' if host=='greatergood.berkeley.edu' else track['key']
            frontier.append({'url':url,'title':label[:160],'track':key})
            known.add(canonical(url));added+=1
            if added>=24:break
        self.journal['frontier']=frontier[-400:]
        return added
