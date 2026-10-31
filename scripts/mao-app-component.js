// Mao has one livestream surface. There is no settings drawer or operator panel.
function AppContent() {
  const {mode}=useMode();
  const windowed=mode==='window';
  reactExports.useEffect(()=>{
    Object.assign(document.documentElement.style,{overflow:'hidden',height:'100%'});
    Object.assign(document.body.style,{overflow:'hidden',height:'100%',position:'fixed',width:'100%'});
  },[]);
  return jsxRuntimeExports.jsxs(jsxRuntimeExports.Fragment,{children:[
    windowed&&window.api&&jsxRuntimeExports.jsx(TitleBar,{}),
    jsxRuntimeExports.jsx(Box,{position:'absolute',top:windowed&&window.api?'30px':0,left:0,right:0,bottom:0,children:jsxRuntimeExports.jsx(MaoDracoAvatar,{})}),
    windowed&&jsxRuntimeExports.jsx(Box,{id:'mao-window-subtitle',position:'absolute',bottom:'24px',left:'50%',transform:'translateX(-50%)',zIndex:10,width:'90%',children:jsxRuntimeExports.jsx(MaoDesktopSubtitle,{})}),
    !windowed&&jsxRuntimeExports.jsx(InputSubtitle,{})
  ]});
}
