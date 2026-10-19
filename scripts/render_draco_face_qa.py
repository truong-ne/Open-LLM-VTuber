"""Offline orthographic render of actual face geometry; no desktop/UI control."""
import io
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'web_tool/mao-5070/draco/character.glb').read_bytes()
offset = 12
while offset < len(raw):
    length, kind = struct.unpack_from('<II', raw, offset)
    offset += 8
    if kind == 0x4E4F534A:
        doc = json.loads(raw[offset:offset + length])
    if kind == 0x004E4942:
        binary = raw[offset:offset + length]
    offset += length


def accessor(index):
    a = doc['accessors'][index]
    view = doc['bufferViews'][a['bufferView']]
    width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[a['type']]
    dtype = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8}[a['componentType']]
    size = np.dtype(dtype).itemsize
    return np.ndarray((a['count'], width), dtype=dtype, buffer=binary,
                      offset=view.get('byteOffset', 0) + a.get('byteOffset', 0),
                      strides=(view.get('byteStride', width * size), size)).copy()


textures = {}
meshes = []
for index, mesh in enumerate(doc['meshes']):
    if index not in [4, 10, 11, 12, 13, 14, 15, 16, 17]:
        continue
    p = mesh['primitives'][0]
    mat = doc['materials'][p['material']]
    texture = mat['pbrMetallicRoughness']['baseColorTexture']['index']
    image = doc['images'][doc['textures'][texture]['source']]
    view = doc['bufferViews'][image['bufferView']]
    data = binary[view.get('byteOffset', 0):view.get('byteOffset', 0) + view['byteLength']]
    textures[mat['name']] = np.array(Image.open(io.BytesIO(data)).convert('RGB')) / 255.
    meshes.append({'name': mat['name'], 'position': accessor(p['attributes']['POSITION']),
                   'uv': accessor(p['attributes']['TEXCOORD_0']), 'index': accessor(p['indices']).reshape(-1, 3)})

changes = json.loads((ROOT / 'private/draco-face-rig-geometry.json').read_text())
replacements = {m['name']: m for m in changes}


def render(updated, opened):
    size = 600
    output = np.full((size, size, 3), [.94, .91, .96])
    depth = np.full((size, size), -np.inf)
    names = {m['name'] for m in meshes}
    items = meshes + ([{'name': m['name'], 'position': [], 'uv': [], 'index': []} for m in changes if m['name'] not in names] if updated else [])
    for item in items:
        name = item['name']
        if updated and name in ['CEL5', 'material', 'material_15'] and opened > .025:
            continue
        if name in ['mao_lip_rim', 'mao_upper_teeth', 'mao_tongue'] and opened <= .025:
            continue
        source = replacements.get(name) if updated else None
        vertex = np.array(source['position']).reshape(-1, 3) if source else item['position'].copy()
        if source and source['delta']:
            vertex += np.array(source['delta']).reshape(-1, 3) * opened
        triangles = np.array(source['index']).reshape(-1, 3) if source else item['index']
        uv = np.array(source['uv']).reshape(-1, 2) if source and source['uv'] else item['uv']
        projected = np.column_stack(((vertex[:, 0] + .105) * size / .21, (1.53 - vertex[:, 1]) * size / .21))
        for ids in triangles:
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
            xx = xx + .5
            yy = yy + .5
            u = ((b[1] - c[1]) * (xx - c[0]) + (c[0] - b[0]) * (yy - c[1])) / denominator
            v = ((c[1] - a[1]) * (xx - c[0]) + (a[0] - c[0]) * (yy - c[1])) / denominator
            bary = np.stack((u, v, 1 - u - v), -1)
            z = bary @ vertex[ids, 2]
            target_depth = depth[lo[1]:hi[1] + 1, lo[0]:hi[0] + 1]
            mask = (bary.min(-1) >= -1e-7) & (z > target_depth)
            if not mask.any():
                continue
            if name in textures:
                tex = textures[name]
                coord = np.clip(bary @ uv[ids], 0, 1)
                tx = np.clip((coord[..., 0] * (tex.shape[1] - 1)).astype(int), 0, tex.shape[1] - 1)
                ty = np.clip((coord[..., 1] * (tex.shape[0] - 1)).astype(int), 0, tex.shape[0] - 1)
                color = tex[ty, tx]
            else:
                value = source.get('color', 0x51202a)
                color = np.broadcast_to(np.array([(value >> 16) & 255, (value >> 8) & 255, value & 255]) / 255., (*z.shape, 3)).copy()
            linear = np.where(color <= .04045, color / 12.92, ((color + .055) / 1.055) ** 2.4)
            if updated:
                if name in ['V13_Face_Reference_Lashes_Paint', 'CEL5'] and opened > .02:
                    point = bary @ vertex[ids]
                    ellipse = (point[..., 0] / .0109) ** 2 + ((point[..., 1] - (1.378535 - .0055 * opened)) / (.0012 + .007 * opened)) ** 2
                    mask &= ~((ellipse < 1) & (point[..., 2] > .06))
                if name in ['V13_Face_Reference_Lashes_Paint', 'CEL5', 'V13_Reference_Upper_Lash_Curved_Mask.001', 'V8_Hair_Fine_Luminous_Strands']:
                    mask &= linear.max(-1) >= .0008
                if name == 'V13_Jade_Iris_Original_Detail.001':
                    gray = linear @ np.array([.2126, .7152, .0722])
                    linear = np.clip(gray[..., None] + 1.06 * (linear - gray[..., None]), 0, 1) ** 1.18
                color = np.where(linear <= .0031308, linear * 12.92, 1.055 * np.maximum(linear, 0) ** (1 / 2.4) - .055)
            else:
                # Approximate the previous filmic transform for comparison.
                linear = np.clip((linear * (2.51 * linear + .03)) / (linear * (2.43 * linear + .59) + .14), 0, 1)
                color = np.where(linear <= .0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - .055)
            target_depth[mask] = z[mask]
            target = output[lo[1]:hi[1] + 1, lo[0]:hi[0] + 1]
            target[mask] = color[mask]
    return Image.fromarray((np.clip(output, 0, 1) * 255).astype(np.uint8))


sheet = Image.new('RGB', (1800, 630), '#f0e8f4')
draw = ImageDraw.Draw(sheet)
for column, (updated, opened, label) in enumerate([(False, 0, 'SOURCE / CLOSED'), (True, 0, 'UPDATED / CLOSED'), (True, .85, 'UPDATED / SPEAKING')]):
    sheet.paste(render(updated, opened), (column * 600, 30))
    draw.text((column * 600 + 16, 9), label, fill='#4b3b55')
sheet.save(ROOT / 'private/draco-face-qa.png')
print('private/draco-face-qa.png')
