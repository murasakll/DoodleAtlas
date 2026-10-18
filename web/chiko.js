'use strict';
globalThis.Chiko=class Chiko{
 constructor({slot,label,bubble}){this.slot=slot;this.label=label;this.bubble=bubble;this.state='';this.messages={lendo:'Só mais uma página…',folheando:'Estou folheando o caderno!',dormindo:'Cadê o jogador? Zzz…',animado:'Achei uma página nova!',confuso:'Esta página ficou confusa…'}}
 setState(state,message=this.messages[state]){if(!this.messages[state]||(state===this.state&&message===this.message))return;this.state=state;this.message=message;this.label.textContent=state;this.bubble.textContent=message;this.slot.setAttribute('aria-label',`Espaço reservado para Chiko ${state}`)}
};
