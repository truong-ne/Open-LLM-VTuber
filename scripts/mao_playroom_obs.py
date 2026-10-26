"""An isolated, local OBS composition using a real Chrome/game window."""

import argparse
import base64
import json
from pathlib import Path

from mao_obs_rehearsal import Obs, ROOT

COLLECTION = "Mao Playroom"
CAPTURE = "Mao Game Window"
OVERLAY = "Mao Playroom Overlay"
BACKGROUND = "Mao Playroom Background"
REGISTRY = ROOT / "private/mao-playroom-obs.json"
BASE = "http://127.0.0.1:12395/mao-5070/playroom.html"


def ensure_collection(obs):
    obs.assert_idle_stream()
    if obs.call("GetSceneCollectionList")["currentSceneCollectionName"] != COLLECTION:
        raise PermissionError("Only the dedicated Mao Playroom collection is permitted")


def configure(obs):
    obs.assert_idle_stream()
    if obs.call("GetRecordStatus")["outputActive"]:
        raise PermissionError("Stop the current recording before configuring")
    if COLLECTION not in obs.call("GetSceneCollectionList")["sceneCollections"]:
        obs.call("CreateSceneCollection", {"sceneCollectionName": COLLECTION})
    obs.call("SetCurrentSceneCollection", {"sceneCollectionName": COLLECTION})
    ensure_collection(obs)
    existing = {item["inputName"]: item for item in obs.call("GetInputList")["inputs"]}
    for item in existing.values():
        obs.call("SetInputMute", {"inputName": item["inputName"], "inputMuted": True})
        if item["inputName"] not in {BACKGROUND, CAPTURE, OVERLAY}:
            obs.call("RemoveInput", {"inputName": item["inputName"]})
    scene = obs.call("GetSceneList")["scenes"][0]["sceneName"]
    obs.call("SetCurrentProgramScene", {"sceneName": scene})
    obs.call(
        "SetVideoSettings",
        {
            "baseWidth": 1920,
            "baseHeight": 1080,
            "outputWidth": 1920,
            "outputHeight": 1080,
            "fpsNumerator": 30,
            "fpsDenominator": 1,
        },
    )

    def create_input(data):
        name = data["inputName"]
        if name in existing:
            if existing[name]["unversionedInputKind"] != data["inputKind"]:
                raise ValueError("The managed source has an unexpected type")
            obs.call(
                "SetInputSettings",
                {
                    "inputName": name,
                    "inputSettings": data["inputSettings"],
                    "overlay": True,
                },
            )
            result = obs.call(
                "GetSceneItemId", {"sceneName": scene, "sourceName": name}
            )
            obs.call(
                "SetSceneItemEnabled",
                {
                    "sceneName": scene,
                    "sceneItemId": result["sceneItemId"],
                    "sceneItemEnabled": data["sceneItemEnabled"],
                },
            )
            return result
        return obs.call("CreateInput", data)

    def browser(name, layer):
        return create_input(
            {
                "sceneName": scene,
                "inputName": name,
                "inputKind": "browser_source",
                "inputSettings": {
                    "url": BASE + "?mode=game&layer=" + layer + "&game=2048",
                    "width": 1920,
                    "height": 1080,
                    "fps": 30,
                    "fps_custom": True,
                    "reroute_audio": True,
                    "shutdown": False,
                },
                "sceneItemEnabled": True,
            },
        )

    browser(BACKGROUND, "background")
    created = create_input(
        {
            "sceneName": scene,
            "inputName": CAPTURE,
            "inputKind": "window_capture",
            "inputSettings": {
                "window": "",
                "priority": 0,
                "method": 2,
                "cursor": True,
                "client_area": True,
                "capture_audio": False,
            },
            "sceneItemEnabled": False,
        },
    )
    windows = obs.call(
        "GetInputPropertiesListPropertyItems",
        {"inputName": CAPTURE, "propertyName": "window"},
    )["propertyItems"]
    matches = [
        item
        for item in windows
        if "2048 Game - Play 2048 Game Online" in item["itemName"]
        and "chrome.exe" in str(item["itemValue"]).lower()
    ]
    if len(matches) != 1:
        raise ValueError(
            "Open exactly one dedicated Chrome window for the selected 2048 game"
        )
    obs.call(
        "SetInputSettings",
        {
            "inputName": CAPTURE,
            "inputSettings": {
                "window": matches[0]["itemValue"],
                "priority": 0,
                "method": 2,
                "capture_audio": False,
            },
            "overlay": True,
        },
    )
    obs.call(
        "SetSceneItemTransform",
        {
            "sceneName": scene,
            "sceneItemId": created["sceneItemId"],
            "sceneItemTransform": {
                "positionX": 64,
                "positionY": 188,
                "boundsType": "OBS_BOUNDS_SCALE_INNER",
                "boundsWidth": 1360,
                "boundsHeight": 765,
                "alignment": 5,
                "boundsAlignment": 0,
            },
        },
    )
    browser(OVERLAY, "overlay")
    for index, name in enumerate((BACKGROUND, CAPTURE, OVERLAY)):
        obs.call("SetInputMute", {"inputName": name, "inputMuted": True})
        item = obs.call("GetSceneItemId", {"sceneName": scene, "sourceName": name})
        obs.call(
            "SetSceneItemIndex",
            {
                "sceneName": scene,
                "sceneItemId": item["sceneItemId"],
                "sceneItemIndex": index,
            },
        )
    registry = {
        "collection": COLLECTION,
        "scene": scene,
        "source": CAPTURE,
        "item_id": created["sceneItemId"],
        "visible": False,
        "url": BASE,
        "window_title": "2048 Game - Play 2048 Game Online - Google Chrome",
        "window_value": matches[0]["itemValue"],
    }
    REGISTRY.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    visibility(obs, True)
    obs.call(
        "PressInputPropertiesButton",
        {"inputName": OVERLAY, "propertyName": "refreshnocache"},
    )
    return {
        "configured": True,
        "collection": COLLECTION,
        "window": registry["window_title"],
        "capture_rect": {"x": 64, "y": 188, "width": 1360, "height": 765},
        "streaming": False,
        "microphone": False,
        "desktop_capture": False,
    }


