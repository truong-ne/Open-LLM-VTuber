import test from 'node:test';
import assert from 'node:assert/strict';
import {clockLabel, countdown, seatRows, avatarUrl} from '../web_tool/mao-5070/draco/classroom-state.mjs';

test('classroom counts down with a bounded forty-seat ranking', () => {
  assert.equal(countdown(1060, 1020.5), 40);
  assert.equal(countdown(1060, 1070), 0);
  assert.equal(clockLabel(28800), '8:00:00');
  assert.equal(clockLabel(3659), '1:00:59');
  const rows = seatRows({classroom: {seats: [{nickname: '<script>', correct: 2}]}});
  assert.equal(rows.length, 40);
  assert.equal(rows[0].nickname, '<script>');
  assert.equal(rows[39], null);
});
test('DiceBear avatars render locally and keep an opaque seed deterministic',()=>{
  const first=avatarUrl('random-id&seed=evil');
  assert.ok(first.startsWith('data:image/svg+xml'));
  const svg=decodeURIComponent(first.slice(first.indexOf(',')+1));
  assert.ok(svg.includes('<svg'));
  assert.ok(svg.includes('<path'));
  assert.equal(avatarUrl('same-id'),avatarUrl('same-id'));
  assert.notEqual(avatarUrl('same-id'),avatarUrl('other-id'));

});
