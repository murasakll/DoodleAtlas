# Textos do DoodleAtlas

[Português](../README.md) · [English](../README.en.md)

A escrita está aberta para receber a sua voz. Pode mandar só um trecho: “troque esta frase por esta”. Não precisa reescrever tudo de uma vez.

## Onde editar

| Arquivo | Conteúdo |
| --- | --- |
| `README.md` | Apresentação em português |
| `README.en.md` | Apresentação em inglês |
| `src/chiko/web/index.html` | Textos fixos em português dos painéis |
| `src/chiko/web/caderno-preview.js` | Abas, sons e legendas do Chiko em português |
| `src/chiko/web/chiko.js` | Falas básicas do Chiko |
| `src/chiko/web/locales.js` | Pares de texto original e tradução inglesa |
| `src/chiko/web/i18n.js` | Troca de idioma e frases com números ou nomes |

No catálogo `locales.js`, cada linha tem o formato `texto em português|English text`. Ao mudar uma frase original, atualize também o lado esquerdo da tradução correspondente. O caractere `|` separa os idiomas e não deve fazer parte da frase. Não traduza IDs, valores dos controles, comandos do Minecraft ou nomes de arquivos.

Nomes de mundos, jogadores, lugares e construções são conteúdo de quem usa o mapa. A troca de idioma não deve reescrevê-los. Mensagens técnicas das bibliotecas podem aparecer no idioma original.

## Tom

Frases curtas, diretas e naturais. O Chiko pode ter personalidade; instruções de salvar, apagar ou compartilhar precisam continuar claras. Créditos e condições das licenças mantêm os nomes e links dos autores.

## Editing the copy

Portuguese source text lives in the HTML and UI modules above. Each line in `locales.js` pairs that source with its English translation, separated by `|`. When changing source copy, update its catalog entry too. Keep IDs, command syntax, control values and user-written names unchanged.
