"""Configure/record an isolated OBS test. This program cannot start a stream.

OBS portable must already be running. Its password stays in private/ config.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import time
import uuid

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parent.parent
OBS_CONFIG = ROOT / "private/tools/obs-33.0.0/config/obs-studio"
SCENE = "Mao Local Rehearsal"
SOURCE = "Mao Rehearsal Browser"
URL = "http://127.0.0.1:12393/web-tool/mao-5070/rehearsal.html"


class Obs:
    def __init__(self):
        config = json.loads(
            (OBS_CONFIG / "plugin_config/obs-websocket/config.json").read_text()
        )
        self.ws = connect(
            f"ws://127.0.0.1:{config['server_port']}",
            open_timeout=5,
            max_size=8 * 1024 * 1024,
        )
        hello = json.loads(self.ws.recv(timeout=5))["d"]
        authentication = hello["authentication"]
        secret = base64.b64encode(
            hashlib.sha256(
                (config["server_password"] + authentication["salt"]).encode()
            ).digest()
        ).decode()
        response = base64.b64encode(
            hashlib.sha256((secret + authentication["challenge"]).encode()).digest()
        ).decode()
        self.ws.send(
            json.dumps(
                {
                    "op": 1,
                    "d": {
                        "rpcVersion": 1,
                        "authentication": response,
                        "eventSubscriptions": 0,
                    },
                }
            )
        )
        if json.loads(self.ws.recv(timeout=5))["op"] != 2:
            raise RuntimeError("OBS identification failed")

    def call(self, name, data=None):
        if name in {
            "StartStream",
            "ToggleStream",
            "SetStreamServiceSettings",
            "StartVirtualCam",
        }:
            raise PermissionError(
                "Rehearsal cannot publish or configure broadcast credentials"
            )
        identifier = uuid.uuid4().hex
        self.ws.send(
            json.dumps(
                {
                    "op": 6,
                    "d": {
                        "requestType": name,
                        "requestId": identifier,
                        "requestData": data or {},
                    },
                }
            )
        )
        while True:
            payload = json.loads(self.ws.recv(timeout=15))
            if payload["op"] == 7 and payload["d"]["requestId"] == identifier:
                result = payload["d"]
                if not result["requestStatus"]["result"]:
                    raise RuntimeError(f"OBS {name}: {result['requestStatus']}")
                return result.get("responseData", {})

    def assert_idle_stream(self):
        if self.call("GetStreamStatus")["outputActive"]:
            raise RuntimeError(
                "A broadcast is active; stop rehearsal without touching it"
            )

    def configure(self):
        self.assert_idle_stream()
        if self.call("GetRecordStatus")["outputActive"]:
            raise RuntimeError("Recording already active")
        profiles = self.call("GetProfileList")
        if "Mao Local Test" not in profiles["profiles"]:
            self.call("CreateProfile", {"profileName": "Mao Local Test"})
        self.call("SetCurrentProfile", {"profileName": "Mao Local Test"})
        collections = self.call("GetSceneCollectionList")
        if SCENE not in collections["sceneCollections"]:
            self.call("CreateSceneCollection", {"sceneCollectionName": SCENE})
        self.call("SetCurrentSceneCollection", {"sceneCollectionName": SCENE})
        # New OBS collections default to capturing desktop and microphone. Remove
        # every input in this dedicated collection before creating our source.
        for item in self.call("GetInputList")["inputs"]:
            self.call(
                "SetInputMute", {"inputName": item["inputName"], "inputMuted": True}
            )
            self.call("RemoveInput", {"inputName": item["inputName"]})
        scenes = self.call("GetSceneList")["scenes"]
        scene = scenes[0]["sceneName"]
        self.call("SetCurrentProgramScene", {"sceneName": scene})
        self.call(
            "SetVideoSettings",
            {
                "baseWidth": 1280,
                "baseHeight": 720,
                "outputWidth": 1280,
                "outputHeight": 720,
                "fpsNumerator": 30,
                "fpsDenominator": 1,
            },
        )
        settings = {
            "url": "about:blank",
            "width": 1280,
            "height": 720,
            "fps": 30,
            "fps_custom": True,
            "reroute_audio": True,
            "shutdown": False,
            "restart_when_active": False,
        }
        self.call(
            "CreateInput",
            {
                "sceneName": scene,
                "inputName": SOURCE,
                "inputKind": "browser_source",
                "inputSettings": settings,
                "sceneItemEnabled": True,
            },
        )
        self.call("SetInputMute", {"inputName": SOURCE, "inputMuted": False})
        self.call(
            "SetInputAudioMonitorType",
            {"inputName": SOURCE, "monitorType": "OBS_MONITORING_TYPE_NONE"},
        )
        directory = str(ROOT / "private/rehearsals")
        self.call("SetRecordDirectory", {"recordDirectory": directory})
        return {
            "scene_collection": SCENE,
            "sources": self.call("GetInputList")["inputs"],
            "video": self.call("GetVideoSettings"),
            "record_directory": directory,
            "streaming": False,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["configure", "record", "status"])
    parser.add_argument("--seconds", type=int, default=120)
    args = parser.parse_args()
    obs = Obs()
    try:
        obs.assert_idle_stream()
        if args.command == "configure":
            result = obs.configure()
        elif args.command == "status":
            result = {
                "stream": obs.call("GetStreamStatus"),
                "record": obs.call("GetRecordStatus"),
                "stats": obs.call("GetStats"),
            }
        else:
            if not 10 <= args.seconds <= 600:
                raise ValueError("Record between 10 and 600 seconds")
            if (
                obs.call("GetSceneCollectionList")["currentSceneCollectionName"]
                != SCENE
            ):
                raise ValueError("Configure the isolated rehearsal collection first")
            inputs = obs.call("GetInputList")["inputs"]
            if len(inputs) != 1 or inputs[0]["inputName"] != SOURCE:
                raise ValueError("Rehearsal must contain only the Mao browser source")
            if obs.call("GetRecordStatus")["outputActive"]:
                raise ValueError("Another recording is active")
            # Warm the 3D scene before recording to avoid shader/load stalls in
            # the recorded output. Synthetic dialogue starts after warm-up.
            obs.call(
                "SetInputSettings",
                {
                    "inputName": SOURCE,
                    "inputSettings": {
                        "url": URL + "?wait=15000&run=" + uuid.uuid4().hex
                    },
                    "overlay": True,
                },
            )
            time.sleep(10)
            obs.assert_idle_stream()
            obs.call("StartRecord")
            try:
                initial = obs.call("GetStats")
                samples = []
                deadline = time.monotonic() + args.seconds
                while time.monotonic() < deadline:
                    time.sleep(min(5, max(0, deadline - time.monotonic())))
                    obs.assert_idle_stream()
                    samples.append(obs.call("GetStats"))
                final = obs.call("GetStats")
                result = {
                    "stats": final,
                    "streaming": False,
                    "duration_seconds": args.seconds,
                    "render_skipped_frames": final["renderSkippedFrames"]
                    - initial["renderSkippedFrames"],
                    "render_total_frames": final["renderTotalFrames"]
                    - initial["renderTotalFrames"],
                    # Output counters reset for each recording, sometimes just
                    # after StartRecord returns. They are not cumulative.
                    "encoder_skipped_frames": final["outputSkippedFrames"],
                    "encoder_total_frames_before_stop": final["outputTotalFrames"],
                    "minimum_sampled_fps": min(s["activeFps"] for s in samples),
                    "maximum_sampled_cpu": max(s["cpuUsage"] for s in samples),
                }
            finally:
                recording = obs.call("StopRecord")
            result.update(recording)
        suffix = "" if args.command == "record" else "-" + args.command
        destination = ROOT / f"logs/mao-obs-rehearsal{suffix}.json"
        destination.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        obs.ws.close()


if __name__ == "__main__":
    main()
