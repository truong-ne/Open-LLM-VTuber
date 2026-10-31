import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
let model='/live2d-models/mao_pro/a.json',subtitleText='Thinking...';
const jsx=(type,props)=>({type,props});
const context={jsxRuntimeExports:{jsx},useSubtitleDisplay:()=>({isLoaded:true,subtitleText}),useSubtitle:()=>({showSubtitle:true}),DEFAULT_SUBTITLE:{text:'Default greeting'}};
vm.createContext(context);
const source=fs.readFileSync('scripts/mao-studio-component.js','utf8');
vm.runInContext(source+';globalThis.ui={MaoDesktopSubtitle};',context);
assert.equal(context.ui.MaoDesktopSubtitle(),null);
subtitleText='Mao đang nghe đây!';
assert.equal(context.ui.MaoDesktopSubtitle().props.children.props.children,subtitleText);
assert.ok(!source.includes('MaoStudioHeader'));
assert.ok(!source.includes('useTextInput'));
model='/other/model.json';
console.log('Mao livestream: no header/composer, dialogue captions passed.');
if(process.argv.includes('--layout-fixture')){
  fs.writeFileSync('logs/mao-studio-layout-fixture.html','<main><div id="mao-original-avatar"></div><div id="mao-window-subtitle" style="position:absolute;left:50%;transform:translateX(-50%)"><div class="mao-caption"><p>Mao đang nghe đây! Hôm nay có chuyện gì vui không? Kể một chút đi, Mao muốn nghe câu chuyện của bạn.</p></div></div></main>');
}
