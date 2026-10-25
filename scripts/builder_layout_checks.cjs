// Runs in the page: detect readable tools, containment and a full-height preview.
module.exports=function builderLayoutChecks(){
 const root=document.querySelector('#page-studio');if(!root)return [];
 const issues=[];
 for(const button of root.querySelectorAll('.studio-palette button')){
  const box=button.getBoundingClientRect(),walker=document.createTreeWalker(button,NodeFilter.SHOW_TEXT);
  for(let text=walker.nextNode();text;text=walker.nextNode())for(const match of text.textContent.matchAll(/\S+/g)){
   const range=document.createRange();range.setStart(text,match.index);range.setEnd(text,match.index+match[0].length);
   const rects=[...range.getClientRects()].filter(r=>r.width>0);
   if(rects.length>1||rects.some(r=>r.left<box.left-1||r.right>box.right+1))issues.push('Unreadable palette word: '+match[0]);
  }
  if(button.scrollWidth>button.clientWidth+2)issues.push('Palette overflow: '+button.textContent);
 }
 for(const selector of ['.studio-palette','.studio-canvas','.studio-inspector']){
  const panel=root.querySelector(selector),box=panel.getBoundingClientRect(),parent=panel.parentElement.getBoundingClientRect();
  if(box.left<parent.left-1||box.right>parent.right+1||panel.scrollWidth>panel.clientWidth+2)issues.push('Panel overflow: '+selector);
  if(panel.scrollHeight>panel.clientHeight+2&&['auto','scroll'].includes(getComputedStyle(panel).overflowY))issues.push('Nested scrollbar: '+selector);
 }
 const frame=root.querySelector('#studio-preview'),doc=frame.contentDocument;
 if(doc?.querySelector('.portal-main')&&frame.clientHeight+3<doc.documentElement.scrollHeight)issues.push('Clipped preview');
 if(document.documentElement.scrollWidth>innerWidth+2)issues.push('Page overflow');
 return [...new Set(issues)];
};
