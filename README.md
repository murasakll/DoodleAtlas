# Chiko · Bedrock Real-Time Map Viewer

Mapa web local para Minecraft Bedrock no Windows: superfície observada, jogadores ao vivo e cartografia em pixel art. O host executa o servidor; amigos acessam pelo navegador na mesma LAN.

## Instalação

1. Execute instalar.bat para preparar Python portátil e dependências em runtime/.
2. Copie config.example.json para config.json. Preencha world com o caminho do seu mundo; mundos.py lista os mundos locais.
3. Ajuste allowed_networks e lan_url para sua rede. Defina pin se desejar autenticação. HTTP e Minecraft devem usar portas distintas.
4. Execute iniciar.bat e abra http://127.0.0.1:8080/. Encerre com parar.bat.

A instalação não configura Firewall ou roteador automaticamente. O servidor se destina a uma LAN de confiança; não o exponha diretamente à internet.

## Captura ao vivo

O parser lê snapshots descartáveis do save. O terreno salvo tem prioridade sobre a captura do pack. Camas e portais são procurados também sob telhados e atualizam pela leitura periódica do save.

Para posições e capturas ao vivo, prepare o behavior pack para o mundo escolhido. Salve e feche o mundo antes de instalar/ativar o pack e mantenha sua própria cópia do save.

No PowerShell, execute: runtime/python/python.exe -X utf8 prepare_pack.py "IDENTIFICADOR_DA_PASTA_DO_MUNDO="

O comando produz fallback/BedrockLiveMap.mcpack sem instalá-lo. Importe-o no Minecraft, ative-o no mundo escolhido e habilite a gravação do Content Log nas opções de criador. Esse transporte não exige /connect.

O comando /livemap:taxa 1 64 300 configura posições a cada 1 s, até 64 leituras/tick e revisita após 300 s. PCs mais fracos devem usar valores baixos. O comando altera a sessão; reabrir o mundo pode restaurar o padrão conservador.

## Recursos

- Mapa em tela cheia, painéis recolhíveis, zoom e gestos de toque.
- Cores naturais e modo Atlas, contornos de construções observadas, camas e portais.
- Tiles WebP sob demanda, pirâmide de zoom e cache limitado; jogadores e entidades em overlay.
- Waypoints, desenho, carimbos, construção modular e avatares personalizáveis.
- Temas claro/escuro/sistema, exportação da área enquadrada e histórico em baixa resolução quando habilitado.
- Persistência por mundo em mapas/, conforme a configuração.

A prévia opcional pela seed é **experimental**, limitada às versões/dimensões reconhecidas pelo adaptador. Prevê biomas, não construções do jogador, estruturas comprovadas ou alturas exatas. Consulte vendor/seed-generator/NOTICE.txt. O binário Windows x64 acompanha fontes e licenças; build_seed_generator.py permite reconstruí-lo.

## Desenvolvimento

server.py serve API/site; terrain.py lê snapshots; tile_pipeline.py gera tiles; web/ contém interface/editores; fallback/behavior_pack/ contém o pack. A paleta é editável em paleta.json.

Após preparar config.json, uma verificação direcionada é: runtime/python/python.exe -X utf8 -m unittest discover -s tests -p test_observed_points.py -v

O comando node tests/web_smoke.mjs requer Node instalado separadamente e usa DOM/canvas simulados. Não comprova funcionamento real no jogo ou no celular.

Configurações pessoais, runtime/, data/, mapas/, logs, relatórios locais e mundos exportados ficam fora do Git. Para copiar bancos SQLite abertos, use a API SQLite de backup; copiar apenas .sqlite pode ignorar dados no WAL.

## Créditos e licenças

Arte do Atlas: **Antique Atlas / Hunternif**, adaptada para tinta e papel, sob **CC BY-NC-SA 3.0**: atribuição, uso não comercial e compartilhamento das adaptações da arte sob a mesma licença. Exportações desse modo incluem créditos. Não há afiliação ou endosso dos autores originais.

Consulte [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [o manifesto da arte](third_party/antique_atlas/manifest.json), as licenças MIT em vendor/seed-generator/ e a licença OFL em web/assets/. Essas licenças possuem escopos distintos e não constituem uma licença única de todo o código do projeto.
