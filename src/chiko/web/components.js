'use strict';
// This isolated gallery never fetches game data, opens SSE or persists user data.
const byId=id=>document.getElementById(id);
const tabs=[...document.querySelectorAll('[role="tab"]')];
function selectTab(tab,focus=false){
 for(const item of tabs){const active=item===tab;item.setAttribute('aria-selected',String(active));item.tabIndex=active?0:-1;byId(item.getAttribute('aria-controls')).hidden=!active}
 if(focus)tab.focus();
}
tabs.forEach((tab,index)=>{
 tab.addEventListener('click',()=>selectTab(tab));
 tab.addEventListener('keydown',event=>{
  let next;
  if(event.key==='ArrowRight')next=(index+1)%tabs.length;
  if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;
  if(event.key==='Home')next=0;
  if(event.key==='End')next=tabs.length-1;
  if(next!==undefined){event.preventDefault();selectTab(tabs[next],true)}
 });
});
byId('discover').addEventListener('click',()=>{byId('action-status').textContent='Uma descoberta de exemplo ganhou uma página!'});
byId('layer-toggle').addEventListener('click',event=>{
 const button=event.currentTarget,active=button.getAttribute('aria-pressed')!=='true';button.setAttribute('aria-pressed',String(active));
 byId('action-status').textContent=active?'Camada real selecionada na amostra.':'Camada real desmarcada na amostra.';
});
byId('follow-demo').addEventListener('click',event=>{
 const button=event.currentTarget,following=button.getAttribute('aria-pressed')!=='true';button.setAttribute('aria-pressed',String(following));button.textContent=following?'Seguindo':'Seguir';
 byId('follow-status').textContent=following?'Ficha selecionada. A câmera do mapa real não foi alterada.':'Você pode escolher outra ficha.';
});
byId('pin-demo-form').addEventListener('submit',event=>{
 event.preventDefault();const input=byId('pin-demo-name'),name=input.value.trim();
 if(!name){input.setCustomValidity('Escreva um nome para o marcador.');input.reportValidity();return}
 input.setCustomValidity('');const card=document.createElement('article');card.className='post-it';
 const title=document.createElement('h3');title.textContent=name;
 const coords=document.createElement('p');coords.className='numbers';coords.textContent='X 2382 · Z 385 / Overworld';
 card.append(title,coords);byId('demo-pins').replaceChildren(card);input.value='';byId('pin-status').textContent='Anotado na amostra. Recarregar restaura o exemplo inicial.';
});
byId('pin-demo-name').addEventListener('input',event=>event.currentTarget.setCustomValidity(''));
byId('time-demo').addEventListener('input',event=>{
 const minutes=60-Number(event.currentTarget.value);byId('time-demo-label').textContent=minutes?`Há ${minutes} min`:'Agora';
});
const chikoMessages={lendo:'Só mais uma página…',folheando:'Estou procurando no caderno!',dormindo:'Cadê o jogador? Zzz…',animado:'Achei uma página nova!',confuso:'Esta página ficou confusa…'};
document.querySelectorAll('[data-chiko]').forEach(button=>button.addEventListener('click',()=>{
 const state=button.dataset.chiko;
 for(const item of document.querySelectorAll('[data-chiko]'))item.setAttribute('aria-pressed',String(item===button));
 byId('chiko-state-name').textContent=state;byId('chiko-slot').setAttribute('aria-label',`Espaço reservado para Chiko ${state}`);byId('chiko-bubble').textContent=chikoMessages[state];
}));
