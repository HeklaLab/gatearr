'use strict';
(()=>{
 const root=document.documentElement;
 // Theme forms share one revision. Keep their saves sequential until the
 // current response has refreshed the entire editor and its revision tokens.
 let lockedControls=[];
 document.addEventListener('submit',event=>{
  const form=event.target,region=form.closest?.('#theme-editor');
  if(!region||event.defaultPrevented||!form.matches('form[data-dynamic]'))return;
  if(lockedControls.length){event.preventDefault();event.stopImmediatePropagation();return;}
  lockedControls=[...region.querySelectorAll('form button,form input,form select,.theme-policy-bar input')].filter(control=>!form.contains(control)&&!control.disabled);
  for(const control of lockedControls)control.disabled=true;
 },true);
 function unlockThemeForms(event){
  if(event.detail.action.pathname!=='/admin/branding/themes')return;
  for(const control of lockedControls)control.disabled=false;
  lockedControls=[];
 }
 document.addEventListener('gatearr:saved',unlockThemeForms);
 document.addEventListener('gatearr:savefailed',unlockThemeForms);
 let active=getComputedStyle(root).colorScheme==='light'?'light':'dark',previewing=false,selectedPreview=null;
 const activeFor=mode=>mode==='light'?'light':mode==='dark'?'dark':(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
 function apply(palette){
  if(!palette)return;
  for(const key of ['accent','button_hover','bg','surface','text','muted','ink'])root.style.setProperty('--'+key,palette[key]);
  root.style.colorScheme=active;root.style.setProperty('--logo-filter',active==='dark'?'brightness(0) invert(1)':'brightness(0)');
  const scene=new URLSearchParams({bg:(palette.gradient?palette.gradient_start:palette.bg).slice(1),accent:palette.accent.slice(1),end:(palette.gradient?palette.gradient_end:palette.bg).slice(1),mode:active,angle:palette.angle});
  root.style.setProperty('--landscape-image','url("/theme-landscape.svg?'+scene+'")');
  document.body.style.background=palette.gradient?`linear-gradient(${palette.angle}deg,${palette.gradient_start},${palette.gradient_end})`:palette.bg;
 }
 const logos={boreal:'/static/gatearr-logo.png','electric-lime':'/static/branding-variants/gatearr-electric-lime.png','neon-rose':'/static/branding-variants/gatearr-neon-rose.png','pumpkin-glow':'/static/branding-variants/gatearr-pumpkin-glow.png','mocha-latte':'/static/branding-variants/gatearr-mocha-latte.png','electric-terminal':'/static/branding-variants/gatearr-electric-terminal.png','graphite-shades':'/static/branding-variants/gatearr-graphite-shades.png','purple-haze':'/static/branding-variants/gatearr-purple-haze.png','bloody-mary':'/static/branding-variants/gatearr-bloody-mary.png'};
 function showTheme(theme){root.style.setProperty('--default-brand-logo','url("'+(logos[theme.preset]||logos.boreal)+'")');apply(theme[active]);}
 function saved(){const data=document.getElementById('theme-state');if(data)showTheme(JSON.parse(data.textContent));}
 function selectedTheme(){const data=document.getElementById('theme-presets-state');if(!data||!selectedPreview)return null;const presets=JSON.parse(data.textContent);return presets[selectedPreview]?{...presets[selectedPreview],preset:selectedPreview}:null;}
 function showCurrent(){const selected=selectedTheme();if(selected)showTheme(selected);else saved();}
 window.GatearrPage.listen(document,'click',event=>{
  const button=event.target.closest('#theme-preset-form button[type=submit]'),form=button?.closest('form'),preset=form?.querySelector('[name=preset]:checked')?.value,data=document.getElementById('theme-presets-state');
  if(!preset||!data||previewing||button.disabled)return;const presets=JSON.parse(data.textContent);if(!presets[preset])return;
  previewing=true;showTheme({...presets[preset],preset});
 },true);
 window.GatearrPage.listen(document,'change',event=>{
  const input=event.target.closest('#theme-preset-form input[name=preset]');
  if(input){selectedPreview=input.value;const data=document.getElementById('theme-presets-state'),label=document.getElementById('theme-selected-name');if(data&&label){const presets=JSON.parse(data.textContent);label.textContent=presets[input.value]?.name||input.value;}showCurrent();return;}
  const mode=event.target.closest('.theme-policy-bar input[name=mode]');if(mode){document.querySelectorAll('#theme-editor [data-theme-mode]').forEach(input=>input.value=mode.value);active=activeFor(mode.value);showCurrent();}
 });
 window.GatearrPage.listen(document,'gatearr:savefailed',event=>{if(event.detail.action.pathname==='/admin/branding/themes'){previewing=false;saved();}});
 window.GatearrPage.listen(document,'input',event=>{
  const form=event.target.closest('.palette-editor');if(!form)return;active=form.elements.palette.value;
  const palette=Object.fromEntries(new FormData(form));palette.gradient=form.elements.gradient.checked;palette.angle=Number(palette.angle)||135;apply(palette);
 });
 window.GatearrPage.listen(document,'gatearr:saved',async event=>{
  if(event.detail.action.pathname!=='/admin/branding/themes')return;
  previewing=false;selectedPreview=null;
  if(event.detail.data.get('action')==='publish'){
   try{await window.GatearrTheme.reload();const mode=event.detail.data.get('mode');active=mode?activeFor(mode):(getComputedStyle(root).colorScheme==='light'?'light':'dark');}
   catch{location.reload();return;}
  }
  saved();
 });
 window.GatearrPage.listen(document,'gatearr:themechange',event=>{active=activeFor(event.detail.mode);showCurrent();});
 saved();
})();
