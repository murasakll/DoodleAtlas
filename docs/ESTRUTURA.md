# Estrutura do projeto

[Voltar à apresentação](../README.md)

A raiz guarda a apresentação, o empacotamento e três atalhos do Windows. O código Python do aplicativo fica em **src/chiko/**. Dados locais e estudos de design não acompanham a publicação.

~~~text
DoodleAtlas/
├── .github/                 Modelos de issues e pull requests
├── config/
│   ├── settings.example.json  Configuração pública, sem um save escolhido
│   └── requirements-lock.txt Referência das dependências
├── docs/
│   ├── images/              Capa, prints e brief da ilustração
│   ├── GUIA.md              Instalação, pack, rede e uso
│   ├── GALERIA.md           Prints com dados sintéticos
│   ├── CONTRIBUINDO.md      Fluxo de contribuição
│   └── ESTRUTURA.md         Este documento
├── scripts/
│   ├── install.ps1          Instalador portátil Windows
│   ├── stop.ps1             Encerramento do serviço
│   └── capture_gallery.py   Prints isolados da documentação
├── src/chiko/
│   ├── __main__.py          Comandos: init, worlds, serve, pack, stop
│   ├── server.py            HTTP, SSE, autorização e coordenação
│   ├── settings.py          Configuração e variáveis de ambiente
│   ├── paths.py             Recursos do pacote e dados locais
│   ├── network/             Content Log, protocolo e criptografia
│   ├── world/               Descoberta, snapshot e leitura do save
│   ├── storage/             Superfícies, pontos, desenhos e histórico
│   ├── cartography/         Paleta, relevo, tiles, Atlas e seed opcional
│   ├── tools/               Pack universal, auditoria e build da seed
│   ├── web/                 Mapa, editor, histórico e UI do caderno
│   ├── assets/
│   │   ├── antique_atlas/   Arte, manifesto e licenças
│   │   ├── branding/        Ícone do DoodleAtlas
│   │   ├── chiko/           Mascote em pixel art
│   │   └── web/             Fonte local e molduras
│   ├── bedrock_pack/        Manifesto e scripts do addon universal
│   └── vendor/seed-generator/ Fontes, licenças e DLL opcional
├── tests/                   Fixtures e simulações isoladas
├── iniciar.bat
├── instalar.bat
├── parar.bat
├── pyproject.toml
├── requirements.txt
├── THIRD_PARTY_NOTICES.md
└── README.md
~~~

## Fluxo dos dados

~~~mermaid
flowchart LR
  A[Save Bedrock] --> B[Snapshot descartável]
  B --> C[Leitor do terreno]
  D[Behavior pack] --> E[Content Log]
  E --> F[Servidor local]
  C --> F
  F --> G[Dados e histórico por mundo]
  G --> H[Tiles sob demanda]
  H --> I[Navegador]
  F -->|SSE| I
  J[Seed opcional e experimental] --> I
  I --> K[Camada desenhada e pontos]
~~~

O terreno real tem prioridade sobre previsões. Jogadores, entidades e anotações são overlays; não fazem parte dos tiles de terreno. A UI do caderno está nos arquivos **caderno-preview.css/js**: o nome veio da etapa de estudo, mas eles já são carregados pela página principal. **caderno.html** é apenas um endereço compatível da mesma interface.

## Fora do repositório

| Local | Conteúdo |
| --- | --- |
| config/settings.local.json | Seu mundo, PIN e escolhas deste PC |
| runtime/ | Python, dependências e ferramentas instaladas |
| data/, mapas/, logs/ | Sessões, capturas, bancos, histórico e logs |
| dist/, build/ | Pack e artefatos de build gerados |
| Documentos/, docs/propostas/ | Estudos e relatórios locais de desenvolvimento |
| src/chiko/_local/ | Diagnósticos privados preservados localmente |

Esses diretórios são ignorados pelo Git. Seus conteúdos não devem ser usados como dependências ocultas do aplicativo publicado. O instalador gera o pack; não é preciso copiar um pacote de um mundo específico para outra máquina.

O guia contém [instruções de dados e backup](GUIA.md#dados-e-backup). Não publique arquivos de controle efêmeros, PIN, tokens ou dumps de mundos para facilitar uma instalação.
