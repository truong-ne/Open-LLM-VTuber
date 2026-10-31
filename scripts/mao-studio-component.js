const MaoDesktopSubtitle = () => {
  const {subtitleText,isLoaded}=useSubtitleDisplay(),{showSubtitle}=useSubtitle();
  if(!isLoaded||!showSubtitle||!subtitleText||['Thinking...','New Conversation Started'].includes(subtitleText)||subtitleText===DEFAULT_SUBTITLE.text)return null;
  return jsxRuntimeExports.jsx('div',{className:'mao-caption',children:jsxRuntimeExports.jsx('p',{children:subtitleText})});
};
