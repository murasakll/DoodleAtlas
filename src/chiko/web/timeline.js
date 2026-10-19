// Historical frames are separate from the live map; predictions and live entities are excluded.
class MapTimeline {
 constructor({getState,getToken,onGo,getView=()=>null}){
  this.getState=getState;this.getToken=getToken;this.onGo=onGo;this.getView=getView;this.frames=[];this.world=null;this.playing=false;this.timer=null;this.poll=null;this.request=0;this.regionDirty=false;
  const el=id=>document.getElementById(id);this.el=el;
  el('openHistory').onclick=()=>{el('historyDialog').showModal();this.refresh()};
  el('closeHistory').onclick=()=>{this.stop();el('historyDialog').close()};
  el('historyDialog').addEventListener('close',()=>this.stop());
  el('historyImage').onerror=()=>{this.stop();el('historyMessage').textContent='A imagem não carregou. Atualize a lista; o registro pode ter expirado pela retenção ou cota.'};
  el('historyRefresh').onclick=()=>this.refresh();el('historyFrame').oninput=()=>{this.stop();this.show(Number(el('historyFrame').value))};
  el('historyDimension').onchange=()=>{this.regionDirty=true;this.stop();this.refresh()};
  el('historyPlay').onclick=()=>{if(this.playing){this.stop();return}if(this.frames.length<2)return;this.playing=true;el('historyPlay').textContent='Pausar';this.step()};
  el('historyCapture').onclick=()=>this.write('/api/history/capture',{dimension:Number(el('historyDimension').value)});
  for(const id of ['historyMinX','historyMinZ','historyMaxX','historyMaxZ'])el(id).oninput=()=>{this.regionDirty=true};
  el('historyUseView').onclick=()=>{
   const view=this.getView();if(!view||!Number.isFinite(view.scale)||view.scale<=0)return;
   const region={dimension:view.dimension,min_x:Math.floor((view.x-view.width/view.scale/2)/16)*16,min_z:Math.floor((view.z-view.height/view.scale/2)/16)*16,max_x:Math.ceil((view.x+view.width/view.scale/2)/16)*16,max_z:Math.ceil((view.z+view.height/view.scale/2)/16)*16};
   this.fillRegion(region);this.regionDirty=true;
   const chunks=(region.max_x-region.min_x)*(region.max_z-region.min_z)/256;
   el('historyRegionStatus').textContent=chunks+' chunks selecionados. '+(chunks>4096?'Aproxime o mapa ou reduza os limites; o máximo é 4.096.':'Clique em Guardar região principal para aplicar.');
  };
  el('historySaveRegion').onclick=()=>{
   if(['historyMinX','historyMinZ','historyMaxX','historyMaxZ'].some(id=>!el(id).value.trim())){el('historyRegionStatus').textContent='Preencha os quatro limites da região.';return;}
   const region={dimension:Number(el('historyDimension').value),min_x:Number(el('historyMinX').value),min_z:Number(el('historyMinZ').value),max_x:Number(el('historyMaxX').value),max_z:Number(el('historyMaxZ').value)};
   if(Object.values(region).some(v=>!Number.isSafeInteger(v))){el('historyRegionStatus').textContent='Preencha os limites com números inteiros.';return;}
   this.write('/api/history/settings',{settings:{primary_region:region}},()=>{this.regionDirty=false;});
  };
  el('historySettings').onsubmit=e=>{e.preventDefault();this.write('/api/history/settings',{settings:{enabled:el('historyEnabled').checked,frames_enabled:el('historyAutomatic').checked,interval_minutes:Number(el('historyInterval').value),limit_mb:Number(el('historyQuota').value),retention_days:Number(el('historyRetention').value)}})};
 }
 fillRegion(region){for(const[id,key]of [['historyMinX','min_x'],['historyMinZ','min_z'],['historyMaxX','max_x'],['historyMaxZ','max_z']])this.el(id).value=String(region[key]);this.el('historyDimension').value=String(region.dimension)}
 stop(){this.playing=false;clearTimeout(this.timer);clearTimeout(this.poll);this.el('historyPlay').textContent='Reproduzir'}
 update(state){
  if(this.world!==state.world_id){this.stop();this.world=state.world_id;this.frames=[];this.regionDirty=false;this.primaryRegion=null;this.request++;this.el('historyImage').removeAttribute?.('src');this.el('historyImage').hidden=true;if(this.el('historyDialog').open)this.refresh()}
  const info=state.history,available=!!info?.available,host=!!this.getToken();
  this.el('openHistory').disabled=!available;
  this.el('openHistory').textContent=info?.frame_count?'▷ '+info.frame_count+' páginas':'▷ Histórico';
  this.el('historyCapture').disabled=!available||!info?.settings?.primary_region||!!info?.running||!(host||state.shared_waypoints?.pin_writes);
  this.el('historySaveRegion').disabled=!available||!host;
  for(const id of ['historyEnabled','historyAutomatic','historyInterval','historyQuota','historyRetention','historySave'])this.el(id).disabled=!available||!host;
  this.el('historySummary').textContent=available?(info.running?'Preparando quadro em baixa resolução…':info.error?'Falha no quadro: '+info.error:info.events+' mudanças registradas · '+info.frame_count+' quadros')+' · '+(info.bytes/1048576).toFixed(1)+' MiB no banco e journal.':'Histórico requer armazenamento por mundo.';
  if(this.el('historyDialog').open&&this.lastLatest!==info?.latest){this.lastLatest=info?.latest;this.refresh()}
 }
 async write(url,body,onSuccess){
  const state=this.getState();if(!state)return;const world=state.world_id;
  try{const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-Host-Token':this.getToken()||''},body:JSON.stringify({...body,world_id:world})});if(!r.ok)throw Error(await r.text());if(this.world!==world)return;onSuccess?.();this.el('historyMessage').textContent=url.endsWith('capture')?'Quadro solicitado. A lista será atualizada ao terminar.':'Preferências salvas neste mundo.';await this.refresh();if(url.endsWith('capture'))this.waitForFrame()}
  catch(error){if(this.world===world)this.el('historyMessage').textContent=error.message}
 }
 waitForFrame(){clearTimeout(this.poll);this.poll=setTimeout(async()=>{if(!this.el('historyDialog').open)return;await this.refresh();if(this.getState()?.history?.running)this.waitForFrame()},2000)}
 async refresh(){
  const world=this.getState()?.world_id,request=++this.request;if(!world)return;
  try{
   const response=await fetch('/api/history');if(!response.ok)throw Error('Histórico: HTTP '+response.status);const data=await response.json();if(request!==this.request||world!==this.getState()?.world_id||data.world_id&&data.world_id!==world)return;
   const options=data.settings||{};
   this.primaryRegion=options.primary_region||null;
   if(this.primaryRegion&&!this.regionDirty)this.fillRegion(this.primaryRegion);
   if(!this.regionDirty)this.el('historyRegionStatus').textContent=this.primaryRegion?'Região principal salva · X '+this.primaryRegion.min_x+' a '+this.primaryRegion.max_x+' · Z '+this.primaryRegion.min_z+' a '+this.primaryRegion.max_z:'Escolha uma região. O registro automático fica parado até você guardar a área.';
   for(const[id,key]of [['historyEnabled','enabled'],['historyAutomatic','frames_enabled']])if(document.activeElement!==this.el(id))this.el(id).checked=!!options[key];
   for(const[id,key]of [['historyInterval','interval_minutes'],['historyQuota','limit_mb'],['historyRetention','retention_days']])if(document.activeElement!==this.el(id)&&options[key]!=null)this.el(id).value=String(options[key]);
   const selected=this.frames[Number(this.el('historyFrame').value)]?.id;
   this.frames=(data.frames||[]).filter(f=>f.dimension===Number(this.el('historyDimension').value)&&(!this.primaryRegion||['min_x','min_z','max_x','max_z'].every(k=>f[k]===this.primaryRegion[k]))).reverse();
   this.el('historyFrame').max=String(Math.max(0,this.frames.length-1));this.el('historyFrame').disabled=!this.frames.length;
   this.el('historyPlay').disabled=this.frames.length<2;
   this.show(Math.max(0,selected?this.frames.findIndex(f=>f.id===selected):this.frames.length-1));
   const list=this.el('historyChanges');list.replaceChildren();
   for(const event of data.recent||[]){const row=document.createElement('div'),b=document.createElement('button'),locate=document.createElement('button');b.type=locate.type='button';b.className=locate.className='button';b.textContent=new Date(event.at*1000).toLocaleTimeString()+' · '+(event.origin==='save'?'Save':'Captura')+' · chunk '+event.x+', '+event.z;b.onclick=()=>this.showChange(event);locate.textContent='Localizar';locate.onclick=()=>{this.stop();this.el('historyDialog').close();this.onGo({x:event.x*16+8,z:event.z*16+8,dimension:event.dimension,scale:2})};row.append(b,locate);list.append(row)}
  }catch(error){if(world===this.getState()?.world_id)this.el('historyMessage').textContent=error.message}
 }
 show(index){
  const frame=this.frames[index],image=this.el('historyImage');this.el('historyFrame').value=String(index);image.hidden=!frame;this.el('historyDownload').hidden=!frame;
  if(!frame){image.removeAttribute?.('src');this.el('historyCaption').textContent='Ainda não há quadros nesta dimensão. Use “Registrar quadro agora” ou aguarde o intervalo automático.';return}
  const url='/api/history/frames/'+frame.id+'.webp?world_id='+encodeURIComponent(this.world);
  image.className='history-image';image.src=url;this.el('historyDownload').href=url;this.el('historyDownload').download='mapa-'+this.world.slice(0,12)+'-'+frame.id+'.webp';
  this.el('historyCaption').textContent=new Date(frame.at*1000).toLocaleString()+' · '+frame.width+' × '+frame.height+' px · X '+frame.min_x+' a '+frame.max_x+' · Z '+frame.min_z+' a '+frame.max_z;
 }
 showChange(event){
  this.stop();const url='/api/history/changes/'+event.id+'.webp?world_id='+encodeURIComponent(this.world),image=this.el('historyImage');
  image.className='history-image history-image--chunk';image.hidden=false;image.src=url;this.el('historyDownload').hidden=false;this.el('historyDownload').href=url;this.el('historyDownload').download='chunk-'+event.x+'-'+event.z+'-'+event.id+'.webp';
  this.el('historyCaption').textContent='Versão observada do chunk '+event.x+', '+event.z+' · dimensão '+event.dimension+' · '+new Date(event.at*1000).toLocaleString()+' · '+(event.origin==='save'?'save':'captura')+' · 16 × 16 blocos. Não altera o mundo nem o mapa atual.';
 }
 step(){if(!this.playing||document.hidden){this.stop();return}const i=Number(this.el('historyFrame').value);this.show((i+1)%this.frames.length);this.timer=setTimeout(()=>this.step(),1500)}
}

class TrailBuffer {
 constructor(){this.points=[];this.world=null;this.last=new Map()}
 clear(){this.points=[];this.last.clear()}
 update(state,enabled,now=Date.now()/1000){
  let changed=this.world!==state.world_id;
  if(changed){this.clear();this.world=state.world_id}
  if(!enabled){changed||=this.points.length>0;this.clear();return changed}
  for(const p of state.players||[]){const old=this.last.get(p.id);if(!Number.isFinite(p.x)||!Number.isFinite(p.z))continue;if(!old||old.dimension!==p.dimension||Math.hypot(old.x-p.x,old.z-p.z)>=2){const point={id:p.id,x:p.x,z:p.z,dimension:p.dimension,at:now,break:!!old&&(old.dimension!==p.dimension||Math.hypot(old.x-p.x,old.z-p.z)>128)};this.points.push(point);this.last.set(p.id,point);changed=true}}
  const before=this.points.length;this.points=this.points.filter(p=>now-p.at<=1800).slice(-1200);for(const[id,p]of this.last)if(now-p.at>1800)this.last.delete(id);return changed||before!==this.points.length;
 }
}
