"""Exercise the desktop component with native 3D and a fake IPC boundary."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import unittest

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = """<!doctype html><html><head><meta charset='utf-8'>
<script type='importmap'>{"imports":{"three":"/web_tool/mao-5070/3d/vendor/three.module.js"}}</script>
<style>body{margin:0}#avatar{position:fixed;inset:30px 0 0}</style></head>
<body data-mode='window'><div id='avatar'></div><div id='mao-window-subtitle'><div class='mao-caption'><p></p></div></div>
<script type='module'>
import {mountDesktopClassroom} from '/web_tool/mao-5070/draco/classroom-desktop.mjs';
import {createNativeBridge} from '/web_tool/mao-5070/draco/native-bridge.mjs';
import {mountNativeAvatar} from '/web_tool/mao-5070/draco/native-avatar.mjs';
const ipc={invoke:async(kind,options)=>{window.calls.push({kind,options});window.fixture.classroom.enabled=options.enabled;return structuredClone(window.fixture);},send(){}};
window.calls=[];window.electron={ipcRenderer:ipc};window.api={setMode(){},updateComponentHover(){}};
window.fixture={phase:'playing',round_id:'fake-round',server_now:Date.now()/1000,ends_at:Date.now()/1000+25,hint_count:2,category:'Con vật',hints:['Leo trèo giỏi, thích ăn chuối.'],hint_index:0,letters:['N','K','H','C','Ỉ','O'],slots:[3,3],classroom:{enabled:true,round_number:42,unlimited:true,players:152,account:'@thanhoathirty6',standings:[],seats:[]}};
const names=['Lan Anh','Minh Khang','Bảo Ngọc','Thanh Hóa','Hải Yến','Tuấn Anh','Ngọc Mai','Bạn Mèo','Hoàng Nam','Khánh Linh'];
window.fixture.classroom.standings=Array.from({length:40},(_,i)=>({nickname:names[i%names.length]+(i>=names.length?' '+(Math.floor(i/names.length)+1):''),avatar_seed:'classroom-preview-'+i,correct:Math.max(1,48-i),points:4000-i*50}));window.fixture.classroom.seats=window.fixture.classroom.standings;
window.fixture.classroom.honor=window.fixture.classroom.standings.slice(0,3).map((r,i)=>({...r,honor_points:320-i*80,gold:12-i*3,silver:8,bronze:4}));
window.fixture.classroom.comments=names.slice(0,4).map((nickname,i)=>({id:i,nickname,player_tag:'#00'+(i+1),text:['Mao ơi câu này vui quá','con khỉ','Mình đoán con khỉ','Cả nhà cùng cố lên'][i],elapsed_ms:2000+i*1234,status:'received'}));window.fixture.classroom.round_results=[];
window.liveDiagnostics={connection:'connected',reader:{fresh_comments:5},queue:{queued_comments:1,inflight_comments:0},desktop:{audioErrors:0},comments:[{nickname:'Mèo Gian Khổ',text:'<'+'script>throw Error("unsafe")<'+'/script>',state:'queued',received_at:Date.now()/1000,transitions:[{state:'received'},{state:'queued'}]}]};
window.maoClassroom=mountDesktopClassroom({ipc,fetcher:async(url)=>({ok:true,json:async()=>structuredClone(String(url).includes('/api/live/diagnostics')?window.liveDiagnostics:window.fixture)})});
window.maoDraco=createNativeBridge();window.maoDraco.options={...window.maoDraco.options,mode:'window',maxFps:30};
window.maoDraco.commentFeedFetcher=async()=>({ok:true,json:async()=>({session:'test',revision:0,comments:[],active:false})});
window.maoDraco.singingFetcher=async()=>({ok:true,json:async()=>({phase:'idle'})});
window.maoWordGame={state:window.fixture,clockOffset:0};
await mountNativeAvatar(document.getElementById('avatar'),window.maoDraco);window.testReady=true;
</script></body></html>"""


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/__desktop_fixture":
            body = FIXTURE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()


class ClassroomLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT))
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_native_half_body_layout_and_toggle(self):
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(
                channel="chrome",
                headless=True,
                args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"],
            )
            page = browser.new_page(viewport={"width": 1500, "height": 1000})
            avatar_requests = []
            page.route(
                "https://api.dicebear.com/**",
                lambda route: (
                    avatar_requests.append(route.request.url),
                    route.abort(),
                ),
            )
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(self.base + "/__desktop_fixture", wait_until="domcontentloaded")
            page.wait_for_function(
                "window.testReady && window.maoDraco.state.frames>10", timeout=60000
            )
            self.assertEqual(
                page.locator("#teacher-stage #mao-native-avatar").count(), 1
            )
            self.assertEqual(page.locator(".desk").count(), 40)
            self.assertEqual(page.locator(".student-avatar").count(), 40)
            self.assertEqual(page.locator(".desk-asset").count(), 0)
            self.assertEqual(page.locator(".portrait").count(), 0)
            page.wait_for_function(
                "[...document.querySelectorAll('.desk:not(.empty) .student-avatar')].every(img=>img.complete&&img.naturalWidth>0)",
                timeout=30000,
            )
            first_avatar = page.locator(".student-avatar").first.get_attribute("src")
            page.evaluate("window.fixture.classroom.seats[0].correct+=1")
            page.wait_for_timeout(850)
            self.assertEqual(
                page.locator(".student-avatar").first.get_attribute("src"), first_avatar
            )
            page.evaluate(
                "[window.fixture.classroom.seats[0],window.fixture.classroom.seats[1]]=[window.fixture.classroom.seats[1],window.fixture.classroom.seats[0]]"
            )
            page.wait_for_function(
                "seed => document.querySelectorAll('.student-avatar')[1].src===seed",
                arg=first_avatar,
            )
            self.assertEqual(
                page.locator(".student-avatar").nth(1).get_attribute("src"),
                first_avatar,
            )
            page.evaluate(
                "[window.fixture.classroom.seats[0],window.fixture.classroom.seats[1]]=[window.fixture.classroom.seats[1],window.fixture.classroom.seats[0]]"
            )
            page.wait_for_timeout(850)
            page.locator(".student-avatar").first.dispatch_event("error")
            page.wait_for_function(
                "document.querySelector('.student-avatar').complete && document.querySelector('.student-avatar').naturalWidth>0"
            )
            self.assertEqual(avatar_requests, [])
            page.locator(".student-avatar").first.evaluate(
                "(img,src)=>img.src=src", first_avatar
            )
            page.wait_for_function(
                "document.querySelector('.student-avatar').complete && document.querySelector('.student-avatar').naturalWidth>0"
            )
            self.assertEqual(page.locator(".live-comment").count(), 4)
            self.assertIn(
                "Máy chủ".lower(), page.locator(".comment-method").inner_text().lower()
            )
            self.assertIn("320", page.locator(".honor-points").first.inner_text())
            page.evaluate("window.fixture.classroom.honor[0].honor_points+=10")
            page.wait_for_function(
                "document.querySelector('.honor-points').textContent.includes('330')"
            )
            self.assertEqual(page.locator(".desk").count(), 40)
            page.screenshot(path=str(ROOT / "logs/classroom-desktop.png"))
            for width, height in [(900, 670), (1080, 1950), (550, 1008), (390, 844)]:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(500)
                self.assertFalse(
                    page.evaluate("document.documentElement.scrollWidth>innerWidth")
                )
                self.assertTrue(
                    page.evaluate("""() => {
                    const r=document.querySelector('.classroom-frame').getBoundingClientRect();
                    return Math.abs(r.width/r.height-9/16)<.003;
                }""")
                )
                self.assertTrue(
                    page.evaluate("""() => {
                    const grid=document.querySelector('.desks'),board=document.querySelector('.classroom-board').getBoundingClientRect();
                    if(getComputedStyle(grid).display!=='grid')return false;
                    return [...grid.children].every(desk=>{
                        const d=desk.getBoundingClientRect(),g=grid.getBoundingClientRect();
                        if(d.width<=0||d.height<=0||d.left<g.left-1||d.right>g.right+1||d.top<board.bottom||d.bottom>g.bottom+1)return false;
                        if(!desk.classList.contains('empty')){
                            const a=desk.querySelector('.student-avatar').getBoundingClientRect();
                            if(a.width>d.width||a.height>d.height||a.top<d.top-8||a.bottom>d.bottom+1)return false;
                        }
                        return true;
                    });
                }""")
                )
                self.assertEqual(
                    page.locator(
                        ".classroom-footer, .classroom-demo, #session-time, #hours"
                    ).count(),
                    0,
                )
                self.assertEqual(page.locator(".honor-person").count(), 3)
                self.assertIn(
                    "Segoe UI",
                    page.locator(".classroom-masthead h1").evaluate(
                        "(el)=>getComputedStyle(el).fontFamily"
                    ),
                )
                self.assertTrue(
                    page.evaluate(
                        "[...document.querySelectorAll('.honor-person')].every(el=>el.getBoundingClientRect().bottom<=document.querySelector('.classroom-honor').getBoundingClientRect().bottom)"
                    )
                )
                page.screenshot(path=str(ROOT / f"logs/classroom-desktop-{width}.png"))
            page.locator(".classroom-masthead").screenshot(
                path=str(ROOT / "logs/classroom-vietnamese-header.png")
            )
            page.evaluate("""() => {
                window.fixture.phase='finished';window.fixture.answer='con khỉ';window.fixture.explanation='Khỉ là con vật leo trèo giỏi.';
                window.fixture.classroom.round_results=[{position:1,nickname:'Lan Anh',elapsed_ms:2000,bonus:10},{position:2,nickname:'Minh Khang',elapsed_ms:3234,bonus:6}];
                window.fixture.classroom.comments[0].status='correct';window.fixture.classroom.comments[0].position=1;
            }""")
            page.wait_for_function(
                "document.querySelectorAll('.podium-chip').length===2"
            )
            self.assertIn("Đúng #1", page.locator(".live-comment").first.inner_text())
            self.assertIn("+10", page.locator(".podium-chip").first.inner_text())
            self.assertIn("Lan Anh", page.locator("#answer-title").inner_text())
            page.screenshot(path=str(ROOT / "logs/classroom-forty-result.png"))
            page.evaluate(
                "window.fixture.phase='playing';window.fixture.classroom.round_results=[]"
            )
            page.set_viewport_size({"width": 1500, "height": 1000})
            page.evaluate(
                "document.querySelector('#mao-window-subtitle p').textContent='Chào cả nhà, Mao đang nghe mọi người đoán nè!'"
            )
            page.wait_for_function(
                "document.getElementById('teacher-speech').textContent.includes('Mao đang nghe')"
            )
            page.evaluate(
                "window.maoDraco.audio={paused:false,ended:false,currentTime:.1};window.maoDraco.payload={volumes:Array(100).fill(.5),sliceLength:20,displayText:{text:'Chào cả lớp!'}};window.maoDraco.speechSession=true"
            )
            page.wait_for_function("window.maoDraco.state.mouthPeak>0", timeout=10000)
            page.evaluate(
                "window.maoDraco.audio=null;window.maoDraco.speechSession=false"
            )
            page.evaluate(
                "window.fixture.classroom.standings[0].nickname='<img src=x onerror=alert(1)>';window.fixture.classroom.seats[0].nickname='<img src=x onerror=alert(1)>'"
            )
            page.wait_for_function(
                "document.querySelector('.seat-name').textContent.startsWith('<img')"
            )
            self.assertEqual(page.locator(".seat-name img").count(), 0)
            page.click('[data-action="panel"]')
            page.click('[data-action="off"]')
            page.locator(".mao-classroom").wait_for(state="hidden")
            self.assertEqual(
                page.locator("#current-mode-name").inner_text(), "Phòng của Mao"
            )
            self.assertEqual(
                page.evaluate("window.calls.at(-1).options.enabled"), False
            )
            page.wait_for_function(
                "document.querySelector('#avatar > #mao-native-avatar')!==null"
            )
            page.wait_for_function("window.maoClassroom.music.playing===true")
            page.set_viewport_size({"width": 568, "height": 1040})
            self.assertTrue(page.locator(".mao-comments").is_hidden())
            page.evaluate("""() => {
                window.dispatchEvent(new CustomEvent('mao-reply-event',{detail:{type:'user-input-transcription',source:'tiktok-live',batch_id:'room-test',text:'Bình luận người xem'+String.fromCharCode(10)+JSON.stringify({comment_groups:[{comment:'Mao đang dùng model nào vậy?',nicknames:['Lan Anh']}]})}}));
                window.dispatchEvent(new CustomEvent('mao-reply-playback'));
            }""")
            page.locator(".mao-comments").wait_for(state="visible")
            self.assertIn(
                "Mao đang dùng model nào",
                page.locator(".mao-comment__text").first.inner_text(),
            )
            self.assertIn(
                "Phòng của Mao", page.locator(".mao-comments__title").inner_text()
            )
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(2300)
            self.assertTrue(page.locator(".mao-comments").is_visible())
            self.assertTrue(
                page.evaluate("""()=>{
                const p=document.querySelector('.mao-comments').getBoundingClientRect();
                const area=document.querySelector('.mao-comment-layer').getBoundingClientRect();
                return p.left>=area.left && p.left<area.left+30 && p.top>area.top+area.height/2 && p.bottom<area.bottom-80;
            }""")
            )
            page.screenshot(path=str(ROOT / "logs/mao-room-comment-visible.png"))
            page.click('[data-action="panel"]')
            page.locator(".mao-live-monitor summary").click()
            page.wait_for_function(
                "document.querySelector('.mao-live-monitor').textContent.includes('Mèo Gian Khổ')"
            )
            self.assertIn(
                "<script>", page.locator(".mao-live-monitor li p").inner_text()
            )
            self.assertEqual(page.locator(".mao-live-monitor script").count(), 0)
            self.assertTrue(
                page.evaluate(
                    "()=>{const r=document.querySelector('.classroom-controls').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight;}"
                )
            )
            page.screenshot(path=str(ROOT / "logs/mao-live-monitor.png"))
            page.click('[data-action="panel"]')
            page.evaluate(
                "window.dispatchEvent(new CustomEvent('mao-reply-event',{detail:{type:'interrupt-signal'}}))"
            )
            page.evaluate("window.maoClassroom.showPreview(true)")
            page.locator(".mao-classroom").wait_for(state="visible")
            page.evaluate("window.fixture.classroom.honor[0].honor_points+=10")
            page.wait_for_function(
                "document.querySelector('.honor-points').textContent.includes('340')"
            )
            page.evaluate("window.maoClassroom.showPreview(false)")
            page.locator(".mao-classroom").wait_for(state="hidden")
            page.click('[data-action="panel"]')
            page.click('[data-action="on"]')
            page.locator(".mao-classroom").wait_for(state="visible")
            self.assertTrue(page.evaluate("window.calls.at(-1).options.enabled"))
            self.assertEqual(
                page.locator("#current-mode-name").inner_text(), "Vua Tiếng Việt"
            )
            self.assertEqual(errors, [])
            browser.close()


if __name__ == "__main__":
    unittest.main()
