import argparse
import asyncio
import json
import logging
from logging.handlers import RotatingFileHandler
from chiko.paths import ROOT


def main():
    parser = argparse.ArgumentParser(prog='python -m chiko')
    commands = parser.add_subparsers(dest='command')
    serve = commands.add_parser('serve',help='Abrir o servidor do mapa')
    serve.add_argument('--config');serve.add_argument('--world');serve.add_argument('--http-host');serve.add_argument('--http-port',type=int)
    commands.add_parser('init',help='Criar configuração local, sem sobrescrever')
    commands.add_parser('worlds',help='Listar mundos encontrados neste computador')
    pack = commands.add_parser('pack',help='Gerar o pack universal ou associado a um mundo')
    pack.add_argument('--world',help='Identificador opcional do mundo para um pack já vinculado')
    pack.add_argument('--output',help='Caminho do arquivo .mcpack')
    commands.add_parser('stop',help='Solicitar encerramento ao servidor local')
    commands.add_parser('verify',help='Verificar HTTP do servidor configurado')
    commands.add_parser('build-seed',help='Reconstruir gerador opcional Windows x64')
    args = parser.parse_args()
    if args.command=='init':
        from chiko.settings import initialize
        print(initialize());return
    if args.command=='worlds':
        from chiko.world.discovery import discover
        print(json.dumps(discover(),ensure_ascii=False,indent=2));return
    if args.command=='pack':
        from chiko.tools.pack import build
        print(build(args.world,args.output));return
    if args.command=='build-seed':
        from chiko.tools.build_seed_generator import main as build
        build();return
    if args.command=='stop':
        from urllib.request import Request,urlopen
        control=ROOT/'data'/'control.json'
        if not control.exists():raise SystemExit('Nenhum servidor local registrado.')
        info=json.loads(control.read_text(encoding='utf-8'))
        from chiko.settings import url
        address=info.get('url') or url('localhost',info['port'])
        request=Request(address+'/api/shutdown',data=b'',headers={'X-Host-Token':info['token']},method='POST')
        with urlopen(request,timeout=5) as response:print('Servidor avisado. Fechando o caderno.')
        return
    if args.command=='verify':
        from chiko.tools.verify import verify
        asyncio.run(verify());return
    from chiko.settings import initialize,load
    initialize()
    overrides={k:getattr(args,k,None) for k in ('world','http_host','http_port') if getattr(args,k,None) is not None}
    try:settings=load(getattr(args,'config',None),overrides)
    except (ValueError,OSError) as error:raise SystemExit(str(error))
    (ROOT/'logs').mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',handlers=[logging.StreamHandler(),RotatingFileHandler(ROOT/'logs/server.log',maxBytes=1024*1024,backupCount=2,encoding='utf-8')])
    from chiko.server import main as serve_map
    try:asyncio.run(serve_map(settings))
    except KeyboardInterrupt:pass


if __name__=='__main__':main()
