'use strict';
(()=>{
 const root=document.documentElement;
 let active=getComputedStyle(root).colorScheme==='light'?'light':'dark',previewing=false;
 function apply(palette){
  if(!palette)return;
  for(const key of ['accent','button_hover','bg','surface','text','muted','ink'])root.style.setProperty('--'+key,palette[key]);
  root.style.colorScheme=active;root.style.setProperty('--logo-filter',active==='dark'?'brightness(0) invert(1)':'brightness(0)');
  document.body.style.background=palette.gradient?`linear-gradient(${palette.angle}deg,${palette.gradient_start},${palette.gradient_end})`:palette.bg;
 }
 const logos={boreal:'/static/gatearr-logo.png','electric-lime':'/static/branding-variants/gatearr-electric-lime.png','neon-rose':'/static/branding-variants/gatearr-neon-rose.png'};
 function showTheme(theme){root.style.setProperty('--default-brand-logo','url("'+(logos[theme.preset]||logos.boreal)+'")');apply(theme[active]);}
 function saved(){const data=document.getElementById('theme-state');if(data)showTheme(JSON.parse(data.textContent));}
 window.GatearrPage.listen(document,'click',event=>{
  const button=event.target.closest('#theme-editor .theme-presets button'),form=button?.closest('form'),preset=form?.querySelector('[name=preset]')?.value,data=document.getElementById('theme-presets-state');
  if(!preset||!data||previewing||button.disabled)return;const presets=JSON.parse(data.textContent);if(!presets[preset])return;
  previewing=true;showTheme({...presets[preset],preset});
 },true);
 window.GatearrPage.listen(document,'gatearr:savefailed',event=>{if(event.detail.action.pathname==='/admin/branding/themes'){previewing=false;saved();}});
 window.GatearrPage.listen(document,'input',event=>{
  const form=event.target.closest('.palette-editor');if(!form)return;active=form.elements.palette.value;
  const palette=Object.fromEntries(new FormData(form));palette.gradient=form.elements.gradient.checked;palette.angle=Number(palette.angle)||135;apply(palette);
 });
 window.GatearrPage.listen(document,'gatearr:saved',event=>{if(event.detail.form.closest('#theme-editor')||event.detail.action.pathname==='/admin/branding/themes'){previewing=false;saved();}});
 window.GatearrPage.listen(document,'gatearr:themechange',event=>{active=event.detail.mode==='auto'?(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'):event.detail.mode;saved();});
 saved();
})();
