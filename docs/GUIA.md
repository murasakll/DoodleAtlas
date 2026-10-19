# Usar o DoodleAtlas

[Voltar à apresentação](../README.md)

## Instalação

No Windows x64, execute `instalar.bat` e depois `iniciar.bat`. O instalador baixa Python e dependências para `runtime/`; precisa de internet nessa etapa. Ele não altera Firewall, roteador ou isolamento de rede do Minecraft.

Com Python próprio, use 3.12 e `python -m pip install -e .`. As dependências diretas estão em `requirements.txt`; `config/requirements-lock.txt` guarda uma referência completa de versões.

O gerador de seed opcional é uma DLL Windows x64 com fontes e licenças em `src/chiko/vendor/seed-generator/`. Sua previsão de biomas Bedrock é experimental. O mapa observado continua disponível sem a previsão.

## Escolher um mundo

Em `config/settings.local.json`, preencha `world` com seu caminho. O arquivo é local e não deve ser publicado. Caminhos relativos usam a pasta do projeto como base; `~/` e caminhos externos próprios também são aceitos.

```powershell
python -m chiko worlds
python -m chiko serve --world "worlds/MeuMundo"
```

Um único mundo encontrado pode ser selecionado automaticamente. Havendo vários, escolha explicitamente. No PC do host, o seletor no canto superior esquerdo troca o mundo. Visitantes não podem fazer essa troca.

## Instalar o pack universal

1. Salve e saia do mundo.
2. Abra `dist/Chiko-Universal.mcpack` para importar no Minecraft. Se precisar gerá-lo: `python -m chiko pack`.
3. Desative o pack antigo naquele mundo e ative o universal. Evite duas capturas concorrentes.
4. Habilite a gravação do Content Log nas opções de criador do Minecraft.
5. Inicie o mundo. No site, escolha o mesmo save e abra **Ajustes → Leitura e captura do jogo**.
6. Copie o comando `/livemap:vincular ...` e execute no chat como host/operador.

O mesmo arquivo serve para mundos compatíveis; cada mundo recebe seu vínculo explícito. Se mover o save para outra pasta ou computador, vincule novamente. O pack declara engine mínima 1.26.50 e Script API 2.9.0.

Para experimentar uma taxa maior:

```text
/livemap:taxa 1 64 300
```

Significa posições a cada 1 s, até 64 sondagens por tick e revisita após 300 s. Não significa 64 chunks por tick e não carrega chunks. A escolha vale na sessão; ao reabrir o mundo pode voltar ao padrão conservador. Comece com taxas baixas em PCs mais fracos.

## Rede e PIN

O terminal informa o endereço local e o da LAN. No mesmo PC, use o endereço local. No celular, use o endereço LAN do host, estando na mesma rede.

| Campo em settings.local.json | Uso |
| --- | --- |
| `http_host` / `http_port` | Interface de escuta e porta; padrão `0.0.0.0:8080`. |
| `advertise_host` | `auto` procura um IPv4 privado; pode ser ajustado para VPN ou várias placas. |
| `allowed_networks` | Redes autorizadas a abrir o site. |
| `pin` | PIN para autenticar visitantes. Sem PIN, visitantes não ganham escrita só por abrir o mapa. |
| `content_log` | `auto` ou caminho do Content Log legível neste PC. |
| `terrain_seconds` | Intervalo mínimo do leitor do save. |
| `minecraft_host` / `minecraft_port` | WebSocket opcional; não é o transporte principal desta instalação. |

`localhost` e loopback são corretos no PC que hospeda o mapa. O projeto não abre portas no roteador nem libera Firewall automaticamente. Informar o IP de um servidor remoto não permite ler seus arquivos.

