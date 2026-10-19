'use strict';
// App orchestration: UI, SSE and state. Camera/drawing and tile URLs are separate.
const $=id=>document.getElementById(id);
const systemTheme=window.matchMedia?.('(prefers-color-scheme: dark)');
function readThemePreference(){try{const value=localStorage.getItem('livemap-theme');return ['light','dark'].includes(value)?value:'system'}catch{return 'system'}}
let themePreference=readThemePreference();
function applyTheme(){const dark=themePreference==='dark'||(themePreference==='system'&&!!systemTheme?.matches);document.body.dataset.theme=dark?'dark':'light';$('themeMode').value=themePreference;map.setStyle({dark})}
const dimName=d=>['Overworld','Nether','End'][d]||String(d);
let state=null,identity=null,hostToken=null,stream=null,fitted=false,waypoints=[],sharedWaypoints=[],waypointSignature='',waypointBusy=false,selected=null,waypointTarget=null,uiError='',playerSignature='',wasFresh=false,lastKnownCount=0,happyUntil=0;
let coverage=null,connectionLost=false,restoringPrefs=false,preferences={},pendingPreference=null,preferenceTimer=null,preferenceSignature='';
let browserTileSignature='';
const preferenceDefaults={viewMode:'cartographer',showGrid:false,observedPoints:true,showTrail:false,showSeed:false,seedY:'64',seedOpacity:'0.32',seedSmooth:true,tilePixels:'256',tileCache:'16',tileDownloads:'4',animals:true,hostiles:true,others:true,aquatic:false,smooth:false,entityFilter:'',exaggeration:'1.5',light:'0.8',packPreset:'4',packRate:'1',packColumns:'4',packRevisit:'300'};
function validCamera(c){return c&&[c.x,c.z,c.scale,c.dimension].every(Number.isFinite)&&[0,1,2].includes(c.dimension)&&c.scale>=.04&&c.scale<=32}
function flushPreferences(){if(preferenceTimer)clearTimeout(preferenceTimer);preferenceTimer=null;if(!pendingPreference)return;const p=pendingPreference;pendingPreference=null;try{localStorage.setItem('livemap-view-'+p.world,JSON.stringify(p.value));$('preferenceStatus').textContent='Câmera e aparência guardadas neste navegador, para este mundo.'}catch{$('preferenceStatus').textContent='Não foi possível guardar as preferências neste navegador.'}}
function queuePreferences(){
 if(!state||!fitted||restoringPrefs)return;
 const controls={};for(const[id,defaultValue]of Object.entries(preferenceDefaults))controls[id]=typeof defaultValue==='boolean'?$(id).checked:$(id).value;
 const value={version:1,camera:{...map.camera},controls,panels:panels.filter(p=>p.open).map(p=>p.id)},signature=state.world_id+JSON.stringify(value);
 if(signature===preferenceSignature)return;preferenceSignature=signature;pendingPreference={world:state.world_id,value};if(preferenceTimer)clearTimeout(preferenceTimer);preferenceTimer=setTimeout(flushPreferences,500);
}
function restorePreferences(world){
 restoringPrefs=true;preferences={};preferenceSignature='';
 try{const p=JSON.parse(localStorage.getItem('livemap-view-'+world)||'{}');if(p.version===1)preferences=p}catch{}
 for(const[id,defaultValue]of Object.entries(preferenceDefaults)){
  const saved=preferences.controls?.[id],value=typeof saved===typeof defaultValue?saved:defaultValue;
  if(typeof defaultValue==='boolean')$(id).checked=value;else $(id).value=value;
 }
 if(!['cartographer','plain'].includes($('viewMode').value))$('viewMode').value='cartographer';
 if(!['64','96','128','192','320'].includes($('seedY').value))$('seedY').value='64';
 if(!Number.isFinite(Number($('seedOpacity').value))||Number($('seedOpacity').value)<.1||Number($('seedOpacity').value)>.7)$('seedOpacity').value='0.32';
 for(const[id,min,max,defaultValue]of [['exaggeration',0,8,1.5],['light',0,1.5,.8],['packRate',.25,2,1],['packColumns',1,128,4],['packRevisit',5,300,300]]){const n=Number($(id).value);if(!Number.isFinite(n)||n<min||n>max)$(id).value=defaultValue}
 for(const p of panels)p.open=false;
 syncPanelButtons();styleChanged();filtersChanged();rateCommand();restoringPrefs=false;
}
const tileChanges=delta=>Object.values(delta||{}).some(d=>d.upsert.length||d.remove.length);
const mergeTiles=(old={},delta={})=>{const out={...old};for(const[d,change]of Object.entries(delta)){const entries=new Map((out[d]||[]).map(c=>[c[0]+','+c[1],c]));for(const[x,z]of change.remove)entries.delete(x+','+z);for(const c of change.upsert)entries.set(c[0]+','+c[1],c);out[d]=[...entries.values()]}return out};
const panels=[...document.querySelectorAll('.floating-panel')],mobile=window.matchMedia?.('(max-width: 720px)');
let editorWorkbench=null;
function syncEditorWorkspace(){if(!editorWorkbench)return;const workspace=$('buildingPanel').open?'building':$('editorPanel').open?'map':null;if(workspace)editorWorkbench.setWorkspace(workspace);else editorWorkbench.suspend()}
function syncPanelButtons(){syncEditorWorkspace();for(const button of document.querySelectorAll('[data-panel]'))button.setAttribute('aria-expanded',String($(button.dataset.panel).open))}
function openPanel(id){for(const panel of panels)if(panel.id!==id)panel.open=false;$(id).open=true;syncPanelButtons()}
for(const panel of panels)panel.addEventListener('toggle',()=>{if(panel.open)for(const other of panels)if(other!==panel)other.open=false;syncPanelButtons();queuePreferences()});
for(const button of document.querySelectorAll('[data-panel]'))button.onclick=()=>{const panel=$(button.dataset.panel);if(panel.open)panel.open=false;else openPanel(panel.id);syncPanelButtons()};
function mobileLayout(){for(const panel of panels)panel.open=false;syncPanelButtons()}
mobile?.addEventListener?.('change',mobileLayout);mobileLayout();
const chiko=new Chiko({slot:$('chiko-slot'),label:$('chiko-state-name'),bubble:$('chiko-bubble')});
const tileSource=new TileSource();
function dimensionChanged(d){$('dimension').value=d;for(const b of document.querySelectorAll('[data-dimension]'))b.setAttribute('aria-pressed',String(Number(b.dataset.dimension)===d));seedControls()}
function seedControls(){const info=state?.seed_layer,overworld=Number($('dimension').value)===0,available=!!info?.available&&overworld;$('showSeed').disabled=!available;for(const id of ['seedY','seedOpacity','seedSmooth'])$(id).disabled=!available||!$('showSeed').checked;$('seedOpacityValue').textContent=Math.round(Number($('seedOpacity').value||.32)*100)+'%';$('seedStatus').textContent=!info?.available?'Prévia indisponível: '+(info?.description||'reinicie o servidor para conferir o gerador.'):!overworld?'Prévia disponível somente no Overworld.':$('showSeed').checked?'Transparente = biomas previstos em Y '+$('seedY').value+'. Costas e fronteiras podem divergir. Não inclui construções nem relevo real.':'Opcional: prevê biomas mesmo sem visitar a área. Terreno observado tem prioridade.'}
function tileControls(){
 const sizes=['64','128','256','512','1024','2048'];if(!sizes.includes($('tilePixels').value))$('tilePixels').value='256';
 if(!['16','32','64','128','256'].includes($('tileCache').value))$('tileCache').value='16';
 if(!['1','2','4','8'].includes($('tileDownloads').value))$('tileDownloads').value='4';
 const pixels=Number($('tilePixels').value),minimum=pixels>=2048?128:pixels>=1024?32:16;
 if(Number($('tileCache').value)<minimum)$('tileCache').value=String(minimum);
 for(const option of $('tileCache').options||[])option.disabled=Number(option.value)<minimum;
 const signature=[pixels,$('tileCache').value,$('tileDownloads').value].join(':');
 if(signature!==browserTileSignature){browserTileSignature=signature;tileSource.configure({pixels,maxBytes:Number($('tileCache').value)*1048576,concurrency:Number($('tileDownloads').value)})}
 $('tilePixels').disabled=!state?.tile_options?.sizes?.includes(pixels);
 const text=$('tilePixels').disabled?'Reinicie o servidor para mudar o tamanho dos tiles.':pixels+' px por tile · cache de imagens: '+$('tileCache').value+' MiB. '+(pixels>=1024?'Tiles grandes podem demorar mais. ':'')+'O tamanho muda a área coberta, não o detalhe do mapa.';
 if($('tileSettingsStatus').textContent!==text)$('tileSettingsStatus').textContent=text;
}
function cameraChanged(c){
 $('coords').textContent=c.cursor?'Cursor X '+Math.floor(c.cursor.x)+' · Z '+Math.floor(c.cursor.z):'Centro X '+Math.round(c.x)+' · Z '+Math.round(c.z)+' · '+c.scale.toFixed(2)+' px/bloco';
 const p=state?.players?.find(p=>p.id===c.following)||state?.players?.find(p=>p.host)||state?.players?.[0];
 $('playerCoords').textContent=p?p.name+': X '+Math.round(p.x)+' · Y '+Math.round(p.y)+' · Z '+Math.round(p.z):(globalThis.DoodleAtlasI18n?.t('Sem jogador ao vivo')||'Sem jogador ao vivo');
 $('follow').textContent=c.following?'Seguindo '+(state?.players?.find(p=>p.id===c.following)?.name||'jogador'):'Arraste para explorar';
 for(const[id,value]of [['cameraX',Math.round(c.x)],['cameraZ',Math.round(c.z)],['cameraScale',Number(c.scale.toFixed(2))]])if(document.activeElement!==$(id))$(id).value=value;
 const target=100/c.scale,power=10**Math.floor(Math.log10(target));let blocks=power;for(const n of [1,2,5])if(n*power<=target)blocks=n*power;
 $('scaleLabel').textContent=blocks+' blocos';$('scaleBar').style.width=Math.round(blocks*c.scale)+'px';queuePreferences();
 if($('exportDialog').open)exportSize();
}
const map=new MapRenderer({canvas:$('map'),overlay:$('markers'),source:tileSource,onCamera:cameraChanged,onDimension:dimensionChanged,onSelect:showSelection,onCoverage:c=>{coverage=c;mapStatus()}});
const portraits=new PixelAvatars({map});map.portraits=portraits;portraits.onChange=()=>{playerSignature=''};
const editor=new MapEditor({map,getState:()=>state,getToken:()=>hostToken});map.editor=editor;editorWorkbench=editor;
const trailBuffer=new TrailBuffer();
const timeline=new MapTimeline({getState:()=>state,getToken:()=>hostToken,onGo:c=>map.setCamera(c),getView:()=>({...map.camera,width:$('markers').clientWidth,height:$('markers').clientHeight})});
$('showTrail').onchange=()=>{if(state){trailBuffer.update(state,$('showTrail').checked);map.setTrail(trailBuffer.points)}queuePreferences()};
function requestedCamera(){try{const q=new URL(window.location.href).searchParams;if(!['x','z','scale'].every(k=>q.has(k)))return null;const c={x:Number(q.get('x')),z:Number(q.get('z')),scale:Number(q.get('scale')),dimension:Number(q.get('dimension')||0)};return Object.values(c).every(Number.isFinite)&&[0,1,2].includes(c.dimension)&&c.scale>=.04&&c.scale<=32?c:null}catch{return null}}
let initialCamera=requestedCamera();
function displayError(){const text=[uiError,state?.player_error,state?.terrain?.error].filter(Boolean).join(' · ');$('error').textContent=text;$('error').hidden=!text}
function mapStatus(){
 const legend=$('unknownLegend'),s=state;
 if(uiError||s?.player_error||s?.terrain?.error||connectionLost){legend.textContent=connectionLost?'Conexão interrompida · mantendo o mapa disponível':'Falha de leitura · mantendo os dados disponíveis';chiko.setState('confuso','Vamos conferir a conexão e os dados.');return}
 if(!s||!coverage){legend.textContent='Preparando esta página do mapa…';chiko.setState('folheando');return}
 if(coverage.failed){legend.textContent='Algumas imagens não carregaram · tente atualizar a página';chiko.setState('confuso','Algumas partes desta página não carregaram.');return}
 if(!coverage.known&&coverage.seedKnown){legend.textContent=coverage.seedFailed?'A prévia da seed não carregou · tente atualizar':coverage.seedLoaded?'Prévia experimental da seed · biomas em Y '+$('seedY').value+' · sem terreno observado aqui':'Preparando prévia da seed…';chiko.setState(coverage.seedFailed?'confuso':coverage.seedLoaded?'lendo':'folheando',coverage.seedLoaded?'Isto é uma previsão. Ainda não temos o terreno real desta área.':undefined);return}
 if(!coverage.known){legend.textContent=s.terrain.progress?'Lendo o save · esta área ainda não tem terreno disponível':'Sem terreno conhecido nesta área · mova o mapa ou use Ver mapa';chiko.setState(s.terrain.progress?'folheando':'lendo','Esta área ainda não tem terreno disponível.');return}
 if(!coverage.loaded&&coverage.pending){legend.textContent='Carregando terreno desta área…';chiko.setState('folheando');return}
 legend.textContent='Superfície observada · áreas vazias indicam ausência de dados';
 if(coverage.seedLoaded)legend.textContent='Terreno observado sobre prévia transparente da seed · previsão experimental em Y '+$('seedY').value;
 const fresh=s.players.length>0&&Date.now()/1000-s.last_player_update<5;
 chiko.setState(!fresh?'dormindo':Date.now()<happyUntil?'animado':'lendo',!fresh?'O terreno está aqui, mesmo sem jogador ao vivo.':undefined);
}
function fail(error){uiError=error instanceof Error?error.message:String(error);displayError();mapStatus()}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){for(const panel of panels)panel.open=false;syncPanelButtons()}});
window.addEventListener('pagehide',flushPreferences);document.addEventListener('visibilitychange',()=>{if(document.hidden)flushPreferences()});
function showSelection(point){selected=point;waypointTarget=null;$('addWaypoint').textContent='Anotar centro do mapa';$('selectionCard').hidden=false;$('selectionName').textContent=point.name||point.typeId||'Ponto do mapa';$('selectionCoords').textContent='X '+Math.floor(point.x)+(Number.isFinite(point.y)?' · Y '+Math.round(point.y):'')+' · Z '+Math.floor(point.z);$('selectionType').textContent=dimName(point.dimension)+(point.typeId?' · '+point.typeId:'')+(point.selectionType==='observed'?' · Encontrado no save':'');}
$('selectionClose').onclick=()=>{$('selectionCard').hidden=true;selected=null};
$('markSelection').onclick=()=>{waypointTarget=selected;$('addWaypoint').textContent='Anotar ponto selecionado';openPanel('waypointsPanel');$('waypointName').focus();$('waypointStatus').textContent='A anotação usará o ponto selecionado.'};
function loadWaypoints(world){try{const data=JSON.parse(localStorage.getItem('livemap-waypoints-'+world)||'[]');waypoints=Array.isArray(data)?data.filter(w=>typeof w.name==='string'&&Number.isFinite(w.x)&&Number.isFinite(w.z)&&[0,1,2].includes(w.dimension)):[]}catch{waypoints=[]}}
function canShare(){return !!state?.shared_waypoints?.available&&!!(hostToken||state.shared_waypoints.pin_writes)}
function sharedControls(){
 const allowed=canShare();$('waypointScope').children[1].disabled=!allowed;
 if(!allowed)$('waypointScope').value='personal';
 $('waypointPermission').textContent=!state?.shared_waypoints?.available?'Por enquanto, você pode salvar pontos pessoais.':allowed?'Pessoal fica neste navegador. Compartilhado fica no mundo e pode ser alterado por quem tem permissão.':'Você pode ver os pontos compartilhados. Para alterá-los, entre com o PIN ou use o PC do host.';
}
function syncSharedPoints(){
 const points=state?.shared_waypoints?.points||[];const signature=JSON.stringify(points);
 if(signature!==waypointSignature){waypointSignature=signature;sharedWaypoints=points;showWaypoints()}
 sharedControls();
}
async function writeShared(point,id=null){
 const expected=identity,world=state.world_id;
 const headers={'Content-Type':'application/json'};if(hostToken)headers['X-Host-Token']=hostToken;
 const response=await fetch(id?'/api/waypoints/'+encodeURIComponent(id)+'?world_id='+encodeURIComponent(world):'/api/waypoints',{method:id?'DELETE':'POST',headers,...(id?{}:{body:JSON.stringify({...point,world_id:world})})});
 if(!response.ok)throw Error(await response.text());
 const result=await response.json();
 if(identity!==expected)return false;
 // A heartbeat may already contain a newer write from another browser.
 if((result.revision??0)>=(state.shared_waypoints?.revision??0)){state.shared_waypoints=result;syncSharedPoints()}
 return true;
}
function showWaypoints(){
 $('waypoints').replaceChildren();
 for(const[w,index,shared]of [...waypoints.map((w,i)=>[w,i,false]),...sharedWaypoints.map(w=>[w,null,true])]){
  const row=document.createElement('div');row.className='waypoint-row';const button=document.createElement('button');button.className='waypoint-name';button.textContent=(shared?'⚑ Compartilhado · ':'⚑ Pessoal · ')+w.name;button.onclick=()=>{map.setCamera({x:w.x,z:w.z,dimension:w.dimension,scale:3});if(mobile?.matches)$('waypointsPanel').open=false};
  const remove=document.createElement('button');remove.className='remove-waypoint';remove.textContent='×';remove.disabled=shared&&!canShare();remove.setAttribute('aria-label','Remover marcador '+w.name);remove.onclick=async()=>{if(shared){if(waypointBusy)return;const expected=identity;waypointBusy=true;try{if(await writeShared(null,w.id))$('waypointStatus').textContent='Ponto compartilhado removido.'}catch(error){if(identity===expected)$('waypointStatus').textContent=error.message}finally{waypointBusy=false}}else{waypoints.splice(index,1);saveWaypoints()}};row.append(button,remove);$('waypoints').append(row);
 }map.setWaypoints([...waypoints,...sharedWaypoints]);
}
function saveWaypoints(){try{localStorage.setItem('livemap-waypoints-'+state.world_id,JSON.stringify(waypoints));$('waypointStatus').textContent='Marcadores salvos neste navegador.'}catch{fail('O navegador não permitiu salvar os marcadores. Eles estão apenas nesta sessão.')}showWaypoints()}
$('waypointForm').onsubmit=async e=>{
 e.preventDefault();if(!state||waypointBusy)return;const name=$('waypointName').value.trim();if(!name)return;
 const p=waypointTarget||{...map.camera},point={name:name.slice(0,60),x:Math.floor(p.x),z:Math.floor(p.z),dimension:p.dimension};
 const expected=identity;waypointBusy=true;$('addWaypoint').disabled=true;
 try{
  if($('waypointScope').value==='shared'){if(!canShare())throw Error('Sem permissão para compartilhar neste mundo.');if(!await writeShared(point))return;$('waypointStatus').textContent='Ponto salvo no mundo e compartilhado com os outros navegadores.'}
  else{waypoints.push(point);saveWaypoints()}
  if(identity===expected){$('waypointName').value='';selected=null;waypointTarget=null;$('addWaypoint').textContent='Anotar centro do mapa';$('selectionCard').hidden=true}
 }catch(error){if(identity===expected)$('waypointStatus').textContent=error.message}finally{waypointBusy=false;$('addWaypoint').disabled=false}
};

