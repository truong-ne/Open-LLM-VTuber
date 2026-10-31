// Native Mao avatar using the shared speech, VAD and IPC providers.
const MaoDracoAvatar = reactExports.memo(() => {
  const {mode} = useMode();
  const {modelInfo} = useLive2DConfig();
  const {forceIgnoreMouse} = useForceIgnoreMouse();
  const {wsState} = useWebSocket();
  const {aiState} = useAiState();
  const ref = reactExports.useRef(null);
  useIpcHandlers();useInterrupt();useAudioTask();
  reactExports.useEffect(() => {
    window.maoDraco.update({mode,scale:modelInfo?.kScale,scrollToResize:modelInfo?.scrollToResize!==false,pointerInteractive:modelInfo?.pointerInteractive!==false,forceIgnoreMouse,socket:wsState,aiState});
  },[mode,modelInfo,forceIgnoreMouse,wsState,aiState]);
  reactExports.useEffect(() => {
    let mounted=true,avatar;const container=ref.current;
    import('http://127.0.0.1:12393/web-tool/mao-5070/draco/native-avatar.mjs?v=48').then(module=>mounted?module.mountNativeAvatar(container,window.maoDraco):null).then(value=>{avatar=value;if(!mounted)value?.dispose();}).catch(error=>{
      if(!mounted)return;
      window.maoDraco.state.lastError=String(error.message||error);console.error('Draco avatar:',error);
      window.electron?.ipcRenderer.send('mao-draco-status',window.maoDraco.state);
    });
    return ()=>{mounted=false;avatar?.dispose();};
  },[]);
  return jsxRuntimeExports.jsx('div',{ref,id:'mao-original-avatar',style:{position:'relative',width:'100%',height:'100%',overflow:'visible'}});
});
