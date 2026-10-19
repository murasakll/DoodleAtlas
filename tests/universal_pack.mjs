import fs from 'node:fs/promises';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';

export async function run(){
 const source=(await fs.readFile(new URL('../src/chiko/bedrock_pack/scripts/main.js',import.meta.url),'utf8')).replace(/^import .*;\r?\n/gm,'');
 const saved=new Map(),commands=new Map(),intervals=[],packets=[];
 const world={getDynamicProperty:k=>saved.get(k),setDynamicProperty:(k,v)=>saved.set(k,v),getAllPlayers:()=>[],getDimension:()=>({getEntities:()=>[]})};
 const system={currentTick:40,run:f=>f(),runInterval:f=>intervals.push(f),afterEvents:{scriptEventReceive:{subscribe(){}}},beforeEvents:{startup:{subscribe:f=>f({customCommandRegistry:{registerCommand:(meta,callback)=>commands.set(meta.name,{meta,callback})}})}}};
 const mc={CommandPermissionLevel:{Any:0,GameDirectors:1},CustomCommandParamType:{String:1,Float:2,Integer:3},CustomCommandStatus:{Success:0,Failure:1}};
 const CaptureQueue=class{constructor(){this.revisitTicks=6000}probe(){}next(){return null}};
 function open(){const box={world,system,mc,CaptureQueue,WORLD_ID:'',console:{warn:line=>packets.push(JSON.parse(line.split('[BEDROCK_LIVE_MAP]')[1]))}};vm.createContext(box);vm.runInContext(source,box);return box}
 let box=open();intervals[0]();if(packets.at(-1).worldId!=='')throw Error('Universal pack invented a world binding');
 const binding=commands.get('livemap:vincular');if(binding.meta.permissionLevel!==1)throw Error('Binding must require a game director');
 if(binding.callback({},'wrong').status!==1||saved.size)throw Error('Invalid binding was persisted');
 const id='a'.repeat(64);binding.callback({},id);intervals[0]();if(packets.at(-1).worldId!==id)throw Error('New binding not applied');
 intervals.length=0;box=open();intervals[0]();if(packets.at(-1).worldId!==id)throw Error('Binding did not survive world reload');
 const other='b'.repeat(64);commands.get('livemap:vincular').callback({},other);intervals[0]();if(packets.at(-1).worldId!==other)throw Error('Rebinding did not apply');
 return {startup:'OK',director_permission:'OK',validation:'OK',persistent_binding:'OK',rebind:'OK',scope:'Script API simulated; real Minecraft pending'};
}
if(typeof process!=='undefined'&&process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)console.log(await run());
