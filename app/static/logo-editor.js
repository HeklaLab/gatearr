'use strict';
(()=>{
 const prepared=new WeakSet(),sources=new WeakMap(),savedFiles=new WeakMap();let dialogOpen=false;
 const fr=()=>document.documentElement.lang.startsWith('fr');
 const t=(en,translated)=>fr()?translated:en;
 function error(input,message){input.setCustomValidity(message);const notice=input.closest('.upload-control')?.querySelector('.upload-error');if(notice){notice.textContent=message;notice.hidden=false;input.closest('.upload-control').querySelector('.upload-picker')?.focus();}else input.reportValidity();}
 async function edit(input,file){
  if(dialogOpen)return;dialogOpen=true;
  const previous=savedFiles.get(input),isImage=input.dataset.logoEditor==='image';
  input.setCustomValidity(isImage?t('Finish adjusting the image before saving.','Terminez l’ajustement de l’image avant d’enregistrer.'):t('Finish adjusting the logo before saving.','Terminez l’ajustement du logo avant d’enregistrer.'));
  const url=URL.createObjectURL(file),image=new Image();let dialog;
  try{
   if(file.size>(isImage?40:5)*1024*1024)throw Error(isImage?t('Choose an image up to 40 MB before resizing.','Choisissez une image de 40 Mo maximum avant redimensionnement.'):t('Choose an image up to 5 MB.','Choisissez une image de 5 Mo maximum.'));
   image.src=url;await image.decode();
   if(image.naturalWidth*image.naturalHeight>40000000)throw Error(t('Choose an image under 40 megapixels.','Choisissez une image de moins de 40 mégapixels.'));
   dialog=document.createElement('dialog');dialog.className='logo-editor';dialog.setAttribute('aria-labelledby','logo-editor-title');
   const title=document.createElement('h2');title.id='logo-editor-title';title.textContent=isImage?t('Adjust your image','Ajuster l’image'):t('Adjust your logo','Ajuster le logo');
   const hint=document.createElement('p');hint.className='hint';hint.textContent=isImage?t('Keep the full image, or zoom and drag to adjust the crop. It will be resized before uploading.','Conservez l’image entière, ou zoomez et déplacez-la pour ajuster le cadrage. Elle sera redimensionnée avant l’envoi.'):t('Keep the full image, or zoom and drag to adjust the crop. The saved logo is resized automatically.','Conservez l’image entière, ou zoomez et déplacez-la pour ajuster le cadrage. Le logo enregistré est redimensionné automatiquement.');
   const canvas=document.createElement('canvas');canvas.tabIndex=0;canvas.setAttribute('aria-label',isImage?t('Image preview','Aperçu de l’image'):t('Logo preview','Aperçu du logo'));
   const controls=document.createElement('div');controls.className='logo-editor-controls';
   const aspectLabel=document.createElement('label');aspectLabel.textContent=t('Format','Format');const aspect=document.createElement('select');
   for(const [value,label] of [['original',t('Original proportions','Proportions d’origine')],['3',t('Wide · 3:1','Horizontal · 3:1')],['1',t('Square · 1:1','Carré · 1:1')]]){const option=document.createElement('option');option.value=value;option.textContent=label;aspect.append(option);}aspectLabel.append(aspect);
   const zoomLabel=document.createElement('label');zoomLabel.textContent=t('Zoom','Zoom');const zoom=document.createElement('input');zoom.type='range';zoom.min='1';zoom.max='4';zoom.step='.01';zoom.value='1';zoomLabel.append(zoom);controls.append(aspectLabel,zoomLabel);
   const actions=document.createElement('div');actions.className='form-actions';
   const button=(label,secondary=false)=>{const b=document.createElement('button');b.type='button';b.textContent=label;if(secondary)b.className='secondary';actions.append(b);return b;};
   const reset=button(t('Show full image','Afficher entièrement'),true),cancel=button(t('Cancel','Annuler'),true),apply=button(isImage?t('Use this image','Utiliser cette image'):t('Use this logo','Utiliser ce logo'));
   dialog.append(title,hint,canvas,controls,actions);document.body.append(dialog);
   let offsetX=0,offsetY=0,drag,accepted=false;const ctx=canvas.getContext('2d');
   function draw(resize=false){
    if(resize){const ratio=aspect.value==='original'?image.naturalWidth/image.naturalHeight:Number(aspect.value);canvas.width=Math.max(1,Math.round(Math.min(1024,1024*ratio,image.naturalWidth)));canvas.height=Math.max(1,Math.round(canvas.width/ratio));}
    ctx.clearRect(0,0,canvas.width,canvas.height);const scale=Math.min(canvas.width/image.naturalWidth,canvas.height/image.naturalHeight)*Number(zoom.value),w=image.naturalWidth*scale,h=image.naturalHeight*scale;
    ctx.drawImage(image,(canvas.width-w)/2+offsetX,(canvas.height-h)/2+offsetY,w,h);
   }
   function fit(){offsetX=offsetY=0;zoom.value='1';draw(true);}
   aspect.addEventListener('change',fit);zoom.addEventListener('input',()=>draw());reset.addEventListener('click',fit);
   canvas.addEventListener('pointerdown',event=>{drag={x:event.clientX,y:event.clientY,offsetX,offsetY};canvas.setPointerCapture(event.pointerId);});
   canvas.addEventListener('pointermove',event=>{if(!drag)return;const rect=canvas.getBoundingClientRect();offsetX=drag.offsetX+(event.clientX-drag.x)*canvas.width/rect.width;offsetY=drag.offsetY+(event.clientY-drag.y)*canvas.height/rect.height;draw();});
   canvas.addEventListener('keydown',event=>{const delta={ArrowLeft:[-10,0],ArrowRight:[10,0],ArrowUp:[0,-10],ArrowDown:[0,10]}[event.key];if(delta){event.preventDefault();offsetX+=delta[0];offsetY+=delta[1];draw();}});
   canvas.addEventListener('pointerup',()=>drag=null);canvas.addEventListener('pointercancel',()=>drag=null);
   function cleanup(){URL.revokeObjectURL(url);dialog.remove();dialogOpen=false;input.setCustomValidity('');if(!accepted){if(previous){input.files=previous;prepared.add(input);}else input.value='';input.dispatchEvent(new Event('change',{bubbles:true}));}}
   dialog.addEventListener('close',cleanup,{once:true});cancel.addEventListener('click',()=>dialog.close());
   apply.addEventListener('click',()=>{apply.disabled=true;canvas.toBlob(blob=>{
    if(!blob||blob.size>5*1024*1024){apply.disabled=false;return;}
    const result=new File([blob],file.name.replace(/\.[^.]+$/,'')+'.png',{type:'image/png'}),transfer=new DataTransfer();transfer.items.add(result);input.files=transfer.files;savedFiles.set(input,transfer.files);prepared.add(input);sources.set(input,file);accepted=true;input.setCustomValidity('');dialog.close();input.dispatchEvent(new Event('change',{bubbles:true}));
   },'image/png');});
   fit();dialog.showModal();
  }catch(e){URL.revokeObjectURL(url);dialog?.remove();dialogOpen=false;input.value='';error(input,e.message);}
 }
 document.addEventListener('change',event=>{const input=event.target;if(!input.matches('input[data-logo-editor]'))return;const file=input.files?.[0];if(!file||prepared.has(input)&&file.type==='image/png'&&sources.get(input)){prepared.delete(input);return;}event.stopImmediatePropagation();edit(input,file);},true);
 document.addEventListener('gatearr:navigated',()=>document.querySelector('dialog.logo-editor[open]')?.close());
 document.addEventListener('click',event=>{const button=event.target.closest('[data-edit-logo]');if(!button)return;const input=button.closest('.upload-control')?.querySelector('input[data-logo-editor]'),file=input&&sources.get(input);if(file){event.preventDefault();edit(input,file);}});
})();
