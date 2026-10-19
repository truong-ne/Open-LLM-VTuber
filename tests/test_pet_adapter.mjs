import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

let now = 0;
const values = [];
const nativeSends = [];
const randomGroups = [];
let meshUpdates = 0;
const model = {
  _idParamAngleY: 'y', _idParamAngleX: 'x', _idParamAngleZ: 'z', _idParamBodyAngleX: 'body',
  _motionManager: { stopAllMotions() {} },
  _model: {
    addParameterValueById(id, value) { values.push([id, value]); },
    update() { meshUpdates += 1; },
  },
  update() {}, startRandomMotion(group) { randomGroups.push(group); return 1; },
};
class Socket {
  listeners = {};
  addEventListener(name, handler) { this.listeners[name] = handler; }
  send(data) { nativeSends.push(JSON.parse(data)); }
  receive(data) { this.listeners.message({ data: JSON.stringify(data) }); }
}
const preferences = new Map([['proactiveSpeakSettings', '{"allowProactiveSpeak":true}']]);
const window = { WebSocket: Socket, getLive2DManager: () => ({ getModel: () => model }) };
const attachTimers = [];
vm.runInNewContext(fs.readFileSync('web_tool/pet-context.js', 'utf8'), {
  window, performance: { now: () => now }, console,
  localStorage: { getItem: key => preferences.get(key), setItem: (key, value) => preferences.set(key, value) },
  setInterval: callback => attachTimers.push(callback),
});
assert.equal(JSON.parse(preferences.get('proactiveSpeakSettings')).allowProactiveSpeak, false);
attachTimers[0]();
model.startRandomMotion('Idle'); model.startRandomMotion('Talk');
assert.deepEqual(randomGroups, []);
const socket = new window.WebSocket();
socket.send(JSON.stringify({ type: 'ai-speak-signal', idle_time: 20 }));
assert.equal(nativeSends.length, 0);
socket.receive({ type: 'audio', display_text: { text: 'Hi Bông!' }, actions: { motions: ['nod'] } });
assert.equal(window.maoPetContext.motionCount, 0);
socket.send(JSON.stringify({ type: 'audio-play-start', display_text: { text: 'Hi Bông!' } }));
assert.equal(window.maoPetContext.lastMotion, 'nod');
now = 250; model.update();
assert.ok(values.some(([id, value]) => id === 'y' && value !== 0));
assert.equal(meshUpdates, 1);
assert.ok(nativeSends.some(message => message.type === 'pet-motion-played' && message.motion === 'nod'));
now = 2100; values.length = 0; model.update();
assert.equal(values.length, 0);
socket.receive({ type: 'audio', display_text: { text: 'Không có sự kiện.' }, actions: { motions: ['idle'] } });
socket.send(JSON.stringify({ type: 'audio-play-start', display_text: { text: 'Không có sự kiện.' } }));
assert.equal(window.maoPetContext.motionCount, 1);
console.log('PET_ADAPTER_OK: gestures follow playback events; no idle speech or random motions.');
