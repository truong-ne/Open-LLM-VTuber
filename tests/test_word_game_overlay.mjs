import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {remainingSeconds} from '../web_tool/mao-5070/draco/word-game-overlay.mjs';
import {cooldownSeconds} from '../web_tool/mao-5070/draco/game-status.mjs';

test('countdown uses server clock offset, clamps at zero and sixty',()=>{
  assert.equal(remainingSeconds({ends_at:1060},1000000,0),60);
  assert.equal(remainingSeconds({ends_at:1060},1020500,0),40);
  assert.equal(remainingSeconds({ends_at:1060},1020500,5000),35);
  assert.equal(remainingSeconds({ends_at:1060},1090000,0),0);
  assert.equal(remainingSeconds({ends_at:1060},0,0),60);
});
test('untrusted player text is rendered as text and shell installs overlay',()=>{
  const overlay=readFileSync(new URL('../web_tool/mao-5070/draco/word-game-overlay.mjs',import.meta.url),'utf8');
  assert.ok(overlay.includes('element.textContent = text'));
  assert.ok(!overlay.includes('innerHTML'));
  const shell=readFileSync(new URL('../scripts/build_draco_shell.mjs',import.meta.url),'utf8');
  assert.ok(shell.includes('createWordGameOverlay'));
});
test('global game cooldown counts down against server time and ends at the exact boundary',()=>{
  const state={phase:'finished',cooldown_ends_at:1090};
  assert.equal(cooldownSeconds(state,1060000),30);
  assert.equal(cooldownSeconds(state,1070000,5000),15);
  assert.equal(cooldownSeconds(state,1089999),1);
  assert.equal(cooldownSeconds(state,1090000),0);
  assert.equal(cooldownSeconds({...state,phase:'playing'},1060000),0);
  assert.equal(cooldownSeconds({phase:'finished'},1060000),0);
});
