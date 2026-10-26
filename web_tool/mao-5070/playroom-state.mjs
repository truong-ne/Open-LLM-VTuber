// These pixels are shared by the browser layout and the OBS source guide.
export const LAYOUT=Object.freeze({width:1920,height:1080,capture:Object.freeze({x:64,y:188,width:1360,height:765})});
export const MODES=Object.freeze({
  game:{label:'Chơi game',eyebrow:'MỘT VÁN NỮA NHÉ?',title:'Chơi cùng Mao',subtitle:'Thiếp đang nghĩ xem nước tiếp theo nên đi thế nào…',icon:'♧'},
  browser:{label:'Lướt web',eyebrow:'ĐI ĐÂU CÙNG THIẾP?',title:'Một vòng cùng Mao',subtitle:'Cùng thiếp mở một trang mới nhé.',icon:'✧'},
  computer:{label:'Dùng máy tính',eyebrow:'GÓC NHỎ CỦA MAO',title:'Mao đang khám phá',subtitle:'Từng việc một thôi, thiếp đang xem đây.',icon:'⌘'}
});
export const modeOf=value=>Object.hasOwn(MODES,value)?value:'game';
export function fitStage(width,height){return Math.max(.01,Math.min(width/LAYOUT.width,height/LAYOUT.height));}
export function obsLayout(base,mode='game',{syncMao=false}={}){
  const root=new URL(base);if(!['http:','https:'].includes(root.protocol))throw Error('Use the local preview URL.');
  root.search='';root.hash='';
  const link=layer=>{const url=new URL(root);url.search=new URLSearchParams({mode:modeOf(mode),layer});if(layer==='overlay'&&syncMao)url.searchParams.set('mao','1');return url.href;};
  return {canvas:{width:LAYOUT.width,height:LAYOUT.height,fps:30},mode:modeOf(mode),sources_bottom_to_top:[
    {name:'Mao · Nền',type:'browser_source',url:link('background'),width:1920,height:1080},
    {name:'Cửa sổ Chrome hoặc game đã chọn',type:'window_capture',...LAYOUT.capture,fit:'contain',window_title_must_match:true,initially_visible:false},
    {name:'Mao · Khung và avatar',type:'browser_source',url:link('overlay'),width:1920,height:1080}
  ],privacy:'Select a specific window, verify it, then show the Window Capture source. The browser preview controls do not remotely control OBS.',starts_streaming:false};
}

export class CaptureSession{
  constructor({mediaDevices,onChange=()=>{}}){this.mediaDevices=mediaDevices;this.onChange=onChange;this.stream=null;this.shield=true;this.pending=false;this.revision=0;this.closed=false;}
  emit(error=''){this.onChange({stream:this.stream,shield:this.shield,pending:this.pending,error});}
  async choose(){
    if(this.closed)return false;
    this.stop();const revision=++this.revision;this.pending=true;this.emit();
    let stream;
    try{
      if(!this.mediaDevices?.getDisplayMedia)throw Error('Trình duyệt này chưa hỗ trợ chọn cửa sổ. Hãy dùng Chrome hoặc Edge.');
      stream=await this.mediaDevices.getDisplayMedia({video:{displaySurface:'browser',frameRate:{ideal:30,max:30}},audio:false,monitorTypeSurfaces:'exclude',selfBrowserSurface:'exclude',surfaceSwitching:'exclude'});
      if(this.closed||revision!==this.revision){for(const track of stream.getTracks())track.stop();return false;}
      const track=stream.getVideoTracks()[0];
      // Reject unknown surfaces too: an older browser must not silently share a monitor.
      if(!track||!['browser','window'].includes(track.getSettings().displaySurface))throw Error('Hãy chọn một tab hoặc cửa sổ, không chọn toàn bộ màn hình.');
      this.stream=stream;this.pending=false;this.shield=true;
      track.addEventListener('ended',()=>{if(this.stream===stream)this.stop();},{once:true});
      this.emit();return true;
    }catch(error){
      for(const track of stream?.getTracks()||[])track.stop();
      if(revision!==this.revision||this.closed)return false;
      this.pending=false;this.emit(error.name==='NotAllowedError'?'Bạn chưa chia sẻ cửa sổ nào.':error.message);return false;
    }
  }
  reveal(){if(!this.stream||this.closed)return false;this.shield=false;this.emit();return true;}
  hide(){this.shield=true;if(this.pending){this.revision++;this.pending=false;}this.emit();}
  stop(){this.revision++;const stream=this.stream;this.stream=null;this.pending=false;this.shield=true;for(const track of stream?.getTracks()||[])track.stop();this.emit();}
  dispose(){this.stop();this.closed=true;}
}
