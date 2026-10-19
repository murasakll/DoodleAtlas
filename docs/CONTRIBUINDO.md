# Contribuir com o DoodleAtlas

Obrigado por ajudar a cuidar do caderno. Comece pelo [guia](GUIA.md) e pela [estrutura](ESTRUTURA.md).

## Relatar um problema

Abra uma issue com a versão do Minecraft, navegador e sistema, passos para reproduzir e o que aconteceu. Uma imagem ajuda. Remova PIN, tokens, caminhos pessoais e coordenadas que não queira publicar. Não envie o mundo inteiro para demonstrar um botão quebrado.

Separe comportamento real de simulação. Informe se o teste usou Minecraft aberto, um save fechado ou a galeria sintética.

## Alterações no código

- Use Python 3.12 e um ambiente virtual. Instale com `python -m pip install -e .`.
- Mantenha rede, leitura do mundo, armazenamento e renderização nos seus módulos.
- Preserve IDs de mundo, dados existentes e permissões do host/PIN.
- Migrações devem ser aditivas e verificáveis. Não apague dados locais como parte de uma mudança visual.
- Arte, fontes e código de terceiros precisam de licença e atribuição compatíveis. Créditos não substituem uma licença.
- Não inclua saves, capturas, configurações locais, dumps ou binários temporários na contribuição.

A suíte de testes do projeto é mantida localmente e não acompanha este repositório. Ao contribuir, descreva como verificou a alteração, os passos para repetir a validação e o que ainda depende de teste no jogo ou navegador real.

DOM/canvas e Script API simulados não provam comportamento no Minecraft real. Comparações de desempenho precisam do mesmo cenário e configurações; evite prometer ganho de FPS a partir de um teste isolado.

Abra um PR curto: problema, mudança e validação. Mudanças grandes ficam mais fáceis de revisar quando divididas por responsabilidade.
