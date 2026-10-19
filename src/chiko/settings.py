import ipaddress
import json
import os
import socket
from pathlib import Path
from chiko.paths import ROOT, SETTINGS, local_path

DEFAULTS = {
    'world': '', 'http_host': '0.0.0.0', 'http_port': 8080,
    'minecraft_host': '127.0.0.1', 'minecraft_port': 8081,
    'advertise_host': 'auto', 'minecraft_advertise_host': 'localhost',
    'terrain_seconds': 60, 'player_seconds': 1,
    'allowed_networks': ['127.0.0.0/8', '::1/128', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'],
    'minecraft_allowed_networks': ['127.0.0.0/8', '::1/128'],
    'pin': '', 'host_name': '', 'content_log': 'auto', 'debug_packets': False,
    'capture_persistent': True, 'capture_limit_mb': 64, 'resource_pack_roots': [],
}


def lan_address():
    candidates = []
    try:
        candidates = [row[4][0] for row in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
    except OSError:
        pass
    for candidate in candidates:
        address = ipaddress.ip_address(candidate)
        if address.is_private and not address.is_loopback and not address.is_link_local:
            return candidate
    return 'localhost'


def url(host, port, scheme='http'):
    host = str(host)
    if ':' in host and not host.startswith('['):host = '[' + host + ']'
    return f'{scheme}://{host}:{port}'


def normalize(values, base=ROOT, require_world=True):
    settings = {**DEFAULTS, **values}
    for key in ('http_port', 'minecraft_port'):
        value = settings[key]
        if isinstance(value, bool) or not str(value).isdigit() or not 1 <= int(value) <= 65535:
            raise ValueError(f'{key}: use uma porta de 1 a 65535')
        settings[key] = int(value)
    if settings['http_port'] == settings['minecraft_port']:raise ValueError('As duas portas precisam ser diferentes')
    for key in ('http_host', 'minecraft_host', 'advertise_host', 'minecraft_advertise_host'):
        value = str(settings[key])
        if not value or any(c.isspace() or c in '/?#@' for c in value):raise ValueError(f'{key}: informe apenas um host, sem URL')
    for key in ('allowed_networks','minecraft_allowed_networks'):
        if not isinstance(settings[key],list) or not settings[key]:raise ValueError(f'{key}: informe uma lista de redes')
        settings[key] = [str(ipaddress.ip_network(n,strict=False)) for n in settings[key]]
    for key, low, high in (('terrain_seconds',2,600),('player_seconds',.25,2)):
        if isinstance(settings[key],bool) or not low <= float(settings[key]) <= high:raise ValueError(f'{key}: valor fora do intervalo {low}–{high}')
    world = settings.get('world')
    if not world and require_world:
        from chiko.world.discovery import discover
        worlds = discover()
        if len(worlds) != 1:raise ValueError('Escolha o mundo em config/settings.local.json ou use: python -m chiko serve --world CAMINHO')
        world = worlds[0]['path']
    if world:
        world = local_path(world,Path(base))
        if require_world and (not (world/'level.dat').is_file() or not (world/'db').is_dir()):
            raise ValueError('O caminho escolhido não contém um save Bedrock (level.dat + db/)')
        settings['world'] = str(world)
    if settings['content_log'] not in ('auto','',None):settings['content_log'] = str(local_path(settings['content_log'],Path(base)))
    settings['resource_pack_roots'] = [str(local_path(p,Path(base))) for p in settings.get('resource_pack_roots',[])]
    host = settings['advertise_host']
    if host == 'auto':host = lan_address()
    settings['lan_url'] = url(host,settings['http_port'])
    local_host = settings['http_host']
    if local_host in ('0.0.0.0','::'):local_host = 'localhost'
    settings['local_url'] = url(local_host,settings['http_port'])
    settings['connect_url'] = url(settings['minecraft_advertise_host'],settings['minecraft_port'],'ws')
    return settings


def load(filename=None, overrides=None, require_world=True):
    path = local_path(filename) if filename else SETTINGS
    values = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    for key in ('world','http_host','http_port','minecraft_host','minecraft_port','advertise_host','pin','content_log'):
        env = os.environ.get('CHIKO_' + key.upper())
        if env is not None:values[key] = env
    return normalize({**values, **(overrides or {})},ROOT,require_world)


def initialize():
    SETTINGS.parent.mkdir(parents=True,exist_ok=True)
    if not SETTINGS.exists():SETTINGS.write_text(json.dumps(DEFAULTS,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return SETTINGS