function update(s){
 const next=s.session_id+':'+s.world_id;const freshWorld=identity!==next;
 if(freshWorld){flushPreferences();identity=next;fitted=false;state=null;coverage=null;selected=null;waypointTarget=null;playerSignature='';wasFresh=false;lastKnownCount=0;happyUntil=0;$('selectionCard').hidden=true;sharedWaypoints=[];waypointSignature='';$('waypointStatus').textContent='';loadWaypoints(s.world_id);showWaypoints();restorePreferences(s.world_id)}
 if(s.terrain){s.terrain={...state?.terrain,...s.terrain};for(const field of ['chunks','regions'])if(s.terrain[field+'_delta']){s.terrain[field]=mergeTiles(state?.terrain?.[field],s.terrain[field+'_delta']);delete s.terrain[field+'_delta']}}
 if(s.live_chunks_delta){s.live_chunks=tileChanges(s.live_chunks_delta)?mergeTiles(state?.live_chunks,s.live_chunks_delta):state?.live_chunks||{};delete s.live_chunks_delta}
 if(s.tile_index_delta){s.tile_index=tileChanges(s.tile_index_delta)?mergeTiles(state?.tile_index,s.tile_index_delta):state?.tile_index||{};delete s.tile_index_delta}
 if(s.entities_delta){const entities=new Map((state?.entities||[]).map(e=>[e.id,e]));for(const id of s.entities_delta.remove)entities.delete(id);for(const e of s.entities_delta.upsert)entities.set(e.id,e);s.entities=[...entities.values()];delete s.entities_delta}
 s={...state,...s};s.players||=[];s.entities||=[];s.terrain||={chunks:{},regions:{}};s.live_chunks||={};state=s;map.update(s);portraits.update(s);syncSharedPoints();timeline.update(s);editor.update(s);if(trailBuffer.update(s,$('showTrail').checked))map.setTrail(trailBuffer.points);
 seedControls();
 tileControls();
 const storage=s.world_storage;
 $('storageStatus').textContent=storage?.persistent?(storage.quota_reached?'Limite de armazenamento atingido; dados antigos preservados. ':storage.near_limit?'Armazenamento perto do limite. ':'Salvo por mundo. ')+(storage.bytes/1048576).toFixed(1)+' MiB em '+storage.folder+' · cota '+Math.round(storage.limit_bytes/1048576)+' MiB, com reserva para banco e journal.':'Armazenamento da sessão; persistência por mundo desativada.';
 $('world').textContent=s.world_name;$('worldSelect').value=s.world_id;$('url').textContent=s.url;$('url').href=s.url;$('command').textContent=s.connect_command;$('command').hidden=s.player_source==='content_log';
 const fresh=Date.now()/1000-s.last_player_update<5;
 $('connection').textContent=s.player_source==='content_log'&&fresh?'● Conectado pelo pack':s.minecraft_connected?'● '+(fresh?'Posições ao vivo':'Aguardando posições'):'○ Sem jogador conectado';
 const count=Object.values(s.terrain.chunks||{}).reduce((n,c)=>n+c.length,0),live=Object.values(s.live_chunks).reduce((n,c)=>n+c.length,0);
 $('terrain').textContent=s.terrain.progress?'Lendo '+s.terrain.progress.done+' / '+s.terrain.progress.total+' chunks':count+' chunks do save · '+live+' capturados · '+(s.terrain.failed_chunks?.length||0)+' erros de parser';
 $('entityCount').textContent=s.entities.length+' entidades carregadas';$('empty').hidden=s.players.length>0;
 $('packBindCommand').textContent=s.pack_command||('/livemap:vincular '+s.world_id);
 const found=s.terrain.observed_points;
 $('observedPointsStatus').textContent=found?(found.points?.length||0)+' camas/portais no save · '+found.scanned_chunks+' chunks examinados'+(found.truncated?' · limite de pontos atingido':'')+'. Atualiza com a leitura do save.':'Aguardando a primeira leitura de camas e portais.';
 if(s.render_queue){const q=s.render_queue,c=s.tile_cache;$('renderQueue').textContent=c?.quota_reached?'Cache temporário no limite · novas imagens continuam sob demanda.':c?.near_limit?'Cache temporário perto do limite · imagens antigas podem ser descartadas.':q.queued||q.running?'Preparando o mapa: '+(q.queued+q.running)+' imagens aguardando.':'Carregamento em repouso · '+(c?.entries??q.cache_entries)+' imagens no cache temporário.'}
 $('seed').textContent=s.terrain.seed?'Seed: '+s.terrain.seed:'Seed ainda não lida';$('seedMap').href='https://www.chunkbase.com/apps/seed-map'+(s.terrain.seed?'#seed='+encodeURIComponent(s.terrain.seed):'');
 if(s.settings){$('saveRateValue').textContent=s.settings.terrain_seconds+' s';if(document.activeElement!==$('saveRate'))$('saveRate').value=s.settings.terrain_seconds}
 if(s.capabilities?.playerSeconds)$('rateNote').textContent=(fresh?'Taxa recebida do jogo: ':'Última taxa recebida: ')+s.capabilities.playerSeconds+' s; '+s.capabilities.columnsPerTick+' leituras/tick; revisita '+s.capabilities.revisitSeconds+' s. O comando abaixo só muda o jogo quando você o executar.';
 if((fresh&&!wasFresh)||count+live>lastKnownCount)happyUntil=Date.now()+3000;wasFresh=fresh;lastKnownCount=count+live;
 displayError();mapStatus();
 const signature=JSON.stringify(s.players);
 if(signature!==playerSignature){playerSignature=signature;$('players').replaceChildren();
  for(const p of s.players){const b=document.createElement('button');b.className='player';b.setAttribute('aria-pressed',String(map.following===p.id));const avatar=document.createElement('span');avatar.className='avatar';avatar.textContent=p.name.slice(0,1);if(portraits.settings.players){const face=document.createElement('canvas');face.width=24;face.height=24;const ctx=face.getContext('2d');if(ctx&&portraits.drawPlayer(ctx,p,12,12,map.style.palette==='atlas')){avatar.textContent='';avatar.append(face)}}const text=document.createElement('span');text.textContent=(p.host?'★ ':'')+p.name;const coords=document.createElement('small');coords.textContent=dimName(p.dimension)+' · '+Math.round(p.x)+', '+Math.round(p.y)+', '+Math.round(p.z);text.append(coords);b.append(avatar,text);b.onclick=()=>{map.follow(p.id);cameraChanged({...map.camera,following:p.id});for(const item of $('players').children)item.setAttribute('aria-pressed',String(item===b));if(mobile?.matches)$('playersPanel').open=false};$('players').append(b)}
 }
 if(!fitted&&(count||live||initialCamera||validCamera(preferences.camera))){if(initialCamera){map.setCamera(initialCamera);initialCamera=null}else if(validCamera(preferences.camera))map.setCamera(preferences.camera);else map.fit();fitted=true}
 cameraChanged({...map.camera,following:map.following});
}
async function worlds(){
 const response=await fetch('/api/worlds');if(!response.ok)throw Error('Não foi possível listar os mundos: HTTP '+response.status);
 $('worldSelect').replaceChildren();for(const world of await response.json()){const option=document.createElement('option');option.value=world.id;option.textContent=world.name;$('worldSelect').append(option)}
 const host=await fetch('/api/host');hostToken=host.ok?(await host.json()).token||null:null;$('worldSelect').disabled=!hostToken;$('saveRate').disabled=!hostToken;
 $('hostHint').textContent=hostToken?'Você pode escolher o mundo neste PC.':'Para trocar o mundo ou o intervalo do save, abra o endereço local exibido no terminal do host.';
 if(state){$('worldSelect').value=state.world_id;sharedControls();showWaypoints();timeline.update(state);editor.controls()}
}
async function connect(){
 const r=await fetch('/api/state');if(r.status===401){stream?.close();if(!$('login').open)$('login').showModal();return}if(!r.ok)throw Error('HTTP '+r.status);
 uiError='';connectionLost=false;update(await r.json());$('qr').src='/qr.png';await worlds().catch(fail);stream?.close();stream=new EventSource('/api/events');stream.onmessage=e=>{try{connectionLost=false;update(JSON.parse(e.data))}catch(error){fail(error)}};stream.onerror=()=>{connectionLost=true;$('connection').textContent='Reconectando ao servidor…';mapStatus()};
}
$('pinform').onsubmit=async e=>{e.preventDefault();try{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin:$('pin').value})});if(r.ok){$('login').close();$('pin').value='';await connect()}else $('loginerror').textContent='PIN inválido ou limite de tentativas atingido'}catch(error){fail(error)}};
$('worldSelect').onchange=async e=>{try{const r=await fetch('/api/worlds/select',{method:'POST',headers:{'Content-Type':'application/json','X-Host-Token':hostToken},body:JSON.stringify({id:e.target.value})});if(!r.ok)throw Error(await r.text())}catch(error){fail(error)}};
function changeDimension(value){map.setDimension(Number(value));$('selectionCard').hidden=true;selected=null;waypointTarget=null;$('addWaypoint').textContent='Anotar centro do mapa'}
$('dimension').onchange=e=>changeDimension(e.target.value);for(const b of document.querySelectorAll('[data-dimension]'))b.onclick=()=>changeDimension(b.dataset.dimension);
$('cameraForm').onsubmit=e=>{e.preventDefault();const x=Number($('cameraX').value),z=Number($('cameraZ').value),scale=Number($('cameraScale').value);if([x,z,scale].every(Number.isFinite)&&scale>=.04&&scale<=32)map.setCamera({x,z,scale})};
$('plus').onclick=()=>map.zoom(1.5);$('minus').onclick=()=>map.zoom(1/1.5);$('fit').onclick=()=>map.fit();$('spawn').onclick=()=>{if(state?.terrain.spawn)map.setCamera({x:state.terrain.spawn.x,z:state.terrain.spawn.z,dimension:0,scale:3})};$('stopFollow').onclick=()=>{map.following=null;for(const b of $('players').children)b.setAttribute('aria-pressed','false');cameraChanged(map.camera)};
function styleChanged(){tileControls();const paper=$('viewMode').value==='cartographer';document.body.dataset.appearance=paper?'cartographer':'plain';$('exaggerationValue').value=$('exaggeration').value;map.setStyle({mode:'relief',tilePixels:Number($('tilePixels').value),palette:paper?'atlas':'minecraft',seed:$('showSeed').checked,seedY:Number($('seedY').value)||64,seedOpacity:Number($('seedOpacity').value)||.32,seedSmooth:$('seedSmooth').checked,cartographic:paper,grid:$('showGrid').checked,exaggeration:Number($('exaggeration').value),intensity:Number($('light').value)});seedControls();queuePreferences()}
function filtersChanged(){map.setFilters({animals:$('animals').checked,hostiles:$('hostiles').checked,others:$('others').checked,aquatic:$('aquatic').checked,observed:$('observedPoints').checked,text:$('entityFilter').value,smooth:$('smooth').checked});queuePreferences()}
for(const id of ['viewMode','showGrid','showSeed','seedY','seedSmooth','tilePixels','tileCache','tileDownloads'])$(id).onchange=styleChanged;$('seedOpacity').oninput=styleChanged;$('exaggeration').oninput=()=>{$('exaggerationValue').value=$('exaggeration').value};for(const id of ['exaggeration','light'])$(id).onchange=styleChanged;
for(const id of ['animals','hostiles','others','aquatic','smooth','observedPoints'])$(id).onchange=filtersChanged;$('entityFilter').oninput=filtersChanged;
$('saveRate').oninput=()=>{$('saveRateValue').textContent=$('saveRate').value+' s'};$('saveRate').onchange=async()=>{try{const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json','X-Host-Token':hostToken},body:JSON.stringify({terrain_seconds:Number($('saveRate').value)})});if(!r.ok)throw Error(await r.text());uiError='';displayError()}catch(error){fail(error)}};
function rateCommand(){const seconds=Number($('packRate').value),columns=Number($('packColumns').value),revisit=Number($('packRevisit').value);$('packRateValue').textContent=seconds+' s';const valid=seconds>=.25&&seconds<=2&&Number.isInteger(columns)&&columns>=1&&columns<=128&&Number.isInteger(revisit)&&revisit>=5&&revisit<=300;$('copyRate').disabled=!valid;$('rateCommand').textContent=valid?'/livemap:taxa '+seconds+' '+columns+' '+revisit:'Use 0,25–2 s, 1–128 leituras e 5–300 s de revisita.';queuePreferences()}
$('packPreset').onchange=()=>{if($('packPreset').value!=='custom'){$('packColumns').value=$('packPreset').value;$('packRate').value=1;$('packRevisit').value=300}rateCommand()};
for(const id of ['packRate','packColumns','packRevisit'])$(id).oninput=()=>{$('packPreset').value='custom';rateCommand()};
$('copyRate').onclick=async()=>{try{await navigator.clipboard.writeText($('rateCommand').textContent);$('copyRate').textContent='Copiado'}catch{$('copyRate').textContent='Selecione e copie o comando acima'}};
let exporting=false;
 $('copyPackBind').onclick=async()=>{try{await navigator.clipboard.writeText($('packBindCommand').textContent);$('copyPackBind').textContent='Copiado: cole no chat do jogo'}catch{$('copyPackBind').textContent='Selecione e copie o comando acima'}};
function exportSize(){try{const l=map.exportLayout(Number($('exportResolution').value));$('exportSize').textContent='Imagem com moldura: '+l.width+' × '+l.height+' px · cerca de '+(l.width*l.height*4/1048576).toFixed(1)+' MiB de pixels temporários, além do mapa aberto.'}catch(error){$('exportSize').textContent=error.message}}
$('openExport').onclick=()=>{if(!state)return;$('exportTitle').value=String(state.world_name||'Meu mundo').trim().slice(0,80);$('exportStatus').textContent='Enquadre a área desejada antes de baixar.';exportSize();if(!$('exportDialog').open)$('exportDialog').showModal()};
$('closeExport').onclick=()=>$('exportDialog').close();$('exportResolution').onchange=exportSize;
$('exportForm').onsubmit=async e=>{
 e.preventDefault();if(exporting)return;exporting=true;$('exportDownload').disabled=true;$('exportStatus').textContent='Preparando a imagem…';let result=null,restoreExport=null;
 try{
  if(($('exportAppearance').value||'antique')==='antique')restoreExport=await map.prepareInkExport();
  result=map.createExport({title:$('exportTitle').value,maxSide:Number($('exportResolution').value),includeWaypoints:$('exportWaypoints').checked,includeAnnotations:$('exportAnnotations').checked,appearance:$('exportAppearance').value||'antique'});
  const blob=await new Promise((resolve,reject)=>result.canvas.toBlob(b=>b?resolve(b):reject(Error('O navegador não conseguiu gerar o PNG.')),'image/png'));
  const name=result.metadata.world.normalize('NFKD').replace(/[^a-z0-9_-]+/gi,'-').replace(/^-+|-+$/g,'').slice(0,48)||'mapa';
  const url=URL.createObjectURL(blob),link=document.createElement('a');
  try{link.href=url;link.download=name+'-'+dimName(result.metadata.dimension)+'-'+result.metadata.created.replace(/[:.]/g,'-')+'.png';document.body.append(link);link.click()}finally{link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000)}
  $('exportStatus').textContent='PNG preparado ('+(blob.size/1024).toFixed(0)+' KiB). Confira o download ou a opção de salvar imagem do navegador.';
 }catch(error){$('exportStatus').textContent=error instanceof Error?error.message:String(error)}
 finally{restoreExport?.();if(result){result.canvas.width=1;result.canvas.height=1}exporting=false;$('exportDownload').disabled=false}
};
$('biomeForm').onsubmit=async e=>{e.preventDefault();try{const query=$('biomeQuery').value.trim(),r=await fetch('/api/biomes?q='+encodeURIComponent(query)+'&dimension='+map.camera.dimension);if(!r.ok)throw Error('Busca: HTTP '+r.status);const data=await r.json();$('biomeResults').replaceChildren();
 for(const item of [...data.seed,...data.saved].slice(0,50)){const b=document.createElement('button');b.textContent=item.error||item.biome+' · X '+Math.round(item.x)+' Z '+Math.round(item.z)+' · '+(item.source==='seed'?'seed':'capturado');b.onclick=()=>{if(!item.error)map.setCamera({x:item.x,z:item.z,scale:3})};$('biomeResults').append(b)}
 if(!data.seed.length&&!data.saved.length)$('biomeResults').textContent='Nenhum resultado nos dados disponíveis. Use a busca pela seed no jogo ou o mapa externo.';
 }catch(error){fail(error)}};
$('themeMode').onchange=()=>{themePreference=['light','dark'].includes($('themeMode').value)?$('themeMode').value:'system';applyTheme();try{localStorage.setItem('livemap-theme',themePreference);$('themeStatus').textContent='Preferência guardada neste navegador.'}catch{$('themeStatus').textContent='Tema aplicado; não foi possível guardar a escolha.'}};
const themeChanged=()=>{if(themePreference==='system')applyTheme()};
if(systemTheme?.addEventListener)systemTheme.addEventListener('change',themeChanged);else systemTheme?.addListener?.(themeChanged);
applyTheme();styleChanged();filtersChanged();rateCommand();connect().catch(fail);

document.addEventListener("doodleatlas:language",()=>{editor.syncPalettes();map.invalidateOverlay();if(!state?.players?.length)$('playerCoords').textContent=globalThis.DoodleAtlasI18n.t('Sem jogador ao vivo');});