Variáveis `CHIKO_WORLD`, `CHIKO_HTTP_HOST`, `CHIKO_HTTP_PORT`, `CHIKO_ADVERTISE_HOST`, `CHIKO_MINECRAFT_HOST`, `CHIKO_MINECRAFT_PORT`, `CHIKO_PIN` e `CHIKO_CONTENT_LOG` substituem campos da configuração. `CHIKO_HOME` escolhe a pasta dos dados locais.

## Navegar, desenhar e exportar

- Arraste, use a roda ou faça pinça para navegar. As dimensões ficam no topo.
- **Mapa** escolhe Atlas/Minecraft, tema e camadas. **Pessoas** permite seguir um jogador.
- **Lugares** guarda pontos pessoais ou compartilhados. Os pessoais usam o armazenamento do navegador.
- **Desenho** reúne carimbos, caminhos e pintura. **Construir** monta uma planta por peças. A camada desenhada é independente dos blocos do jogo.
- **Foco** recolhe ferramentas; `Esc` traz a interface de volta e encerra a edição conforme o editor.
- **Exportar** baixa PNG da área enquadrada. Para enquadrar todo o terreno conhecido, use **Ver mapa** antes. A previsão da seed, jogadores e entidades ficam fora da exportação.

Sons são opcionais, iniciados após um clique em **Ativar sons**. Movimento reduzido do sistema pausa o sketch. Dormir e entrar numa caverna ainda não têm detecção real integrada ao mascote.

## Histórico de uma região

No PC do host, abra **Histórico**. Enquadre uma área, clique em **Usar área visível do mapa** e depois em **Guardar região principal**. Também pode informar os quatro limites, em múltiplos de 16 blocos.

O limite é 4.096 chunks. Se a vista ultrapassar isso, aproxime o mapa ou reduza os limites. Depois use **Registrar quadro agora**, ou habilite o intervalo automático.

O registro automático fica parado enquanto não houver região principal. A região é salva por mundo; mudanças dos chunks são guardadas separadamente e deduplicadas por conteúdo. Os quadros não incluem seed, entidades ou jogadores. O painel mostra quadros do mesmo recorte para manter a reprodução estável; quadros antigos de outros recortes continuam sujeitos à cota e à retenção existentes.

## Dados e backup

`data/`, `mapas/` e `logs/` ficam na pasta de dados do aplicativo. Não acompanham o repositório. A pasta de cada mundo reúne armazenamento persistente; caches temporários e sessões podem ficar em `data/`.

Para um backup manual simples, salve e saia do Minecraft. Preserve os dados de sessão antes de encerrar o aplicativo, pois sessões temporárias podem ser removidas no encerramento. Bancos SQLite abertos devem ser copiados pela API `sqlite3.Connection.backup`; copiar só o `.sqlite` pode omitir o WAL. Com o aplicativo fechado e os bancos devidamente encerrados, copie a pasta do mundo e a configuração local. Não reaproveite `data/control.json` antigo: ele contém controle efêmero do processo.

Pontos pessoais usam o navegador e não entram no backup do servidor automaticamente. Guarde a exportação JSON da edição quando precisar transportar o desenho. O projeto não apaga seu save original para limpar o mapa.

## Se algo não aparecer

| Sintoma | Conferir |
| --- | --- |
| Terreno aparece, jogador não | Pack ativo, Content Log habilitado e vínculo com o mesmo mundo. |
| Outro mundo recebe a captura | Desative packs antigos e refaça o vínculo explícito. |
| Celular não abre | Mesma rede, endereço LAN correto e regras locais de acesso. |
| Prévia de seed ausente | Versão/dimensão suportada pelo gerador opcional; ela não é necessária para terreno observado. |
| Histórico não registra | Região principal salva, permissão do host, orçamento e cota disponíveis. |
| Captura demora | Fila do pack, taxa selecionada, disponibilidade de chunks e persistência do save. Aumentar a taxa não elimina esses limites. |

Ao abrir uma issue, envie passos, versões e mensagens de erro. Não publique PIN, tokens, saves ou logs pessoais completos.
