(() => {
 'use strict';
 document.body.classList.add('caderno-ui');
 const byId = id => document.getElementById(id);
 const layersContent=byId('layersPanel').querySelector('.panel-content');
 function mapSection(title){
   const section=document.createElement('section');section.className='map-option-group';
   const heading=document.createElement('h3');heading.textContent=title;section.append(heading);return section;
 }
 const worldField=byId('worldSelect').closest('label');worldField.classList.add('world-switch-field');
 const worldTitle=byId('world');worldTitle.classList.add('world-title-source');
 worldTitle.before(worldField);
 const worldHelp=byId('hostHint');worldHelp.hidden=true;worldField.append(worldHelp);
 byId('worldSelect').setAttribute('aria-describedby','hostHint');
 byId('dimension').closest('label').hidden=true;
 const appearanceGroup=mapSection('Seu jeito de ver o mapa');
 appearanceGroup.append(byId('viewMode').closest('label'),byId('themeMode').closest('label'));
 const informationGroup=mapSection('Informações no mapa');
 informationGroup.append(byId('showGrid').closest('label'),byId('observedPoints').closest('label'),byId('observedPointsStatus'));
 const help=document.createElement('details');help.className='nested-panel map-credits';
 const helpSummary=document.createElement('summary');helpSummary.textContent='Créditos';help.append(helpSummary);
 const credits=byId('artCredits');
 if(credits)help.append(credits);
 appearanceGroup.append(byId('themeStatus'),help);
 const advanced=[...layersContent.children];
 function foldOptions(title,nodes,className=''){
   const details=document.createElement('details'),summary=document.createElement('summary');
   details.className='nested-panel quiet-options '+className;summary.textContent=title;details.append(summary,...nodes.filter(Boolean));return details;
 }
 informationGroup.querySelector('h3').remove();
 layersContent.replaceChildren(appearanceGroup,foldOptions('O que aparece no mapa',[informationGroup]),...advanced);
 const choiceGroups=[];
 function visualChoices(id,title,options){
   const select=byId(id),source=select.closest('label'),group=document.createElement('fieldset');group.className='map-choices';
   const legend=document.createElement('legend');legend.textContent=title;group.append(legend);
   const buttons=[];
   for(const [value,name,description] of options){
     const button=document.createElement('button');button.type='button';button.className='map-choice';
     const label=document.createElement('strong');label.textContent=name;button.append(label);
     if(description){const small=document.createElement('small');small.textContent=description;button.append(small);}
     button.onclick=()=>{select.value=value;select.dispatchEvent(new Event('change',{bubbles:true}));syncMapChoices();};
     buttons.push([button,value]);group.append(button);
   }
 source.classList.add('preview-choice-source');source.hidden=true;source.after(group);choiceGroups.push({select,buttons});
 }
 function syncMapChoices(){for(const {select,buttons} of choiceGroups)for(const [button,value] of buttons)button.setAttribute('aria-pressed',String(select.value===value));}
 visualChoices('viewMode','Estilo do terreno',[['cartographer','✎ Atlas','Traços e símbolos'],['plain','▦ Minecraft','Cores naturais']]);
 visualChoices('themeMode','Papel da interface',[['system','◐ Sistema',''],['light','☼ Claro',''],['dark','☾ Escuro','']]);
 const appearanceObserver=new MutationObserver(syncMapChoices);appearanceObserver.observe(document.body,{attributes:true,attributeFilter:['data-theme','data-appearance']});
 byId('viewMode').addEventListener('change',syncMapChoices);byId('themeMode').addEventListener('change',syncMapChoices);syncMapChoices();
 const portraitHelp=[...byId('playersPanel').querySelectorAll('p.note')].find(p=>p.textContent.startsWith('PNG de skin'));
 if(portraitHelp){const tips=document.createElement('details'),summary=document.createElement('summary');tips.className='nested-panel';summary.textContent='Como enviar uma skin';portraitHelp.before(tips);tips.append(summary,portraitHelp);}
 const chosenColorFields=['editColor','editBackgroundColor','portraitSkin','portraitHair','portraitAccent'];
 for(const id of chosenColorFields)byId(id).closest('label')?.classList.add('paper-color-field');
 // Keep original controls and listeners; only change what is visible first.
 const waypointContent=byId('waypointsPanel').querySelector('.panel-content');
 const newPlace=foldOptions('+ Anotar um lugar',[byId('waypointForm')],'new-place');
 waypointContent.insertBefore(newPlace,byId('waypoints'));
 const placesEmpty=document.createElement('p');placesEmpty.className='note empty-page';placesEmpty.textContent='Seus lugares aparecem aqui. Anote uma base, uma mina ou um caminho para voltar.';
 byId('waypoints').after(placesEmpty);
 function syncPlacesEmpty(){placesEmpty.hidden=byId('waypoints').childElementCount>0;}
 new MutationObserver(syncPlacesEmpty).observe(byId('waypoints'),{childList:true});syncPlacesEmpty();
 byId('markSelection').addEventListener('click',()=>{newPlace.open=true;},{capture:true});
 const editorCommon=byId('editorCommon'),editorActions=editorCommon.querySelector('.editor-actions');
 const technicalControls=[byId('editVisible').closest('label'),byId('editGrid').closest('details'),byId('editReload').closest('details')];
 const advancedDrawing=foldOptions('Mais opções de desenho',technicalControls);
 advancedDrawing.append(byId('editJSON'));
 editorCommon.replaceChildren(byId('editChosenTool'),byId('editEnabled').closest('label'),editorActions,byId('editCount'),byId('editStatus'),advancedDrawing);
 const editorBody=byId('editorPanel').querySelector('.panel-content');
 const editorIntro=editorBody.querySelector('p.note');editorIntro.after(byId('editorMapSlot'));
 const buildingBody=byId('buildingPanel').querySelector('.panel-content');
 byId('editBuilding').closest('label').after(byId('editorBuildingSlot'));
 byId('editBackgroundVisible').closest('details').open=false;
 const settingsBody=byId('settingsPanel').querySelector('.panel-content');
 settingsBody.append(foldOptions('Diagnóstico e armazenamento',[byId('renderQueue'),byId('storageStatus')]));
 editorBody.classList.add('workflow-sheet');buildingBody.classList.add('workflow-sheet');
 // The scroll region has explicit bounds, so details' anonymous box cannot clip it.
 const scrollSheets=[];
 for(const id of ['historyDialog','exportDialog']){
   const dialog=byId(id),body=document.createElement('div');body.className='dialog-scroll-body';
   body.append(...dialog.childNodes);dialog.append(body);
 }
 let scrollFrame=null;
 function queueScrollMeasure(){if(scrollFrame===null)scrollFrame=requestAnimationFrame(measureScrollSheets);}
 function measureScrollSheets(){
   scrollFrame=null;
   for(const item of scrollSheets){
     const {host,region,rail,thumb,heading}=item;
     if(heading){const value=heading.offsetHeight+'px';if(host.style.getPropertyValue('--panel-heading-height')!==value)host.style.setProperty('--panel-heading-height',value);}
     const viewport=region.clientHeight,total=region.scrollHeight,overflow=Math.max(0,total-viewport);
     rail.hidden=viewport<=0||overflow<=1;
     rail.setAttribute('aria-valuemax',String(Math.round(overflow)));
     rail.setAttribute('aria-valuenow',String(Math.round(Math.min(overflow,region.scrollTop))));
     rail.setAttribute('aria-valuetext',overflow?Math.round(region.scrollTop/overflow*100)+'% da folha':'Folha inteira visível');
     if(rail.hidden)continue;
     const track=rail.clientHeight;
     item.thumbHeight=Math.min(track,Math.max(28,track*viewport/total));
     item.thumbOffset=(track-item.thumbHeight)*Math.min(1,Math.max(0,region.scrollTop/overflow));
     thumb.style.height=item.thumbHeight+'px';thumb.style.transform='translateY('+item.thumbOffset+'px)';
   }
 }
 const sheetResize=new ResizeObserver(queueScrollMeasure);
 const sheetChanges=new MutationObserver(queueScrollMeasure);
 for(const host of document.querySelectorAll('.floating-panel,#historyDialog,#exportDialog')){
   const region=host.querySelector('.panel-content,.dialog-scroll-body');if(!region)continue;
   const heading=host.matches('details')?host.querySelector('summary'):null;
   if(!region.id)region.id=host.id+'-scroll';
   region.tabIndex=0;region.setAttribute('role','region');region.setAttribute('aria-label','Conteúdo de '+(heading?.textContent.trim()||host.querySelector('h2')?.textContent||'painel'));
   const rail=document.createElement('div'),thumb=document.createElement('span');
   rail.className='sketch-scroll-rail';rail.hidden=true;rail.tabIndex=0;
   rail.setAttribute('role','scrollbar');rail.setAttribute('aria-label','Rolar opções do painel');rail.setAttribute('aria-controls',region.id);rail.setAttribute('aria-orientation','vertical');rail.setAttribute('aria-valuemin','0');rail.setAttribute('aria-valuemax','0');rail.setAttribute('aria-valuenow','0');
   thumb.className='sketch-scroll-thumb';thumb.setAttribute('aria-hidden','true');rail.append(thumb);host.append(rail);
   const item={host,region,rail,thumb,heading,thumbHeight:28,thumbOffset:0,drag:null};scrollSheets.push(item);
   region.classList.add('sketch-scroll-content');
   region.addEventListener('scroll',queueScrollMeasure,{passive:true});host.addEventListener('toggle',queueScrollMeasure);region.addEventListener('load',queueScrollMeasure,true);
   sheetResize.observe(region);if(heading)sheetResize.observe(heading);
   sheetChanges.observe(region,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['open','hidden']});
   if(host.matches('dialog'))sheetChanges.observe(host,{attributes:true,attributeFilter:['open']});
   function seek(clientY,offset){
     const travel=rail.clientHeight-item.thumbHeight;
     if(travel<=0)return;
     const ratio=Math.max(0,Math.min(1,(clientY-rail.getBoundingClientRect().top-offset)/travel));
     region.scrollTop=ratio*Math.max(0,region.scrollHeight-region.clientHeight);queueScrollMeasure();
   }
   rail.onpointerdown=event=>{
     if(!event.isPrimary||event.button!==0)return;
     event.preventDefault();rail.focus();
     const y=event.clientY-rail.getBoundingClientRect().top;
     const offset=y>=item.thumbOffset&&y<=item.thumbOffset+item.thumbHeight?y-item.thumbOffset:item.thumbHeight/2;
     item.drag={id:event.pointerId,offset};rail.setPointerCapture(event.pointerId);seek(event.clientY,offset);
   };
   rail.onpointermove=event=>{if(item.drag?.id===event.pointerId)seek(event.clientY,item.drag.offset);};
   const finish=event=>{if(item.drag?.id!==event.pointerId)return;item.drag=null;if(rail.hasPointerCapture(event.pointerId))rail.releasePointerCapture(event.pointerId);};
   rail.onpointerup=finish;rail.onpointercancel=finish;rail.onlostpointercapture=finish;
   rail.onkeydown=event=>{
     const delta={ArrowDown:40,ArrowUp:-40,PageDown:region.clientHeight*.85,PageUp:-region.clientHeight*.85}[event.key];
     if(delta!==undefined)region.scrollTop+=delta;
     else if(event.key==='Home')region.scrollTop=0;
     else if(event.key==='End')region.scrollTop=region.scrollHeight;
     else return;
     event.preventDefault();queueScrollMeasure();
   };
   rail.addEventListener('wheel',event=>{
     event.preventDefault();region.scrollTop+=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?region.clientHeight:1);queueScrollMeasure();
   },{passive:false});
 }
 window.addEventListener('resize',queueScrollMeasure);
 document.fonts?.ready.then(queueScrollMeasure);
 queueScrollMeasure();
 const existingControls = new Map([...document.querySelectorAll('.tool-rail [data-panel]')].map(button=>[button.dataset.panel,button]));
 const tabs=document.createElement('nav');tabs.className='book-tabs paper';tabs.setAttribute('aria-label','Abas do caderno');
 const entries=[['layersPanel','▱ Mapa'],['playersPanel','☷ Pessoas'],['waypointsPanel','⚑ Lugares'],['editorPanel','✎ Desenho'],['buildingPanel','⌂ Construir'],['biomesPanel','◇ Biomas'],['settingsPanel','⚙ Ajustes']];
 const panelButtons=[];
 function syncPanels(){for(const button of panelButtons)button.setAttribute('aria-expanded',String(byId(button.dataset.bookPanel).open));}
 for(const [id,title] of entries){
   const button=document.createElement('button');button.type='button';button.textContent=title;button.dataset.bookPanel=id;
   button.setAttribute('aria-controls',id);button.setAttribute('aria-expanded',String(byId(id).open));
   button.onclick=()=>{
     const opening=!byId(id).open;
     if(opening)for(const [other] of entries)if(other!==id)byId(other).open=false;
     const original=existingControls.get(id);
     if(original)original.click();else byId(id).open=opening;
     syncPanels();
   };
   byId(id).addEventListener('toggle',syncPanels);panelButtons.push(button);tabs.append(button);
 }
 const historyButton=document.createElement('button');historyButton.type='button';historyButton.textContent='◷ Histórico';historyButton.onclick=()=>byId('openHistory').click();tabs.append(historyButton);
 const concentration=document.createElement('button');concentration.type='button';concentration.textContent='□ Foco';concentration.setAttribute('aria-pressed','false');
 function setFocus(on){
   if(on){byId('editorPanel').open=false;byId('buildingPanel').open=false;}
   document.body.classList.toggle('focus-map',on);concentration.setAttribute('aria-pressed',String(on));concentration.firstChild.nodeValue=on?'▣ Voltar':'□ Foco';
 }
 concentration.onclick=()=>setFocus(!document.body.classList.contains('focus-map'));tabs.append(concentration);tabs.append(document.querySelector('.map-footer'));document.body.append(tabs);
 document.addEventListener('keydown',event=>{if(event.key==='Escape')setFocus(false);});
 const settings=document.createElement('details');settings.className='preview-settings paper';
 settings.innerHTML='<summary>Traço e sons</summary><div class="preview-options"><button id="preview-motion" type="button" aria-pressed="true">Pausar traço</button><button id="sound-toggle" type="button" aria-pressed="false">♪ Ativar sons</button><label>Volume <input id="sound-volume" type="range" min="0" max="100" value="25"><output id="sound-level">25%</output></label></div><p id="sound-status" class="preview-status" role="status">Sons desligados.</p>';
 document.body.append(settings);
 const slot=byId('chiko-slot');slot.replaceChildren();
 const mascot=document.createElement('img');mascot.src='/assets/chiko-pixel-v1.png';mascot.className='chiko-pixel';mascot.alt='Chiko em pixel art';
 const context=document.createElement('span');context.className='chiko-context';context.setAttribute('aria-hidden','true');slot.append(mascot,context);
 const brand=document.querySelector('.atlas-brand');
 brand.textContent='▱ DoodleAtlas';
 const chikoSummary=byId('chikoPanel').querySelector('summary');
 const stateLabel=byId('chiko-state-name');stateLabel.classList.add('chiko-state-source');
 const summaryPortrait=document.createElement('img');summaryPortrait.src=mascot.src;summaryPortrait.alt='';summaryPortrait.className='chiko-summary-portrait';
 const summaryCopy=document.createElement('span');summaryCopy.className='chiko-summary-copy';
 const summaryName=document.createElement('strong');summaryName.textContent='Chiko';
 const summaryState=document.createElement('small');summaryState.className='chiko-summary-state';
 summaryCopy.append(summaryName,summaryState);
 const summaryHint=document.createElement('span');summaryHint.className='chiko-summary-hint';summaryHint.setAttribute('aria-hidden','true');summaryHint.textContent='+';
 chikoSummary.replaceChildren(summaryPortrait,summaryCopy,stateLabel,summaryHint);
 function syncChikoDisclosure(){summaryHint.textContent=byId('chikoPanel').open?'−':'+';byId('chiko-bubble').setAttribute('aria-live',byId('chikoPanel').open?'polite':'off');}
 byId('chikoPanel').addEventListener('toggle',syncChikoDisclosure);syncChikoDisclosure();
 const arrival=document.createElement('div');arrival.className='live-arrival';arrival.setAttribute('aria-hidden','true');document.body.append(arrival);
 let previousDimension=null,captionTimer=null,captionHoldUntil=0,lastDiscoveryAt=-Infinity;
 function updateCaption(name){
   clearTimeout(captionTimer);
   const now=Date.now(),captions={lendo:'Consultando o atlas',folheando:'Preparando a página',animado:'Uma nova descoberta',dormindo:'Aguardando companhia',confuso:'Vamos conferir os dados'};
   if(name==='confuso'){captionHoldUntil=0;summaryState.textContent=captions.confuso;return;}
   if(name==='animado'&&now-lastDiscoveryAt>=30000){lastDiscoveryAt=now;captionHoldUntil=now+4000;summaryState.textContent=captions.animado;return;}
   if(name==='animado')name='lendo';
   const caption=captions[name]||'Seu companheiro de viagem';
   if(!summaryState.textContent){summaryState.textContent=caption;return;}
   captionTimer=setTimeout(()=>{if(summaryState.textContent!==caption)summaryState.textContent=caption;},Math.max(600,captionHoldUntil-now));
 }
 function updateContext(){
   const dimension=byId('dimension').value, name=byId('chiko-state-name').textContent;
   updateCaption(name);
   slot.setAttribute('aria-label','Chiko em pixel art · '+name);
   context.textContent=name==='confuso'?'?':dimension==='1'?'♨':dimension==='2'?'✧':name==='animado'?'⚑':name==='folheando'?'…':'✎';
   if(previousDimension!==null&&previousDimension!==dimension){
     arrival.style.setProperty('--event-ink',dimension==='1'?'#f5be88':dimension==='2'?'#ddd5f2':'#b5e7ef');
     arrival.classList.remove('entering');void arrival.offsetWidth;arrival.classList.add('entering');
   }
   previousDimension=dimension;
 }
 const contextObserver=new MutationObserver(updateContext);
 contextObserver.observe(byId('chiko-state-name'),{childList:true,characterData:true,subtree:true});
 for(const button of document.querySelectorAll('[data-dimension]'))contextObserver.observe(button,{attributes:true,attributeFilter:['aria-pressed']});
 byId('dimension').addEventListener('change',updateContext);updateContext();
 const motionPreference=matchMedia('(prefers-reduced-motion: reduce)');
 let motionEnabled=true;
 const borders=new Map();
 function syncMotion(){
   const enabled=motionEnabled&&!motionPreference.matches&&!document.hidden;
   document.body.classList.toggle('motion-on',enabled);
   byId('preview-motion').setAttribute('aria-pressed',String(motionEnabled));
   byId('preview-motion').firstChild.nodeValue=motionPreference.matches?'Traço parado pelo sistema':motionEnabled?'Pausar traço':'Animar traço';
   if(byId('preview-motion').disabled!==motionPreference.matches)byId('preview-motion').disabled=motionPreference.matches;
   for(const [host,border] of borders){if(enabled&&border.visible&&!host.disabled)border.svg.unpauseAnimations();else border.svg.pauseAnimations();}
 }
 byId('preview-motion').onclick=()=>{motionEnabled=!motionEnabled;syncMotion();};
 const ns='http://www.w3.org/2000/svg';
 function outline(w,h,v){
   const [a,b,c]=[[-1,.7,-.5],[.8,-1,.6],[-.5,1,-.8]][v];
   return `M2 ${3+a}L${w*.38} ${3+b}L${w-2} ${3+c} M${w-3+a} 1L${w-3+b} ${h*.55}L${w-3+c} ${h-1} M${w-1} ${h-3+a}L${w*.55} ${h-3+c}L1 ${h-3+b} M${3+c} ${h-1}L${3+a} ${h*.4}L${3+b} 1`;
 }
 const visibility=new IntersectionObserver(entries=>{for(const entry of entries){const item=borders.get(entry.target);if(item)item.visible=entry.isIntersecting;}syncMotion();});
 const resize=new ResizeObserver(entries=>{
   for(const entry of entries){
     const host=entry.target,item=borders.get(host),w=host.clientWidth,h=host.clientHeight;if(!item||!w||!h)continue;
     item.svg.style.left=item.svg.style.top='0px';item.svg.style.width=w+'px';item.svg.style.height=h+'px';item.svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
     const frames=[0,1,2,0].map(v=>outline(w,h,v));item.path.setAttribute('d',frames[0]);item.animation.setAttribute('values',frames.join(';'));item.animation.beginElement();
   }
   syncMotion();
 });
 function attachSketch(host){
   const existing=borders.get(host);
   if(existing){if(existing.svg.parentNode!==host)host.append(existing.svg);return;}
   if(host.matches('button')&&getComputedStyle(host).position==='static')host.classList.add('sketch-button-static');
   const i=borders.size;
   const svg=document.createElementNS(ns,'svg');svg.classList.add('live-sketch');svg.setAttribute('aria-hidden','true');svg.setAttribute('focusable','false');
   const path=document.createElementNS(ns,'path'),animation=document.createElementNS(ns,'animate');
   for(const [key,value] of Object.entries({attributeName:'d',begin:'indefinite',dur:(2.4+i%3*.2)+'s',repeatCount:'indefinite',calcMode:'discrete',keyTimes:'0;.28;.68;1'}))animation.setAttribute(key,value);
   path.append(animation);svg.append(path);host.append(svg);host.classList.add('live-sketch-ready');
   borders.set(host,{svg,path,animation,visible:false});resize.observe(host);visibility.observe(host);
 }
 document.querySelectorAll('.atlas-title,.dimension-tabs,.floating-panel>summary,.chiko-corner,button').forEach(attachSketch);
 // Player lists and editor palettes rebuild their buttons; labels can replace the SVG too.
 const buttonObserver=new MutationObserver(records=>{
   for(const record of records){
     if(record.target.nodeType===1){const button=record.target.closest('button');if(button&&button.isConnected)attachSketch(button);}
     for(const node of record.addedNodes||[]){
       if(node.nodeType!==1||!node.isConnected||node.namespaceURI===ns)continue;
       if(node.matches('button'))attachSketch(node);
       node.querySelectorAll('button').forEach(attachSketch);
     }
   }
   for(const [host,item] of borders)if(!host.isConnected){resize.unobserve(host);visibility.unobserve(host);item.svg.pauseAnimations();borders.delete(host);}
   syncMotion();
 });
 buttonObserver.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled']});
 motionPreference.addEventListener('change',syncMotion);document.addEventListener('visibilitychange',syncMotion);syncMotion();
 let soundContext, soundMaster, paperNoise;
 let soundsEnabled = false, lastSoundAt = -Infinity;
 const soundToggle = document.getElementById('sound-toggle');
 const soundVolume = document.getElementById('sound-volume');
 const soundStatus = document.getElementById('sound-status');
 function setSoundLevel() {
   const volume = Number(soundVolume.value) / 100;
   document.getElementById('sound-level').textContent = Math.round(volume * 100) + '%';
   if (soundMaster) soundMaster.gain.setTargetAtTime(soundsEnabled ? volume * 2 : 0, soundContext.currentTime, .025);
 }
 function syncSoundButton() {
   soundToggle.setAttribute('aria-pressed',String(soundsEnabled));
   soundToggle.firstChild.nodeValue = soundsEnabled ? '♪ Silenciar sons' : '♪ Ativar sons';
 }
 async function enableSound() {
   const AudioEngine = window.AudioContext || window.webkitAudioContext;
   if (!AudioEngine) { soundStatus.textContent = 'Este navegador não oferece áudio sintetizado.'; return false; }
   try {
     if (!soundContext) {
       soundContext = new AudioEngine();
       soundMaster = soundContext.createGain(); soundMaster.gain.value = 0;
       const limiter = soundContext.createDynamicsCompressor();
       limiter.threshold.value = -6; limiter.knee.value = 0; limiter.ratio.value = 20;
       limiter.attack.value = .003; limiter.release.value = .08;
       soundMaster.connect(limiter); limiter.connect(soundContext.destination);
       paperNoise = soundContext.createBuffer(1,soundContext.sampleRate,soundContext.sampleRate);
       const samples = paperNoise.getChannelData(0);
       for (let i=0;i<samples.length;i++) samples[i] = Math.random()*2-1;
     }
     await soundContext.resume();
     if (soundContext.state !== 'running') throw new Error('Audio suspended');
     soundsEnabled = true; syncSoundButton(); setSoundLevel();
     soundStatus.textContent = 'Sons ativos · apenas nas suas ações.';
     return true;
   } catch {
     soundsEnabled = false; syncSoundButton(); setSoundLevel();
     soundStatus.textContent = 'O navegador bloqueou o áudio. Tente ativar novamente.';
     return false;
   }
 }
 function playSound(kind) {
   if (!soundsEnabled || !soundContext || soundContext.state !== 'running' || document.hidden) return;
   const now = soundContext.currentTime;
   if (now-lastSoundAt < .09) return;
   lastSoundAt = now;
   function tone(frequency, endFrequency, duration, delay=0, type='sine', level=.2) {
     const voice = soundContext.createOscillator(), envelope = soundContext.createGain();
     const at = now + delay;
     voice.type = type; voice.frequency.setValueAtTime(frequency,at);
     voice.frequency.exponentialRampToValueAtTime(endFrequency,at+duration);
     envelope.gain.setValueAtTime(.0001,at);
     envelope.gain.exponentialRampToValueAtTime(level,at+.008);
     envelope.gain.exponentialRampToValueAtTime(.0001,at+duration);
     voice.connect(envelope); envelope.connect(soundMaster);
     voice.onended = () => { voice.disconnect(); envelope.disconnect(); };
     voice.start(at); voice.stop(at+duration+.02);
   }
   function scratch(duration, frequency, delay=0, level=.2) {
     const voice = soundContext.createBufferSource(), filter = soundContext.createBiquadFilter(), envelope = soundContext.createGain();
     const at = now+delay;
     voice.buffer = paperNoise; filter.type = 'bandpass'; filter.frequency.value = frequency; filter.Q.value = .7;
     envelope.gain.setValueAtTime(.0001,at);
     envelope.gain.exponentialRampToValueAtTime(Math.min(level * 1.8,.8),at+.008);
     envelope.gain.exponentialRampToValueAtTime(.0001,at+duration);
     voice.connect(filter); filter.connect(envelope); envelope.connect(soundMaster);
     voice.onended = () => { voice.disconnect(); filter.disconnect(); envelope.disconnect(); };
     voice.start(at,Math.random()*.4); voice.stop(at+duration+.02);
   }
   switch(kind) {
     case 'stamp': tone(140,48,.12,0,'triangle',.35); scratch(.055,900,0,.35); break;
     case 'paper': scratch(.18,1500); scratch(.12,2400,.1,.12); break;
     case 'nether': tone(180,65,.38,0,'triangle'); scratch(.22,460,.05,.18); break;
     case 'end': tone(740,735,.36); tone(1110,1100,.3,.09,'sine',.12); break;
     case 'sleep': scratch(.22,800,0,.12); tone(330,220,.4,.05,'sine',.1); break;
     case 'underground': scratch(.08,700); tone(190,170,.18,.08,'triangle',.1); break;
     case 'discovery': tone(523,523,.18); tone(784,784,.28,.13); break;
     case 'lost': tone(294,262,.16,0,'sine',.12); tone(220,196,.2,.16,'sine',.1); break;
     default: scratch(.065,2300,0,.16); scratch(.04,3100,.07,.1);
   }
 }
 soundToggle.onclick = async () => {
   if (soundsEnabled) {
     soundsEnabled = false; syncSoundButton(); setSoundLevel();
     soundStatus.textContent = 'Sons desligados.';
   } else if (await enableSound()) playSound('paper');
 };
 soundVolume.oninput = setSoundLevel;
 document.addEventListener('click',event => {
   const button = event.target.closest('button');
   if (!button || button.disabled || button === soundToggle) return;
   if (button.dataset.sound && !soundsEnabled) {
     soundStatus.textContent = 'Clique em “Ativar sons” primeiro.'; return;
   }
   const actionSounds = {save:'stamp',pin:'discovery',follow:'pencil',export:'paper',replay:'paper'};
   const dimensionSound = {0:'paper',1:'nether',2:'end'}[button.dataset.dimension];
   const kind = button.dataset.sound || button.dataset.event || dimensionSound || actionSounds[button.dataset.action] || 'pencil';
   playSound(kind === 'surface' ? 'paper' : kind);
 });
 document.addEventListener('visibilitychange',() => {
   if (document.hidden && soundMaster) soundMaster.gain.setTargetAtTime(0,soundContext.currentTime,.015);
   else setSoundLevel();
 });

})();
