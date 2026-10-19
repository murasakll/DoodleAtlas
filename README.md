<p align="center"><img src="src/chiko/assets/branding/doodleatlas-icon.png" alt="Mapa desenhado à mão com Chiko segurando o canto" width="220"></p>

# DoodleAtlas

**Seu mundo, guardado entre mapas e rabiscos.**

DoodleAtlas é uma ferramenta de cartografia interativa para **Minecraft Bedrock**. A interface parece um caderno feito à mão: papel, traços em preto e branco, bordas sketch animadas e detalhes em ciano. O terreno pode aparecer como atlas ilustrado ou com as cores naturais do Minecraft e relevo.

**Chiko é o bibliotecário do atlas.** Ele acompanha a exploração e guarda os mapas e registros das suas aventuras. O personagem é de [Hachiko / Noah](https://www.tiktok.com/@hachikookami).

[Guia](docs/GUIA.md) · [Galeria](docs/GALERIA.md) · [Estrutura completa](docs/ESTRUTURA.md) · [Contribuir](docs/CONTRIBUINDO.md)

## Destaques

- **Caderno doodle:** temas claro, escuro e automático, bordas sketch e sons opcionais.
- **Dois estilos de terreno:** Atlas ilustrado ou Minecraft com cores naturais e relevo.
- **Editor manual:** pincéis, estradas e cercas conectáveis, carimbos, pintura de fundo e construções modulares.
- **Três dimensões:** Overworld, Nether e End.
- **Jogadores ao vivo:** posição e entidades quando o pack envia os dados do jogo.
- **Lugares e personagens:** pontos pessoais ou compartilhados, presets e envio manual de skin/rosto PNG.
- **Registros por mundo:** desenhos, histórico por chunk e quadros de uma região principal escolhida.
- **Exportação PNG:** área enquadrada com título, norte, escala e anotações opcionais.
- **Seed opcional:** previsão experimental sempre atrás do terreno observado.

## Por dentro do caderno

Os prints mostram a interface funcionando com **dados fictícios de demonstração**. Não são um save real nem uma medição de desempenho. O ícone é uma adaptação gerada com IA da referência do Chiko.

| Atlas de papel | Editor cartográfico |
| --- | --- |
| ![Mapa ilustrado](docs/images/01-atlas.png) | ![Ferramentas de desenho](docs/images/02-editor.png) |
| Lugares compartilhados | Cores naturais |
| ![Lugares no mapa](docs/images/03-lugares.png) | ![Modo Minecraft](docs/images/04-minecraft.png) |

[Ver histórico e tema noturno](docs/GALERIA.md).

## Estrutura do projeto

```text
DoodleAtlas/
├── src/chiko/          Código; nome técnico mantido por compatibilidade
│   ├── network/        Conexão e protocolo
│   ├── world/          Descoberta e leitura do save
│   ├── storage/        Dados, desenhos e histórico
│   ├── cartography/    Paleta, relevo e tiles
│   ├── web/            Interface, mapa e editor
│   ├── assets/         Ícone, mascote, fonte e arte do atlas
│   ├── bedrock_pack/   Addon para os dados ao vivo
│   └── vendor/         Seed opcional e licenças
├── config/             Exemplo público e configuração local ignorada pelo Git
├── docs/               Guia e prints das funções
├── scripts/            Instalação e ferramentas de desenvolvimento
├── tests/              Testes e simulações
├── instalar.bat        Preparar Python portátil no Windows
├── iniciar.bat         Abrir o servidor
├── parar.bat           Encerrar o aplicativo
├── pyproject.toml      Pacote e comandos
├── requirements.txt    Dependências Python
├── THIRD_PARTY_NOTICES.md
├── LICENSE
└── README.md
```

Os assets ficam dentro do pacote para acompanhar a instalação. Mundos, capturas, tokens, logs e configurações pessoais ficam fora do Git.

## Instalar e rodar

O ambiente preparado é **Windows x64 com Python 3.12**. O pack declara engine mínima **1.26.50** e Script API **2.9.0**; isso não garante versões futuras. O gerador nativo de seed é opcional e voltado a Windows x64.

```powershell
git clone https://github.com/murasakll/Bedrock-Real-Time-Map-Viwer.git DoodleAtlas
cd DoodleAtlas
```

### Instalação simples no Windows

Execute `instalar.bat` e depois `iniciar.bat`. O instalador baixa Python e dependências para `runtime/` e gera `dist/Chiko-Universal.mcpack`. Abra o endereço mostrado no terminal.

Para dados ao vivo, importe o `.mcpack`, ative-o no mundo e faça o vínculo em **Ajustes → Leitura e captura do jogo**. Salve e saia do mundo antes de instalar ou atualizar o pack. Use `parar.bat` para encerrar.

### Com seu Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
python -m chiko init
python -m chiko worlds
python -m chiko pack
python -m chiko serve --world "worlds/MeuMundo"
```

Substitua `worlds/MeuMundo` pelo caminho do seu save. O módulo `chiko` e o nome do pack foram mantidos por compatibilidade; o projeto se chama **DoodleAtlas**.

### Configurar mundo, endereço e portas

`python -m chiko init` cria **config/settings.local.json** a partir do exemplo, sem sobrescrever suas escolhas. Ajuste os campos necessários:

```json
{
  "world": "worlds/MeuMundo",
  "http_host": "0.0.0.0",
  "http_port": 8080,
  "advertise_host": "auto"
}
```

O trecho mostra apenas os campos a ajustar; preserve os demais campos do arquivo criado. `0.0.0.0` permite escutar nas interfaces do PC. `auto` detecta o endereço anunciado. No próprio PC, use o endereço local exibido; no celular, o endereço LAN do PC e a mesma porta. **127.0.0.1 é válido para acesso local**, mas em outro aparelho aponta para aquele aparelho.

A conexão do Minecraft tem campos separados: `minecraft_host`, `minecraft_port` e `minecraft_advertise_host`. O padrão local atende ao jogo no mesmo PC. Um IP externo sozinho não fornece o save nem o log de outro servidor. [Rede, PIN e diagnóstico](docs/GUIA.md).

## Limites e dados

O leitor trabalha com snapshots descartáveis do save. O pack lê apenas o terreno acessível no jogo; a seed é previsão, não confirmação de construções. O histórico registra mudanças observadas, não reconstrói o passado. A região principal aceita até **4.096 chunks** e tem limites de armazenamento.

Configurações locais, `data/`, `mapas/`, `logs/` e mundos não acompanham o repositório. Para preservar bancos SQLite abertos, siga o [procedimento de backup](docs/GUIA.md#dados-e-backup). Não há promessa de ganho de FPS ou suporte automático a qualquer Realm/servidor público.

## Desenvolvimento

```powershell
python -m unittest discover -s tests -v
node tests/web_smoke.mjs
```

Os testes usam dados temporários e simulações. Consulte [como contribuir](docs/CONTRIBUINDO.md) para as demais verificações.

## Créditos e agradecimentos

- **Projeto e código:** [murasakll](https://github.com/murasakll).
- **Personagem Chiko:** [Hachiko / Noah](https://www.tiktok.com/@hachikookami). No DoodleAtlas, ele assume o papel de bibliotecário dos mapas e registros. A pixel art e as ilustrações de apresentação são adaptações geradas com IA a partir das referências fornecidas.
- **Arte do Atlas:** [Antique Atlas / Hunternif e colaboradores](https://github.com/AntiqueAtlasTeam/AntiqueAtlas), sob **CC BY-NC-SA 3.0**.
- **Fonte manuscrita:** Caveat, distribuída localmente sob **SIL OFL 1.1**.
- **Seed opcional:** Cubiomes / Cubitect e SeedForge, com licenças MIT próprias.
- **Bibliotecas:** Amulet Core, aiohttp, Pillow, qrcode e cryptography.

[Licenças, atribuições e alterações de terceiros](THIRD_PARTY_NOTICES.md).

## Licença

O código autoral do **DoodleAtlas** é distribuído sob a [licença MIT](LICENSE): você pode usar, modificar e distribuir esse código mantendo o aviso de autoria e a licença.

A MIT **não substitui as licenças das dependências, fontes e artes**. A arte do Antique Atlas mantém **CC BY-NC-SA 3.0**, inclusive a condição não comercial. O personagem Chiko pertence a Hachiko / Noah e não recebeu licença aberta neste repositório.

Projeto independente, sem afiliação ou endosso da Mojang, Microsoft ou Antique Atlas.
