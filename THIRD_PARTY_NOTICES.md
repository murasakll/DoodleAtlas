# Cr?ditos e licen?as do DoodleAtlas

## Antique Atlas

O modo Atlas usa 25 folhas PNG de terreno do [Antique Atlas](https://github.com/AntiqueAtlasTeam/AntiqueAtlas), versão fixada no commit `b706821d3f0203038de3de6e79a6d354fe2c7b18` (branch `1.18`). Atribuição original: Copyright (c) 2015 Hunternif <hunternif@gmail.com>. Créditos ao projeto Antique Atlas e seus colaboradores.

As texturas são distribuídas sob **Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported** ([CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/)). A licença exige atribuição, uso não comercial e compartilhamento de adaptações dessa arte sob a mesma licença. Publicar o repositório no GitHub não substitui essas obrigações. Não há endosso do projeto original.

Os PNGs em `src/chiko/assets/antique_atlas/tiles/` são cópias sem alteração. Em execução, o aplicativo adapta cores para tinta/papel, seleciona quadrantes, compõe vizinhos e recorta a arte aos dados disponíveis. Essas adaptações da arte permanecem sob CC BY-NC-SA 3.0. Exportações que contenham essa arte incluem os créditos; mantenha atribuição e licença ao compartilhá-las ou adaptá-las.

- [Manifesto: arquivos, URLs originais e SHA-256](src/chiko/assets/antique_atlas/manifest.json)
- [Licença original do projeto](src/chiko/assets/antique_atlas/UPSTREAM-LICENSE.txt)
- [Texto completo da licença da arte](src/chiko/assets/antique_atlas/CC-BY-NC-SA-3.0.txt)

Não foi incorporado código Java do Antique Atlas. A GPL mencionada na licença original se refere ao código daquele projeto; a inclusão destes PNGs não declara todo o código do Chiko sob GPL ou sob Creative Commons. Este aviso descreve apenas esta integração, não substitui uma auditoria de todas as dependências do repositório antes de publicá-lo.

## Personagem Chiko e imagens da apresentação

Personagem atribuído a **Hachiko / Noah**: <https://www.tiktok.com/@hachikookami>.

`src/chiko/assets/chiko/chiko-pixel-v1.png` é uma recriação em pixel art gerada com IA a partir da referência fornecida do personagem. `docs/images/chiko-banner.png` é uma ilustração de apresentação gerada com IA usando essa identidade. Não são apresentadas como desenhos executados pelo criador original. A autoria do personagem continua atribuída a Hachiko / Noah; não foi declarada uma licença aberta para ele nem um endosso do projeto.

Os seis prints em `docs/images/` foram capturados da interface executada com dados sintéticos. Quando exibem arte do Antique Atlas, essa parte mantém CC BY-NC-SA 3.0 e os créditos acima. A capa é ilustração, não screenshot. O brief está em `docs/images/chiko-banner.prompt.txt`.

## Fonte Caveat

Fonte local distribuída sob **SIL Open Font License 1.1**. O texto da licença e a atribuição acompanham `src/chiko/assets/web/OFL-Caveat.txt`; a fonte está no mesmo diretório. Não é carregada de uma CDN.

## Gerador opcional de seed

O gerador inclui fontes de **Cubiomes / Cubitect** e alterações de **SeedForge**, sob as licenças MIT fornecidas pelos respectivos projetos. Fontes, hashes fixados, avisos, patch e DLL estão em `src/chiko/vendor/seed-generator/`. Veja `NOTICE.txt`, `LICENSE-cubiomes.txt`, `LICENSE-seedforge.txt` e `manifest.json` nessa pasta.

A adaptação para as versões Bedrock indicadas é experimental. A licença de uma biblioteca não comprova compatibilidade da previsão com todo mundo Bedrock.

## Dependências Python

As dependências diretas são declaradas em `requirements.txt`: Amulet Core, aiohttp, Pillow, qrcode e cryptography. Seus pacotes e dependências transitivas mantêm as licenças próprias. A instalação é feita pelos distribuidores dos pacotes; não são vendidas ou relicenciadas como código autoral do Chiko.

Playwright/Chromium são ferramentas opcionais de captura da galeria. Não estão incorporados ao aplicativo ou ao repositório.

## Código autoral

O código autoral do DoodleAtlas é Copyright (c) 2026 murasakll e distribuído sob a licença MIT em `LICENSE`. Essa licença cobre o código autoral, não os direitos do personagem Chiko, as artes do Antique Atlas, as fontes ou as dependências, que mantêm seus termos próprios.

O ícone `src/chiko/assets/branding/doodleatlas-icon.png` foi gerado com IA a partir da referência fornecida do Chiko segurando um mapa. É uma adaptação do personagem de Hachiko / Noah, sem declaração de licença aberta ou endosso do criador. O brief está em `docs/images/doodleatlas-icon.prompt.txt`.
