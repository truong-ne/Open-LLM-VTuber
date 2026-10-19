"""Z-buffer inspection of preview morphs, skin, eye ink and cloth, without UI automation."""
import io
import json
import struct
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'web_tool/mao-5070/draco/character.glb').read_bytes()
offset = 12
while offset < len(raw):
    length, kind = struct.unpack_from('<II', raw, offset)
    offset += 8
    if kind == 0x4e4f534a:
        doc = json.loads(raw[offset:offset + length])
    if kind == 0x004e4942:
        binary = raw[offset:offset + length]
    offset += length
textures = {}
for mat in doc['materials']:
    tex = mat.get('pbrMetallicRoughness', {}).get('baseColorTexture')
    if tex is None:
        continue
    img = doc['images'][doc['textures'][tex['index']]['source']]
    view = doc['bufferViews'][img['bufferView']]
    data = binary[view.get('byteOffset', 0):view.get('byteOffset', 0) + view['byteLength']]
    textures[mat['name']] = np.array(Image.open(io.BytesIO(data)).convert('RGBA')) / 255.
meta = json.loads((ROOT / 'private/draco-expression-qa.json').read_text())
blob = (ROOT / 'private/draco-expression-qa.bin').read_bytes()


def array(ref, width=3, dtype=np.float32):
    return np.frombuffer(blob, dtype, ref['count'], ref['offset']).reshape(-1, width)


def render(frame):
    size = 480
    output = np.full((size, size, 3), [.94, .91, .96])
    depth = np.full((size, size), -np.inf)
    if frame['crop'].startswith('face'):
        center = np.array(frame['center']) + [0, .065, 0]
        extent = .26
    else:
        center = np.array([0, .95, 0])
        extent = 1.95
    for mesh, snap in zip(meta['meshes'], frame['meshes']):
        if not snap['visible'] or snap['opacity'] < .05:
            continue
        name = mesh['name']
        vertex = array(snap['position'])
        local = array(snap['local'])
        indices = array(mesh['index'], 3, np.uint32)
        uv = array(mesh['uv'], 2)
        colors = array(mesh['colors']) if 'colors' in mesh else []
        projected = np.column_stack(((vertex[:, 0] - center[0]) / extent * size + size / 2,
                                     (center[1] - vertex[:, 1]) / extent * size + size / 2))
        # Reject off-screen/degenerate triangles in a vector batch. Most body
        # triangles do not contribute to a face close-up.
        corners = projected[indices]
        lows, highs = corners.min(1), corners.max(1)
        area = np.abs(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]))
        valid = (lows[:, 0] < size) & (lows[:, 1] < size) & (highs[:, 0] >= 0) & (highs[:, 1] >= 0) & (area > .025)
        for ids in indices[valid]:
            points = projected[ids]
            lo = np.maximum(0, np.floor(points.min(0)).astype(int))
            hi = np.minimum(size - 1, np.ceil(points.max(0)).astype(int))
            if np.any(lo > hi):
                continue
            a, b, c = points
            denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(denominator) < 1e-9:
                continue
            yy, xx = np.mgrid[lo[1]:hi[1] + 1, lo[0]:hi[0] + 1]
            xx, yy = xx + .5, yy + .5
            u = ((b[1] - c[1]) * (xx - c[0]) + (c[0] - b[0]) * (yy - c[1])) / denominator
            v = ((c[1] - a[1]) * (xx - c[0]) + (a[0] - c[0]) * (yy - c[1])) / denominator
            bary = np.stack((u, v, 1 - u - v), -1)
            z = bary @ vertex[ids, 2]
            target_depth = depth[lo[1]:hi[1] + 1, lo[0]:hi[0] + 1]
            mask = (bary.min(-1) >= -1e-7) & (z > target_depth)
            if not mask.any():
                continue
            if name in textures and len(uv):
                tex = textures[name]
                coord = np.clip(bary @ uv[ids], 0, 1)
                tx = (coord[..., 0] * (tex.shape[1] - 1)).astype(int)
                ty = (coord[..., 1] * (tex.shape[0] - 1)).astype(int)
                color = tex[ty, tx, :3]
                mask &= tex[ty, tx, 3] > .2
                if name in ['V13_Face_Reference_Lashes_Paint', 'CEL5', 'V13_Reference_Upper_Lash_Curved_Mask.001', 'V8_Hair_Fine_Luminous_Strands']:
                    mask &= color.max(-1) > .0103
            elif len(colors):
                linear = bary @ colors[ids]
                color = np.where(linear <= .0031308, linear * 12.92, 1.055 * np.maximum(linear, 0) ** (1 / 2.4) - .055)
            else:
                value = mesh['color']
                color = np.broadcast_to(np.array([(value >> 16) & 255, (value >> 8) & 255, value & 255]) / 255., (*z.shape, 3)).copy()
            if name in ['V13_Face_Reference_Lashes_Paint', 'CEL5'] and frame['open'] > .02:
                point = bary @ local[ids]
                smile = frame.get('smile', 0)
                mouth_y = 1.378535 - .0055 * frame['open'] + smile * .003 * np.clip(np.abs(point[..., 0]) / .012, 0, 1.4) ** 2
                ellipse = (point[..., 0] / (.0109 * (1 + .18 * smile))) ** 2 + ((point[..., 1] - mouth_y) / (.0012 + .007 * frame['open'])) ** 2
                mask &= ~((ellipse < 1) & (point[..., 2] > .06))
            target_depth[mask] = z[mask]
            target = output[lo[1]:hi[1] + 1, lo[0]:hi[0] + 1]
            target[mask] = color[mask] * snap['opacity'] + target[mask] * (1 - snap['opacity'])
    return Image.fromarray((np.clip(output, 0, 1) * 255).astype(np.uint8))


for kind in ['face', 'face-side', 'body']:
    if '--hip' in sys.argv and kind != 'body':
        continue
    if '--face' in sys.argv and not kind.startswith('face'):
        continue
    if '--body' in sys.argv and kind != 'body':
        continue
    frames = [f for f in meta['frames'] if f['crop'] == kind]
    if '--hip' in sys.argv:
        frames = [f for f in frames if f['label'].startswith('hipSway')]
    if not frames:
        continue
    sheet = Image.new('RGB', (480 * 3, 510 * ((len(frames)+2)//3)), '#f0e8f4')
    draw = ImageDraw.Draw(sheet)
    for i, frame in enumerate(frames):
        x, y = i % 3 * 480, i // 3 * 510
        sheet.paste(render(frame), (x, y + 30))
        draw.text((x + 16, y + 9), frame['label'], fill='#4b3b55')
        print(frame['label'], flush=True)
    path = ROOT / f'private/draco-preview-{kind}-qa.png'
    sheet.save(path)
    print(path)
