/* Direct WebGL renderer for six independently skinned illustration layers. */
(() => {
  const vertex=`attribute vec2 aPosition;attribute vec2 aUV;uniform vec2 uCanvas;uniform float uScale;uniform vec2 uOffset;varying vec2 vUV;void main(){vec2 p=aPosition*uScale+uOffset;gl_Position=vec4(p.x/uCanvas.x*2.0-1.0,1.0-p.y/uCanvas.y*2.0,0,1);vUV=aUV;}`;
  const fragment=`precision mediump float;uniform sampler2D uTexture;uniform float uWire;varying vec2 vUV;void main(){vec4 c=texture2D(uTexture,vUV);if(c.a<0.025)discard;gl_FragColor=mix(c,vec4(0.1,0.8,0.75,0.7),uWire);}`;
  class Renderer {
    constructor(canvas,textureUrl){
      this.canvas=canvas;this.rig=new window.MaoMesh.Rig();this.rms=0;this.paused=false;this.wire=false;this.alive=true;this.frames=0;this.drawMs=0;
      this.gl=canvas.getContext('webgl',{alpha:true,premultipliedAlpha:true,antialias:true});
      if(!this.gl)throw new Error('Trình duyệt không hỗ trợ WebGL');
      this.ready=this.load(textureUrl);
    }
    shader(type,source){const g=this.gl,s=g.createShader(type);g.shaderSource(s,source);g.compileShader(s);if(!g.getShaderParameter(s,g.COMPILE_STATUS))throw new Error(g.getShaderInfoLog(s));return s;}
    buffer(data,target){const g=this.gl,b=g.createBuffer();g.bindBuffer(target,b);g.bufferData(target,data,g.DYNAMIC_DRAW);return b;}
    async load(url){
      const g=this.gl,im=new Image();im.src=url;await im.decode();
      if(im.width!==1536||im.height!==1024)throw new Error('Atlas size does not match rig');
      this.program=g.createProgram();g.attachShader(this.program,this.shader(g.VERTEX_SHADER,vertex));g.attachShader(this.program,this.shader(g.FRAGMENT_SHADER,fragment));g.linkProgram(this.program);
      if(!g.getProgramParameter(this.program,g.LINK_STATUS))throw new Error(g.getProgramInfoLog(this.program));
      this.locations={};for(const key of ['uCanvas','uScale','uOffset','uTexture','uWire'])this.locations[key]=g.getUniformLocation(this.program,key);
      this.pos=g.getAttribLocation(this.program,'aPosition');this.uv=g.getAttribLocation(this.program,'aUV');
      this.texture=g.createTexture();g.bindTexture(g.TEXTURE_2D,this.texture);g.pixelStorei(g.UNPACK_PREMULTIPLY_ALPHA_WEBGL,true);
      g.texImage2D(g.TEXTURE_2D,0,g.RGBA,g.RGBA,g.UNSIGNED_BYTE,im);
      for(const p of [g.TEXTURE_WRAP_S,g.TEXTURE_WRAP_T])g.texParameteri(g.TEXTURE_2D,p,g.CLAMP_TO_EDGE);
      for(const p of [g.TEXTURE_MIN_FILTER,g.TEXTURE_MAG_FILTER])g.texParameteri(g.TEXTURE_2D,p,g.LINEAR);
      this.layers=window.MaoMesh.parts.map(part=>{
        const m=window.MaoMesh.mesh(part);
        return {part,...m,pb:this.buffer(m.vertices,g.ARRAY_BUFFER),ub:this.buffer(m.uv,g.ARRAY_BUFFER),ib:this.buffer(m.indices,g.ELEMENT_ARRAY_BUFFER),lb:this.buffer(m.lines,g.ELEMENT_ARRAY_BUFFER)};
      });
      g.enable(g.BLEND);g.blendFunc(g.ONE,g.ONE_MINUS_SRC_ALPHA);
      for(let i=0;i<120;i++)this.rig.update(1/120);
      this.last=performance.now();this.tick(this.last);
      return this;
    }
    render(){
      const start=performance.now(),g=this.gl,dpr=Math.min(devicePixelRatio||1,2),w=Math.round(this.canvas.clientWidth*dpr),h=Math.round(this.canvas.clientHeight*dpr);
      if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=w;this.canvas.height=h;}
      g.viewport(0,0,w,h);g.clearColor(0,0,0,0);g.clear(g.COLOR_BUFFER_BIT);g.useProgram(this.program);
      const scale=Math.min(w/580,h/1200)*(this.closeup?2:1);
      g.uniform2f(this.locations.uCanvas,w,h);g.uniform1f(this.locations.uScale,scale);g.uniform2f(this.locations.uOffset,w/2-400*scale,this.closeup?h*.35-220*scale:h-1180*scale);
      g.activeTexture(g.TEXTURE0);g.bindTexture(g.TEXTURE_2D,this.texture);g.uniform1i(this.locations.uTexture,0);
      for(const l of this.layers){
        for(let i=0;i<l.source.length;i+=2){const q=window.MaoMesh.deform(l.part,l.source[i],l.source[i+1],this.rig.p);l.vertices[i]=q[0];l.vertices[i+1]=q[1];}
        g.bindBuffer(g.ARRAY_BUFFER,l.pb);g.bufferSubData(g.ARRAY_BUFFER,0,l.vertices);g.enableVertexAttribArray(this.pos);g.vertexAttribPointer(this.pos,2,g.FLOAT,false,0,0);
        g.bindBuffer(g.ARRAY_BUFFER,l.ub);g.enableVertexAttribArray(this.uv);g.vertexAttribPointer(this.uv,2,g.FLOAT,false,0,0);
        g.uniform1f(this.locations.uWire,0);g.bindBuffer(g.ELEMENT_ARRAY_BUFFER,l.ib);g.drawElements(g.TRIANGLES,l.indices.length,g.UNSIGNED_SHORT,0);
        if(this.wire){g.uniform1f(this.locations.uWire,1);g.bindBuffer(g.ELEMENT_ARRAY_BUFFER,l.lb);g.drawElements(g.LINES,l.lines.length,g.UNSIGNED_SHORT,0);}
      }
      this.drawMs=performance.now()-start;this.frames++;
    }
    tick(now){if(!this.alive)return;const dt=(now-this.last)/1000;this.last=now;if(!this.paused)this.rig.update(dt,this.audioLevel?.()??this.rms);this.render();this.raf=requestAnimationFrame(t=>this.tick(t));}
    destroy(){this.alive=false;cancelAnimationFrame(this.raf);const g=this.gl;for(const l of this.layers||[])for(const key of ['pb','ub','ib','lb'])g.deleteBuffer(l[key]);g.deleteTexture(this.texture);g.deleteProgram(this.program);}
  }
  window.MaoMesh.Renderer=Renderer;
})();
