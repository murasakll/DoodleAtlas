(() => {
 'use strict';
 const storageKey='doodleatlas-language';
 let language;
 try{language=localStorage.getItem(storageKey);}catch{}
 if(!['pt-BR','en'].includes(language))language=navigator.language?.toLowerCase().startsWith('en')?'en':'pt-BR';
 const messages=globalThis.DoodleAtlasLocales.en;
 const patterns=[
  [/^Seguindo (.*)$/,'Following $1'],
  [/^Compartilhado · (.*)$/,'Shared · $1'],
  [/^Pessoal · (.*)$/,'Personal · $1'],
  [/^Prévia experimental da seed · biomas em Y (.*) · sem terreno observado aqui$/,'Experimental seed preview · biomes at Y $1 · no observed terrain here'],
  [/^Terreno observado sobre prévia transparente da seed · previsão experimental em Y (.*)$/,'Observed terrain over a transparent seed preview · experimental prediction at Y $1'],
  [/^Remover marcador (.*)$/,'Remove place $1'],
  [/^Conteúdo de (.*)$/,'Contents of $1'],
  [/^(\d+(?:[.,]\d+)?) blocos$/,'$1 blocks'],
  [/^(\d+) entidades carregadas$/,'$1 entities loaded'],
  [/^(\d+) páginas$/,'$1 pages'],
  [/^(\d+) mudanças registradas$/,'$1 recorded changes'],
  [/^(\d+) quadros$/,'$1 frames'],
  [/^(\d+) chunks do save$/,'$1 saved chunks'],
  [/^(\d+) capturados$/,'$1 captured'],
  [/^(\d+) erros de parser$/,'$1 parser errors'],
  [/^Lendo (\d+) \/ (\d+) chunks$/,'Reading $1 / $2 chunks'],
  [/^(\d+) camas\/portais no save · (\d+) chunks examinados(.*)\. Atualiza com a leitura do save\.$/,'$1 beds/portals in the save · $2 chunks examined$3. Updates when the save is read.'],
  [/^(\d+) chunks selecionados\. (.*)$/,(_,n,message)=>n+' chunks selected. '+translate(message)],
  [/^(\d+) \/ 20\.000 células · (.*)$/,(_,n,message)=>n+' / 20,000 cells · '+translate(message)],
  [/^(\d+) alterações pendentes$/,'$1 pending changes'],
  [/^Prévia indisponível: (.*)$/,(_,message)=>'Preview unavailable: '+translate(message)],
  [/^(\d+) px por tile · cache de imagens: (\d+) MiB\. (Tiles grandes podem demorar mais\. )?O tamanho muda a área coberta, não o detalhe do mapa\.$/,(_,size,cache,large)=>size+' px per tile · image cache: '+cache+' MiB. '+(large?'Large tiles may take longer. ':'')+'Size changes the area covered, not map detail.'],
  [/^Transparente = biomas previstos em Y (\d+)\. Costas e fronteiras podem divergir\. Não inclui construções nem relevo real\.$/,'Transparent = predicted biomes at Y $1. Coasts and borders may differ. Does not include buildings or actual relief.'],
  [/^(Taxa recebida do jogo|Última taxa recebida): (.*) s; (\d+) leituras\/tick; revisita (.*) s\. O comando abaixo só muda o jogo quando você o executar\.$/,(_,kind,seconds,reads,revisit)=>(kind==='Taxa recebida do jogo'?'Rate received from the game: ':'Last received rate: ')+seconds+' s; '+reads+' reads/tick; revisit '+revisit+' s. The command below changes the game only when you run it.'],
  [/^Imagem com moldura: (\d+) × (\d+) px · cerca de (.*) MiB de pixels temporários, além do mapa aberto\.$/,'Framed image: $1 × $2 px · about $3 MiB of temporary pixels, in addition to the open map.'],
  [/^(Salvo por mundo\.|Armazenamento perto do limite\.|Limite de armazenamento atingido; dados antigos preservados\.) (.*) MiB em (.*) · cota (\d+) MiB, com reserva para banco e journal\.$/,(_,status,size,folder,quota)=>translate(status)+' '+size+' MiB in '+folder+' · quota '+quota+' MiB, with room for database and journal.'],
  [/^Não foi possível ler a edição: HTTP (.*)$/,'Could not read drawing: HTTP $1'],
  [/^Não foi possível listar os mundos: HTTP (.*)$/,'Could not list worlds: HTTP $1'],
  [/^PNG preparado \((.*) KiB\)\. Confira o download ou a opção de salvar imagem do navegador\.$/,'PNG ready ($1 KiB). Check your downloads or the browser image-saving option.'],
  [/^Centro X (.*)$/,(_,value)=>'Center X '+value.replace('px/bloco','px/block')],
  [/^Cursor X (.*)$/,(_,value)=>'Cursor X '+value.replace('px/bloco','px/block')],
  [/^(.*) px\/bloco$/,'$1 px/block'],
  [/^(\d+) × (\d+) px · padrão$/,'$1 × $2 px · default'],
  [/^(\d+) · padrão$/,'$1 · default'],
  [/^(\d+)% da folha$/,'$1% of page'],
  [/^Preparando o mapa: (\d+) imagens aguardando\.$/,'Preparing the map: $1 images waiting.'],
  [/^Carregamento em repouso · (\d+) imagens no cache temporário\.$/,'Loading idle · $1 images in the temporary cache.'],
  [/^(.*) · (\d+(?: × \d+)?) células?$/,(_,kind,size)=>translate(kind)+' · '+size+' cells'],
  [/^(.*) · Encontrado no save$/,'$1 · Found in the save'],
  [/^Região principal salva · X (.*)$/,'Main region saved · X $1'],
  [/^(.*) MiB no banco e journal\.$/,'$1 MiB in the database and journal.'],
  [/^Falha no quadro: (.*)$/,'Frame failed: $1'],
  [/^Construir · (.*)$/,(_,kind)=>'Build · '+translate(kind)],
  [/^Desenhar · (.*)$/,(_,kind)=>'Draw · '+translate(kind)],
  [/^(.*) células · (.*)$/,'$1 cells · $2'],
 ];
 function translate(source){
  if(language==='pt-BR'||!source)return source;
  const text=String(source),trimmed=text.trim();
  let result=Object.hasOwn(messages,trimmed)?messages[trimmed]:undefined;
  if(result===undefined){
   for(const [pattern,replacement] of patterns){if(pattern.test(trimmed)){result=trimmed.replace(pattern,replacement);break;}}
   // Decorations and counters are separate from the copy, not separate messages.
   if(result===undefined){
    const decorated=trimmed.match(/^([^\p{L}\p{N}]+)(.+)$/u);
    if(decorated)result=decorated[1]+translate(decorated[2]);
    else if(trimmed.includes(' · '))result=trimmed.split(' · ').map(part=>translate(part)).join(' · ');
   }
  }
  return result===undefined?source:text.slice(0,text.indexOf(trimmed))+result+text.slice(text.indexOf(trimmed)+trimmed.length);
 }
 const originals=new WeakMap();
 const attributes=new WeakMap();
 const excluded='script,style,code,svg,[translate="no"],[data-i18n-skip],#world,#worldSelect option,#players,#portraitPlayer option,#editBuilding option:not([value=""]),#selectionName,#playerCoords,#biomeResults,#chiko-state-name,#url,#command,#rateCommand,#packBindCommand';
 function skipped(element){return !element||Boolean(element.closest(excluded));}
 function localizeText(node){
  if(skipped(node.parentElement))return;
  const previous=originals.get(node),current=node.nodeValue;
  const source=previous&&current===previous.rendered?previous.source:current;
  const rendered=translate(source);originals.set(node,{source,rendered});
  if(current!==rendered)node.nodeValue=rendered;
 }
 function localizeAttributes(element){
  if(skipped(element))return;
  let known=attributes.get(element);if(!known){known={};attributes.set(element,known);}
  for(const name of ['title','placeholder','aria-label','aria-valuetext','alt','label']){
   if(!element.hasAttribute(name))continue;
   const current=element.getAttribute(name),previous=known[name];
   const source=previous&&current===previous.rendered?previous.source:current;
   const rendered=translate(source);known[name]={source,rendered};
   if(current!==rendered)element.setAttribute(name,rendered);
  }
 }
 function visit(root){
  if(root.nodeType===Node.TEXT_NODE){localizeText(root);return;}
  if(root.nodeType!==Node.ELEMENT_NODE||skipped(root))return;
  localizeAttributes(root);
  for(const child of root.childNodes)visit(child);
 }
 function changeLanguage(next){
  if(!['pt-BR','en'].includes(next))return;
  language=next;try{localStorage.setItem(storageKey,next);}catch{}
  document.documentElement.lang=next;
  visit(document.head);visit(document.body);
  const select=document.getElementById('languageSelect');if(select)select.value=next;
  document.dispatchEvent(new CustomEvent('doodleatlas:language',{detail:{language:next}}));
 }
 globalThis.DoodleAtlasI18n={t:translate,setLanguage:changeLanguage,get language(){return language;}};
 document.addEventListener('DOMContentLoaded',()=>{
  const field=document.createElement('label');field.className='field language-field';
  const caption=document.createElement('span');caption.textContent='Idioma';
  const select=document.createElement('select');select.id='languageSelect';select.className='input';
  for(const [value,name] of [['pt-BR','Português'],['en','English']]){
   const option=document.createElement('option');option.value=value;option.textContent=name;option.lang=value;option.translate=false;select.append(option);
  }
  select.onchange=()=>changeLanguage(select.value);field.append(caption,select);
  document.querySelector('.map-option-group')?.prepend(field);
  changeLanguage(language);
  // Only changed branches are visited. No polling or full-tree walk on SSE updates.
  new MutationObserver(records=>{
   const changed=new Set();
   for(const record of records){
    if(record.type==='childList')for(const node of record.addedNodes)changed.add(node);
    else changed.add(record.target);
   }
   for(const node of changed){if(node.isConnected)visit(node);}
  }).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['title','placeholder','aria-label','aria-valuetext','alt','label']});
 },{once:true});
})();
