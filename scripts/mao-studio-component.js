const MaoDesktopSubtitle = () => {
  const {isLoaded}=useSubtitleDisplay(),{showSubtitle}=useSubtitle();
  const [spokenText,setSpokenText]=reactExports.useState('');
  reactExports.useEffect(()=>{
    const sync=()=>{
      const bridge=window.maoDraco,audio=bridge?.audio;
      const text=audio&&!audio.paused&&!audio.ended?String(bridge.payload?.displayText?.text||''):'';
      setSpokenText(previous=>previous===text?previous:text);
    };
    sync();const timer=setInterval(sync,100);return()=>clearInterval(timer);
  },[]);
  if(!isLoaded||!showSubtitle||!spokenText)return null;
  return jsxRuntimeExports.jsx('div',{className:'mao-caption',children:jsxRuntimeExports.jsx('p',{children:spokenText})});
};
