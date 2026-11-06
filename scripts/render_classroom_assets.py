"""Render selected CC0 Kenney OBJ furniture into crisp transparent desktop sprites."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import zipfile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "web_tool/mao-5070/draco/assets/classroom"
MODELS = {
    "books": "books",
    "plant": "pottedPlant",
}


def geometry(archive, name):
    materials, current = {}, None
    for line in archive.read(f"Models/{name}.mtl").decode().splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "newmtl":
            current = parts[1]
        elif parts[0] == "Kd":
            materials[current] = [float(v) for v in parts[1:4]]
    vertices, normals, groups = [], [], {}
    for line in archive.read(f"Models/{name}.obj").decode().splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "v":
            vertices.append([float(v) for v in parts[1:4]])
        elif parts[0] == "vn":
            normals.append([float(v) for v in parts[1:4]])
        elif parts[0] == "usemtl":
            current = parts[1]
        elif parts[0] == "f":
            group = groups.setdefault(
                current, {"position": [], "normal": [], "color": materials[current]}
            )
            corners = [v.split("/") for v in parts[1:]]
            for i in range(1, len(corners) - 1):
                for corner in (corners[0], corners[i], corners[i + 1]):
                    group["position"].extend(vertices[int(corner[0]) - 1])
                    group["normal"].extend(normals[int(corner[2]) - 1])
    return list(groups.values())


HTML = """<!doctype html><style>html,body{margin:0;background:transparent}canvas{display:block}</style><script type='module'>
import * as T from '/web_tool/mao-5070/3d/vendor/three.module.js';
const renderer=new T.WebGLRenderer({alpha:true,antialias:true,preserveDrawingBuffer:true});renderer.setSize(768,768);renderer.setPixelRatio(1);renderer.outputColorSpace=T.SRGBColorSpace;renderer.setClearColor(0,0);document.body.append(renderer.domElement);
const data=await(await fetch('/__model')).json(),scene=new T.Scene(),asset=new T.Group();
for(const row of data){const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(row.position,3));g.setAttribute('normal',new T.Float32BufferAttribute(row.normal,3));const color=new T.Color(...row.color).convertSRGBToLinear();asset.add(new T.Mesh(g,new T.MeshStandardMaterial({color,roughness:.8,metalness:0})));}
scene.add(asset);const bounds=new T.Box3().setFromObject(asset),center=bounds.getCenter(new T.Vector3()),size=bounds.getSize(new T.Vector3());asset.position.sub(center);const radius=size.length()/2;
const camera=new T.OrthographicCamera(-radius,radius,radius,-radius,.01,radius*20);camera.position.set(radius*5,radius*4,radius*6);camera.lookAt(0,0,0);camera.updateMatrixWorld(true);
let max=0;for(const x of [bounds.min.x,bounds.max.x])for(const y of [bounds.min.y,bounds.max.y])for(const z of [bounds.min.z,bounds.max.z]){const p=new T.Vector3(x,y,z).sub(center).project(camera);max=Math.max(max,Math.abs(p.x),Math.abs(p.y));}camera.zoom=1/(max*1.08);camera.updateProjectionMatrix();
scene.add(new T.HemisphereLight(0xfffbef,0x738075,2));const light=new T.DirectionalLight(0xfff5dc,3.5);light.position.set(-3,7,5);scene.add(light);const fill=new T.DirectionalLight(0xe6f4ff,1);fill.position.set(4,2,-3);scene.add(fill);renderer.render(scene,camera);window.ready=true;
</script>"""


def main():
    model = []

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path in {"/__render", "/__model"}:
                body = (
                    HTML.encode()
                    if self.path == "/__render"
                    else json.dumps(model).encode()
                )
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/html" if self.path == "/__render" else "application/json",
                )
                self.end_headers()
                self.wfile.write(body)
            else:
                super().do_GET()

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(Handler, directory=str(ROOT))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with (
            zipfile.ZipFile(ROOT / "private/kenney-classroom-furniture.zip") as archive,
            sync_playwright() as runtime,
        ):
            browser = runtime.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 768, "height": 768})
            for dest, name in MODELS.items():
                model[:] = geometry(archive, name)
                page.goto(f"http://127.0.0.1:{server.server_port}/__render")
                page.wait_for_function("window.ready===true")
                page.locator("canvas").screenshot(
                    path=str(DEST / f"{dest}.png"), omit_background=True
                )
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
