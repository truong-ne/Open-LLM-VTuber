"""Keep the public source paragraph visible while Mao explains it."""
import re


class ReadingFollower:
    def __init__(self):
        self.current = {'matched': False, 'quote': ''}

    async def focus(self, page, quote):
        self.current = {'matched': False, 'quote': str(quote)[:220]}
        words=re.findall(r'[^\W_]+',str(quote),re.UNICODE)[:16]
        if len(words)<4 or page is None or page.is_closed():
            return False
        pattern=re.compile(r'[\W_]*'.join(re.escape(word) for word in words),re.I)
        target=page.locator('p:visible,li:visible,blockquote:visible,h2:visible,h3:visible,dd:visible,div.abstract:visible').filter(has_text=pattern).first
        try:
            await target.wait_for(state='visible',timeout=5000)
            await target.evaluate('''el => {
                let style=document.getElementById('mao-reading-highlight');
                if(!style){style=document.createElement('style');style.id='mao-reading-highlight';
                    style.textContent='[data-mao-reading-active="true"]{outline:2px solid #efad36!important;outline-offset:5px;background-color:#fff1bb!important;color:#222!important;scroll-margin:110px}';document.head.append(style);}
                document.querySelectorAll('[data-mao-reading-active]').forEach(node=>node.removeAttribute('data-mao-reading-active'));
                el.setAttribute('data-mao-reading-active','true');
                el.scrollIntoView({block:'center',behavior:'smooth'});
            }''')
            self.current['matched']=True
            return True
        except Exception as error:
            if type(error).__name__ not in ('TimeoutError','TargetClosedError','Error'):
                raise
            return False

    async def clear(self,page):
        self.current={'matched':False,'quote':''}
        if page and not page.is_closed():
            try:
                await page.locator('[data-mao-reading-active]').evaluate_all(
                    "nodes=>nodes.forEach(node=>node.removeAttribute('data-mao-reading-active'))")
            except Exception:
                pass
