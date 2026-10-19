/* Context gestures for the v1 desktop client. No idle speech or random motions. */
(() => {
  "use strict";
  if (window.maoPetContext) return;
  const allowed = new Set(["nod", "shake", "tilt", "shy", "sway"]);
  const state = { lastMotion: null, motionCount: 0, lastEventAt: null, idleEnabled: false };
  window.maoPetContext = state;
  const settings = JSON.parse(localStorage.getItem("proactiveSpeakSettings") || "{}");
  localStorage.setItem("proactiveSpeakSettings", JSON.stringify({ ...settings, allowProactiveSpeak: false }));
  if (!localStorage.getItem("maoPetProxyConfigured")) {
    localStorage.setItem("wsUrl", JSON.stringify("ws://127.0.0.1:12393/proxy-ws"));
    localStorage.setItem("maoPetProxyConfigured", "true");
  }

  let gesture = null;
  let attached = null;
  let petModeRequested = false;
  function attach() {
    const model = window.getLive2DManager?.()?.getModel(0);
    if (!model || attached === model) return model;
    attached = model;
    if (!petModeRequested && window.api?.setMode) {
      petModeRequested = true;
      window.api.setMode("pet");
    }
    model._motionManager?.stopAllMotions();
    const randomMotion = model.startRandomMotion.bind(model);
    model.startRandomMotion = (group, ...args) => {
      if (group === "Idle" || group === "Talk") return -1;
      return randomMotion(group, ...args);
    };
    const update = model.update.bind(model);
    model.update = (...args) => {
      update(...args);
      if (!gesture || !model._model) return;
      const p = (performance.now() - gesture.started) / 2000;
      if (p >= 1) { gesture = null; return; }
      const env = Math.sin(Math.PI * p);
      const add = (id, value) => id && model._model.addParameterValueById(id, value);
      if (gesture.name === "nod") add(model._idParamAngleY, 11 * Math.sin(4 * Math.PI * p) * env);
      if (gesture.name === "shake") add(model._idParamAngleX, 14 * Math.sin(4 * Math.PI * p) * env);
      if (gesture.name === "tilt") add(model._idParamAngleZ, 12 * env);
      if (gesture.name === "shy") {
        add(model._idParamAngleY, -9 * env);
        add(model._idParamAngleZ, 9 * env);
      }
      if (gesture.name === "sway") {
        add(model._idParamBodyAngleX, 7 * Math.sin(2 * Math.PI * p) * env);
        add(model._idParamAngleZ, 7 * Math.sin(2 * Math.PI * p) * env);
      }
      // LAppModel.update already deformed the mesh before these offsets were added.
      // Recompute it now so the gesture is visible in this frame, not reset next frame.
      model._model.update();
      if (!gesture.reported && model._idParamAngleY) {
        gesture.reported = true;
        gesture.notify?.(gesture.name);
      }
    };
    return model;
  }
  function play(actions, notify) {
    const name = actions?.motions?.find(value => allowed.has(value));
    if (!name || !attach()) return;
    gesture = { name, started: performance.now(), notify, reported: false };
    state.lastMotion = name;
    state.motionCount += 1;
    state.lastEventAt = Date.now();
    console.info("[Mao pet] context gesture", name);
  }
  // Only attaches guards when a model appears; this timer never generates actions.
  setInterval(attach, 500);
  const NativeWebSocket = window.WebSocket;
  window.WebSocket = class extends NativeWebSocket {
    constructor(...args) {
      super(...args);
      this.petActions = [];
      this.addEventListener("message", event => {
        let data;
        try { data = JSON.parse(event.data); } catch { return; }
        if (data.type === "audio") this.petActions.push({ text: data.display_text?.text, actions: data.actions });
        if (data.type === "control" && data.text === "conversation-chain-end") this.petActions = [];
      });
    }
    send(raw) {
      let data;
      try { data = JSON.parse(raw); } catch { return super.send(raw); }
      if (data.type === "ai-speak-signal" && Number(data.idle_time) > 0) return;
      if (data.type === "interrupt-signal") { gesture = null; this.petActions = []; }
      if (data.type === "audio-play-start") {
        const index = this.petActions.findIndex(item => item.text === data.display_text?.text);
        if (index >= 0) play(this.petActions.splice(index, 1)[0].actions, motion => {
          this.send(JSON.stringify({ type: "pet-motion-played", motion }));
        });
      }
      return super.send(raw);
    }
  };
})();
