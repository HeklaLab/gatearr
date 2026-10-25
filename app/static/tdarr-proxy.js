'use strict';
(() => {
 const path=document.currentScript.dataset.proxyBase;
 if(!path||!location.pathname.startsWith(path))return;
 const absolute=value=>{
  try{
   const url=new URL(value,document.baseURI);
   if(!['http:','https:','ws:','wss:'].includes(url.protocol)||url.host!==location.host)return value;
   if(url.pathname===path.slice(0,-1)||url.pathname.startsWith(path))return value;
   url.pathname=path+url.pathname.replace(/^\//,'');return url.href;
  }catch{return value;}
 };
 // A base element covers static relative resources, but SPA code also builds
 // root-absolute API, lazy-chunk and Socket.IO URLs at runtime.
 const fetchNative=window.fetch;
 window.fetch=function(input,options){
  if(input instanceof Request){const url=absolute(input.url);if(url!==input.url)input=new Request(url,input);}
  else input=absolute(input);
  return fetchNative.call(this,input,options);
 };
 const openNative=XMLHttpRequest.prototype.open;
 XMLHttpRequest.prototype.open=function(method,url,...args){return openNative.call(this,method,absolute(url),...args);};
 const Socket=window.WebSocket;
 window.WebSocket=new Proxy(Socket,{construct(target,args){args[0]=absolute(args[0]);return Reflect.construct(target,args);}});
 const Events=window.EventSource;
 if(Events)window.EventSource=new Proxy(Events,{construct(target,args){args[0]=absolute(args[0]);return Reflect.construct(target,args);}});
 for(const [type,key] of [[HTMLScriptElement,'src'],[HTMLLinkElement,'href'],[HTMLImageElement,'src'],[HTMLSourceElement,'src']]){
  const descriptor=Object.getOwnPropertyDescriptor(type.prototype,key);
  if(descriptor?.set)Object.defineProperty(type.prototype,key,{...descriptor,set(value){descriptor.set.call(this,absolute(value));}});
 }
 const setAttribute=Element.prototype.setAttribute;
 Element.prototype.setAttribute=function(name,value){
  if((name.toLowerCase()==='src'&&this.matches('script,img,source'))||(name.toLowerCase()==='href'&&this.matches('link')))value=absolute(value);
  return setAttribute.call(this,name,value);
 };
 const notice=()=>parent.postMessage({type:'gatearr:tdarr-failure'},location.origin);
 window.addEventListener('error',event=>{
  if(String(event.message||'').startsWith('ResizeObserver loop'))return;
  if(event.target===window||event.target instanceof HTMLScriptElement||event.target instanceof HTMLLinkElement)notice();
 },true);
 window.addEventListener('unhandledrejection',notice);
})();
