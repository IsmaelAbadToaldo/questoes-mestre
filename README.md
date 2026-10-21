# Estudo reverso · PPCA/UFRR 2027

App de questões para a prova escrita do PPCA/UFRR (22/10/2026): as 100 questões do PDF *Estudo reverso*, em 13 blocos de assunto, com correção na hora (verde = certa, vermelho = errada), gabarito comentado, conceito-chave e referência ao Celes e ao Cormen.

**Site:** https://ismaelabadtoaldo.github.io/questoes-mestre/

## IDs

| ID |
|---|
| `JADE-31` |
| `OPALA-58` |

Cada pessoa entra com o seu ID, e as respostas, o histórico e as estatísticas ficam guardados nele. Maiúsculas, espaços e hífen não importam na digitação (`jade31` funciona).

## Onde o progresso fica salvo

- **No aparelho** (localStorage), na hora, a cada resposta.
- **Na nuvem** (api.restful-api.dev, gratuita e sem conta), em lotes: ao entrar, a cada 10 respostas ou 6 minutos, ao sair e quando a aba ou o app vai para segundo plano. Assim dá para continuar em outro aparelho com o mesmo ID.

A API gratuita aceita cerca de 50 requisições por dia por usuário. Se ela recusar ou sair do ar, nada se perde: o app segue salvando no aparelho, mostra "Nuvem fora do ar" no topo e tenta de novo depois. O status no topo também é um botão para enviar na hora.

Para trocar um ID, mude a chave na constante `PESSOAS` do `index.html`. Para criar um ID novo, crie o registro e cole o `id` devolvido em `PESSOAS`:

```sh
curl -X POST https://api.restful-api.dev/objects -H "Content-Type: application/json" \
  -d '{"name":"estudo-reverso-ppca-NOVO","data":{"v":1,"tentativas":[],"zeradoEm":0}}'
```

## Arquivos

- `index.html`: o app inteiro (HTML, CSS e JS, sem dependências).
- `questoes.js`: as 100 questões, geradas do PDF.
- `scripts/extrair_questoes.py`: extrator do PDF. Confere cada questão: a letra do gabarito rápido contra a do gabarito comentado, e o texto da alternativa correta contra o texto do gabarito.

Para regerar as questões (o PDF fica em `docs/`, fora do repositório):

```sh
pip install pymupdf
python scripts/extrair_questoes.py docs/Estudo_Reverso_PPCA_2027.pdf questoes.js
```

Para rodar localmente, abra o `index.html` no navegador ou use `python -m http.server` e acesse http://localhost:8000.
