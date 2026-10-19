<p align="center"><img src="src/chiko/assets/branding/doodleatlas-icon.png" alt="Mapa desenhado à mão com Chiko segurando o canto" width="200"></p>

<h1 align="center">DoodleAtlas</h1>
<p align="center"><b>Seu mundo, guardado entre mapas e rabiscos.</b></p>
<p align="center"><b>Português</b> · <a href="README.en.md">English</a></p>
<p align="center"><a href="docs/GUIA.md">Guia</a> · <a href="docs/GALERIA.md">Galeria</a> · <a href="docs/ESTRUTURA.md">Estrutura</a> · <a href="docs/CONTRIBUINDO.md">Contribuir</a></p>

Mapa interativo para **Minecraft Bedrock** com cara de caderno feito à mão. Veja seu mundo e seus jogadores no navegador, desenhe sua vila por cima e exporte tudo como imagem.

**Chiko é o bibliotecário do atlas:** ele acompanha a exploração e guarda os mapas e registros. O personagem é de [Hachiko / Noah](https://www.tiktok.com/@hachikookami).

| Atlas de papel | Editor cartográfico |
| --- | --- |
| ![Mapa ilustrado](docs/images/01-atlas.png) | ![Ferramentas de desenho](docs/images/02-editor.png) |
| **Lugares compartilhados** | **Cores naturais** |
| ![Lugares no mapa](docs/images/03-lugares.png) | ![Modo Minecraft](docs/images/04-minecraft.png) |

<sub>Prints com dados fictícios de demonstração, não de um save real. O ícone é uma adaptação gerada com IA da referência do Chiko. [Ver mais na galeria](docs/GALERIA.md).</sub>

## O que você pode fazer

- **Ver o mundo no navegador:** roda no seu PC e abre também no celular, pela mesma rede. O terreno vem do próprio save, mesmo sem ninguém online, a partir de uma cópia temporária que não mexe no banco original.
- **Acompanhar jogadores ao vivo:** um behavior pack envia posições e amostras do terreno pelo Content Log.
- **Escolher o visual:** terreno em estilo Atlas (arte do Antique Atlas) ou Minecraft (cores naturais e relevo), nas três dimensões: Overworld, Nether e End.
- **Desenhar sobre o mapa:** pincéis, estradas e cercas que se conectam sozinhas, carimbos de casas, templos e moinhos, pintura de fundo e construções modulares. Os desenhos são anotações e não alteram o jogo.
- **Marcar lugares e personagens:** pontos pessoais ou compartilhados, camas e portais detectados automaticamente, presets de aparência e envio de skin ou rosto em PNG.
- **Ver a evolução da região:** versões de chunks e quadros de uma região principal de até 4.096 chunks.
- **Exportar:** PNG da área enquadrada, com título, norte, escala e anotações opcionais, ou JSON da edição.
- **Prever biomas (experimental):** a seed aparece sempre por baixo do terreno realmente observado.
- **Personalizar:** tema claro, escuro ou automático, bordas sketch animadas, sons opcionais e interface em português e inglês.

## Começar

**Você precisa de:** Windows x64 e Minecraft Bedrock. O instalador baixa o Python 3.12 e as dependências sozinho.

```powershell
git clone https://github.com/murasakll/Bedrock-Real-Time-Map-Viwer.git DoodleAtlas
cd DoodleAtlas
```

1. Execute **`instalar.bat`**. Ele prepara o Python em `runtime/` e gera `dist/Chiko-Universal.mcpack`.
2. Execute **`iniciar.bat`** e abra o endereço mostrado no terminal.
3. Escolha seu mundo no seletor do site.

Para parar, use `parar.bat`. Para abrir no celular, use o endereço do PC na rede local, com a mesma porta.

### Ativar jogadores ao vivo

1. Salve e saia do mundo.
2. Importe `dist/Chiko-Universal.mcpack` no Minecraft e ative o pack no mundo, desativando versões antigas.
3. Ative a gravação do Content Log nas opções de criador.
4. Abra o mundo e, no site, vá em **Ajustes → Leitura e captura do jogo** para copiar o comando de vínculo.
5. No chat, como host ou operador, execute `/livemap:vincular ...` com o identificador mostrado.

A taxa de captura se ajusta com `/livemap:taxa`. O guia explica cada valor.

<details>
<summary><b>Instalar com seu próprio Python</b></summary>

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

Troque `worlds/MeuMundo` pelo caminho do seu save. O módulo `chiko` e o nome do pack são nomes antigos mantidos por compatibilidade.
</details>

<details>
<summary><b>Configurar mundo, endereço e portas</b></summary>

`python -m chiko init` cria `config/settings.local.json` sem sobrescrever o que você já tem:

```json
{
  "world": "worlds/MeuMundo",
  "http_host": "0.0.0.0",
  "http_port": 8080,
  "advertise_host": "auto"
}
```

`0.0.0.0` faz o servidor escutar na rede, mas não é o endereço que se digita. No próprio PC use `127.0.0.1`. No celular, use o endereço do PC na rede local e a mesma porta. A conexão do Minecraft usa campos separados (`minecraft_host`, `minecraft_port` e `minecraft_advertise_host`). Mais detalhes sobre rede, PIN e diagnóstico estão no [guia](docs/GUIA.md).
</details>

## O que ele não faz

- **Não altera o jogo:** desenhos e construções são anotações do atlas.
- **Não mostra localizações pela seed:** ela é apenas uma previsão de biomas.
- **Não acessa Realms ou servidores públicos automaticamente:** ter o IP de um servidor remoto não dá acesso ao save nem ao log dele.
- **Não promete compatibilidade com versões futuras do Minecraft.** O pack declara engine mínima **1.26.50** e Script API **2.9.0**.

Mundos, capturas, `data/`, `mapas/`, `logs/` e configurações pessoais ficam fora do Git. Para fazer backup de bancos SQLite abertos, veja o [procedimento no guia](docs/GUIA.md#dados-e-backup).

## Desenvolvimento

```powershell
python -m unittest discover -s tests -v
node tests/web_smoke.mjs
```

Os testes usam dados temporários e simulações. Veja [como contribuir](docs/CONTRIBUINDO.md) e a [estrutura do projeto](docs/ESTRUTURA.md). Para dar seu tom aos textos e às traduções, consulte [onde editar](docs/TEXTOS.md).

## Créditos

- **Projeto e site:** [murasakll](https://github.com/murasakll) criou o site e a interface.
- **Lógica do mapa:** a maior parte foi desenvolvida com [ChatGPT (OpenAI)](https://openai.com/) e [Claude (Anthropic)](https://www.anthropic.com/).
- **Personagem Chiko:** [Hachiko / Noah](https://www.tiktok.com/@hachikookami). O personagem pertence a ele, imagem em pixel art temporaria.
- **Arte do Atlas:** [Antique Atlas / Hunternif e colaboradores](https://github.com/AntiqueAtlasTeam/AntiqueAtlas)
- **Fonte manuscrita:** Caveat
- **Previsão de mapa:** Cubiomes / Cubitect e SeedForge
- **Bibliotecas:** Amulet Core, aiohttp, Pillow, qrcode e cryptography

## Licença

O código autoral é distribuído sob a [licença MIT](LICENSE).

A MIT não cobre dependências, fontes e artes de terceiros: a arte do Antique Atlas segue **CC BY-NC-SA 3.0**, inclusive a condição não comercial, e a fonte Caveat segue **SIL OFL 1.1**. O personagem Chiko pertence a Hachiko / Noah e não recebeu licença aberta neste repositório. Detalhes em [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

Projeto independente, sem afiliação ou endosso da Mojang, Microsoft ou Antique Atlas.