"""Compose only Mao's dedicated Chrome window beneath the transparent pet."""
from scripts.mao_obs_rehearsal import Obs, ROOT
from src.open_llm_vtuber.live.idle_host_storage import read_json, write_json

CAPTURE = 'Mao Research Chrome'
KEY = 'Transparent pet background'


class ResearchComposition:
    def __init__(self):
        self.obs = None
        self.last = None
        self.path = ROOT / 'private/mao-research-obs.json'

    def update(self, title):
        desktop = read_json(ROOT / 'private/draco-desktop-status.json')
        pet = desktop.get('mode') == 'pet' and desktop.get('ready') is True
        signature = (pet, title)
        if signature == self.last:
            return
        if self.obs is None:
            self.obs = Obs()
        obs = self.obs
        if obs.call('GetSceneCollectionList')['currentSceneCollectionName'] != 'Mao YouTube Live':
            return
        scene = obs.call('GetSceneList')['currentProgramSceneName']
        items = obs.call('GetSceneItemList', {'sceneName': scene})['sceneItems']
        avatar = next((i for i in items if i['sourceName'] == 'Mao Avatar'), None)
        if avatar is None:
            return
        saved = read_json(self.path)
        if 'avatar_window_transform' not in saved:
            saved['avatar_window_transform'] = avatar['sceneItemTransform']
            write_json(self.path, saved)
        windows = obs.call('GetInputPropertiesListPropertyItems', {
            'inputName': 'Mao Avatar', 'propertyName': 'window'})['propertyItems']
        matches = [w for w in windows if w.get('itemEnabled')
                   and str(w['itemValue']).lower().endswith(':chrome.exe')
                   and w['itemName'] == '[chrome.exe]: ' + title + ' - Google Chrome']
        chrome = next((i for i in items if i['sourceName'] == CAPTURE), None)
        if chrome is None:
            result = obs.call('CreateInput', {'sceneName': scene, 'inputName': CAPTURE,
                'inputKind': 'window_capture', 'inputSettings': {}, 'sceneItemEnabled': False})
            chrome = {'sceneItemId': result['sceneItemId']}
        if matches:
            obs.call('SetInputSettings', {'inputName': CAPTURE, 'overlay': True,
                'inputSettings': {'window': matches[0]['itemValue'], 'method': 2,
                    'priority': 0, 'capture_audio': False, 'client_area': True, 'cursor': False}})
        # Strict title match: never fall back to an unrelated personal Chrome tab.
        obs.call('SetSceneItemEnabled', {'sceneName': scene,
            'sceneItemId': chrome['sceneItemId'], 'sceneItemEnabled': pet and len(matches) == 1})
        filters = obs.call('GetSourceFilterList', {'sourceName': 'Mao Avatar'})['filters']
        if not any(f['filterName'] == KEY for f in filters):
            obs.call('CreateSourceFilter', {'sourceName': 'Mao Avatar', 'filterName': KEY,
                'filterKind': 'color_key_filter_v2', 'filterSettings': {
                    'key_color_type': 'custom', 'key_color': 0, 'similarity': 1,
                    'smoothness': 1, 'opacity': 1.0}})
        obs.call('SetSourceFilterEnabled', {'sourceName': 'Mao Avatar',
            'filterName': KEY, 'filterEnabled': pet})
        if pet:
            canvas = obs.call('GetVideoSettings')
            transform = {'positionX': 0, 'positionY': 0, 'alignment': 5,
                'boundsType': 'OBS_BOUNDS_SCALE_INNER', 'boundsWidth': canvas['baseWidth'],
                'boundsHeight': canvas['baseHeight'], 'boundsAlignment': 0,
                'cropLeft': 0, 'cropRight': 0, 'cropTop': 0, 'cropBottom': 0}
            for item in (chrome, avatar):
                obs.call('SetSceneItemTransform', {'sceneName': scene,
                    'sceneItemId': item['sceneItemId'], 'sceneItemTransform': transform})
            obs.call('SetSceneItemIndex', {'sceneName': scene,
                'sceneItemId': chrome['sceneItemId'], 'sceneItemIndex': 1})
        else:
            original = saved['avatar_window_transform']
            writable = {k: original[k] for k in ('positionX','positionY','alignment','boundsType',
                'boundsWidth','boundsHeight','boundsAlignment','cropLeft','cropRight','cropTop','cropBottom',
                'rotation','scaleX','scaleY') if k in original}
            obs.call('SetSceneItemTransform', {'sceneName': scene,
                'sceneItemId': avatar['sceneItemId'], 'sceneItemTransform': writable})
        if not pet or len(matches) == 1:
            self.last = signature
        saved.update(pet=pet, chrome_visible=pet and len(matches)==1, chrome_title=title)
        write_json(self.path, saved)

    def close(self):
        if self.obs:
            self.obs.ws.close()
            self.obs = None