def visibility(obs, show):
    ensure_collection(obs)
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if registry["collection"] != COLLECTION or registry["source"] != CAPTURE:
        raise PermissionError("Unexpected capture registry")
    obs.call(
        "SetSceneItemEnabled",
        {
            "sceneName": registry["scene"],
            "sceneItemId": registry["item_id"],
            "sceneItemEnabled": bool(show),
        },
    )
    url = BASE + "?mode=game&layer=overlay&game=2048" + ("" if show else "&shield=1")
    obs.call(
        "SetInputSettings",
        {"inputName": OVERLAY, "inputSettings": {"url": url}, "overlay": True},
    )
    registry["visible"] = bool(show)
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
    return {"visible": bool(show)}


def frame(obs, program=False):
    ensure_collection(obs)
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if not registry.get("visible"):
        raise PermissionError("The capture is covered")
    windows = obs.call(
        "GetInputPropertiesListPropertyItems",
        {"inputName": CAPTURE, "propertyName": "window"},
    )["propertyItems"]
    if (
        len(
            [
                w
                for w in windows
                if w["itemValue"] == registry.get("window_value")
                and "chrome.exe" in str(w["itemValue"]).lower()
            ]
        )
        != 1
    ):
        raise PermissionError("The selected game window is no longer present")
    source = registry["scene"] if program else CAPTURE
    request = {
        "sourceName": source,
        "imageFormat": "png",
        "imageWidth": 1920 if program else 1360,
    }
    if program:
        request["imageHeight"] = 1080
    return base64.b64decode(
        obs.call("GetSourceScreenshot", request)["imageData"].split(",", 1)[1]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["configure", "hide", "show", "snapshot"])
    parser.add_argument(
        "--output", type=Path, default=ROOT / "logs/mao-playroom-real-game.png"
    )
    args = parser.parse_args()
    obs = Obs()
    try:
        if args.command == "configure":
            result = configure(obs)
        elif args.command in {"hide", "show"}:
            result = visibility(obs, args.command == "show")
        else:
            args.output.write_bytes(frame(obs, True))
            result = {
                "snapshot": str(args.output),
                "real_window": True,
                "streaming": False,
            }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        obs.ws.close()


if __name__ == "__main__":
    main()
