"""Extrai as questões do PDF "Estudo reverso" para o arquivo de dados do app.

Uso:
    python scripts/extrair_questoes.py docs/Estudo_Reverso_PPCA_2027.pdf questoes.js

Requer PyMuPDF (pip install pymupdf). O PDF foi gerado com ReportLab e tem
estilos fixos, então a extração se guia pela fonte de cada linha:
  - DejaVuSans-Bold 14.5 ........ título de bloco ("01 · Fundamentos ...")
  - DejaVuSerif-Bold "NN)" ...... início de questão
  - DejaVuSerif .................. enunciado, alternativas e comentário
  - DejaVuSansMono ............... código (com indentação preservada)
  - DejaVuSans 6.6 ............... rótulo da linguagem do código
  - "NN · Resposta X · nível" .... cabeçalho do gabarito comentado
"""
import json
import re
import sys
import unicodedata

import pymupdf

MONO = "DejaVuSansMono"
LINHA_CODIGO = 10.6          # entrelinha do código, em pontos
LARGURA_CHAR = 0.602 * 8.2   # largura de um caractere de DejaVuSansMono 8.2
RE_ROMANO = re.compile(r"^(I|II|III|IV|V|VI|VII|VIII)\.\s")
RE_ALTERNATIVA = re.compile(r"^([a-e])\)\s+(.*)$")
RE_BLOCO = re.compile(r"^(\d{2})\s*·\s*(.+)$")
RE_RESPOSTA = re.compile(r"^(\d{2,3})\s*·\s*Resposta\s+([A-E])")
LINGUAGENS = {"C": "C", "PYTHON": "Python"}


def ler_linhas(caminho):
    """Todas as linhas do PDF, em ordem de leitura, com fonte e posição."""
    doc = pymupdf.open(caminho)
    linhas = []
    for num_pag, pagina in enumerate(doc, 1):
        da_pagina = []
        for bloco in pagina.get_text("dict")["blocks"]:
            for ln in bloco.get("lines", []):
                spans = [s for s in ln["spans"] if s["text"]]
                if not spans:
                    continue
                x0, y0, x1, y1 = ln["bbox"]
                da_pagina.append({
                    "pag": num_pag, "x0": x0, "y0": y0, "x1": x1,
                    "texto": "".join(s["text"] for s in spans),
                    "fonte": spans[0]["font"],
                    "tam": round(spans[0]["size"], 1),
                    "spans": spans,
                })
        da_pagina.sort(key=lambda l: (round(l["y0"], 1), l["x0"]))
        linhas.extend(da_pagina)
    return linhas


def rodape(l):
    return l["fonte"] == "DejaVuSans" and l["tam"] == 7.6


def titulo_bloco(l):
    return l["fonte"] == "DejaVuSans-Bold" and l["tam"] == 14.5


def normaliza(txt):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", txt)).strip()


class Paragrafos:
    """Junta linhas justificadas em parágrafos.

    Em texto justificado, toda linha que não é a última do parágrafo vai até
    a margem direita; uma linha mais curta encerra o parágrafo.
    """

    def __init__(self, margem_direita):
        self.margem = margem_direita
        self.itens = []
        self.aberto = False

    def linha(self, l, texto=None):
        texto = (l["texto"] if texto is None else texto).strip()
        if self.aberto and not RE_ROMANO.match(texto):
            self.itens[-1] += " " + texto
        else:
            self.itens.append(texto)
        self.aberto = l["x1"] >= self.margem - 4

    def fecha(self):
        self.aberto = False


def extrair_questoes(linhas):
    blocos, questoes = [], []
    q = None
    modo = None          # "enunciado" | "alternativas"
    paragrafos = None
    codigo = None        # bloco de código aberto no enunciado
    ultima_alt = None
    margem = max(l["x1"] for l in linhas if l["fonte"] == "DejaVuSerif" and l["pag"] < 46)

    def fecha_questao():
        # Cada parágrafo vira um item próprio, para o app renderizar com <p>.
        if q is None:
            return
        fecha_codigo()
        itens = []
        for it in q["enunciado"]:
            if it["t"] == "p":
                itens.extend({"t": "p", "x": p} for p in it.pop("_par").itens if p.strip())
            elif it["x"].strip():
                itens.append(it)
        q["enunciado"] = itens

    def fecha_codigo():
        nonlocal codigo
        if codigo is not None:
            codigo["x"] = "\n".join(codigo.pop("_linhas")).rstrip("\n")
            codigo.pop("_y", None)
            codigo.pop("_pag", None)
            codigo = None

    def texto_enunciado(l, texto=None):
        # Parágrafos do enunciado e blocos de código ficam intercalados na ordem do PDF.
        nonlocal paragrafos
        fecha_codigo()
        if paragrafos is None:
            paragrafos = Paragrafos(margem)
            q["enunciado"].append({"t": "p", "_par": paragrafos})
        paragrafos.linha(l, texto)

    def interrompe_paragrafos():
        nonlocal paragrafos
        paragrafos = None

    for l in linhas:
        if l["pag"] == 1 or rodape(l):
            continue
        texto = l["texto"]
        if titulo_bloco(l):
            if texto.startswith("Folha de respostas"):
                break
            m = RE_BLOCO.match(texto)
            blocos.append({"id": int(m.group(1)), "nome": m.group(2).strip()})
            continue
        if l["fonte"] == "DejaVuSans" and l["tam"] == 8.4 and texto.startswith("Questões"):
            blocos[-1]["resumo"] = texto.split("·", 1)[1].strip()
            continue
        primeiro = l["spans"][0]
        if primeiro["font"] == "DejaVuSerif-Bold" and re.fullmatch(r"\d{2,3}\)", primeiro["text"].strip()):
            fecha_questao()
            interrompe_paragrafos()
            q = {"n": int(primeiro["text"].strip()[:-1]), "bloco": blocos[-1]["id"],
                 "enunciado": [], "alternativas": {}}
            questoes.append(q)
            modo = "enunciado"
            texto_enunciado(l, texto[len(primeiro["text"]):])
            continue
        if q is None:
            continue
        if l["fonte"] == "DejaVuSans" and l["tam"] == 6.6:
            # Rótulo da linguagem no canto do quadro de código: começa um quadro novo.
            fecha_codigo()
            interrompe_paragrafos()
            codigo = {"t": "code", "lang": LINGUAGENS.get(texto.strip(), texto.strip().title()),
                      "_linhas": [], "_y": None, "_pag": l["pag"]}
            q["enunciado"].append(codigo)
            continue
        if l["fonte"] == MONO:
            if codigo is None:
                interrompe_paragrafos()
                anterior = q["enunciado"][-1] if q["enunciado"] else None
                if anterior and anterior.get("t") == "code" and "_linhas" not in anterior:
                    # Quadro que continua depois de uma quebra de página.
                    anterior["_linhas"] = anterior["x"].split("\n")
                    codigo = anterior
                else:
                    codigo = {"t": "code", "lang": "", "_linhas": [], "_y": None, "_pag": l["pag"]}
                    q["enunciado"].append(codigo)
                codigo["_y"], codigo["_pag"] = None, l["pag"]
            if codigo["_y"] is not None and codigo["_pag"] == l["pag"]:
                vazias = round((l["y0"] - codigo["_y"]) / LINHA_CODIGO) - 1
                codigo["_linhas"].extend([""] * max(0, vazias))
            recuo = max(0, round((l["x0"] - 73.0) / LARGURA_CHAR))
            codigo["_linhas"].append(" " * recuo + texto.rstrip())
            codigo["_y"], codigo["_pag"] = l["y0"], l["pag"]
            continue
        if l["fonte"] != "DejaVuSerif":
            raise ValueError(f"linha inesperada na página {l['pag']}: {texto!r} ({l['fonte']})")
        m = RE_ALTERNATIVA.match(texto)
        if m and l["x0"] < 60:
            fecha_codigo()
            interrompe_paragrafos()
            modo = "alternativas"
            ultima_alt = m.group(1)
            q["alternativas"][ultima_alt] = m.group(2).strip()
        elif modo == "alternativas":
            q["alternativas"][ultima_alt] += " " + texto.strip()
        else:
            texto_enunciado(l)
    fecha_questao()
    return blocos, questoes


def extrair_gabarito(linhas):
    pag_comentado = next(l["pag"] for l in linhas if titulo_bloco(l) and l["texto"].startswith("Gabarito comentado"))
    # Gabarito rápido: tabela de pares "NN X" no topo da primeira página do gabarito.
    tabela = []
    for l in linhas:
        if l["pag"] != pag_comentado:
            continue
        if l["texto"].startswith("Cada letra"):
            break
        tabela.append(l)
    rapido = {}
    for l in tabela:
        for n, letra in re.findall(r"\b(\d{2,3})\s+([A-E])\b", l["texto"]):
            rapido[int(n)] = letra

    respostas = {}
    r = None
    estado = None
    paragrafos = None
    bloco_atual = None
    comecou = False
    for l in linhas:
        if l["pag"] < pag_comentado or rodape(l):
            continue
        texto = l["texto"]
        if titulo_bloco(l):
            m = RE_BLOCO.match(texto)
            if m:
                bloco_atual = int(m.group(1))
                comecou = True
            continue
        if not comecou:
            continue
        m = RE_RESPOSTA.match(texto)
        if m and l["fonte"] == "DejaVuSans-Bold":
            nivel = re.search(r"(fácil|médio|difícil)", texto)
            r = {"n": int(m.group(1)), "letra": m.group(2), "bloco": bloco_atual,
                 "nivel": nivel.group(1) if nivel else None,
                 "texto_resposta": "", "comentario": [], "conceito": "", "referencia": ""}
            respostas[r["n"]] = r
            estado = "resposta"
            paragrafos = None
            continue
        if r is None:
            continue
        if l["fonte"] == "DejaVuSans" and l["tam"] == 8.0 and r["nivel"] is None:
            r["nivel"] = re.search(r"(fácil|médio|difícil)", texto).group(1)
            continue
        if l["fonte"] == "DejaVuSans" and l["tam"] == 8.6 and estado == "resposta":
            r["texto_resposta"] = (r["texto_resposta"] + " " + texto.strip()).strip()
            continue
        if l["fonte"] == "DejaVuSerif" and estado in ("resposta", "comentario"):
            if paragrafos is None:
                margem = max(x["x1"] for x in linhas if x["fonte"] == "DejaVuSerif" and x["pag"] >= pag_comentado)
                paragrafos = Paragrafos(margem)
            estado = "comentario"
            paragrafos.linha(l)
            r["comentario"] = paragrafos.itens
            continue
        if texto.startswith("Conceito-chave:"):
            estado = "conceito"
            r["conceito"] = texto[len("Conceito-chave:"):].strip()
            continue
        if estado == "conceito" and l["fonte"] == "DejaVuSans" and l["tam"] == 8.8:
            r["conceito"] += " " + texto.strip()
            continue
        if texto.startswith("Referência:"):
            estado = "referencia"
            r["referencia"] = texto[len("Referência:"):].strip()
            continue
        if estado == "referencia" and l["fonte"] == "DejaVuSans-Oblique":
            r["referencia"] += " " + texto.strip()
            continue
        raise ValueError(f"linha inesperada no gabarito, página {l['pag']}: {texto!r} ({l['fonte']} {l['tam']})")
    return rapido, respostas


def montar(caminho_pdf):
    linhas = ler_linhas(caminho_pdf)
    blocos, questoes = extrair_questoes(linhas)
    rapido, respostas = extrair_gabarito(linhas)
    problemas = []
    for q in questoes:
        r = respostas.get(q["n"])
        if r is None:
            problemas.append(f"Q{q['n']}: sem comentário no gabarito")
            continue
        if rapido.get(q["n"]) != r["letra"]:
            problemas.append(f"Q{q['n']}: gabarito rápido {rapido.get(q['n'])} ≠ comentado {r['letra']}")
        if r["bloco"] != q["bloco"]:
            problemas.append(f"Q{q['n']}: bloco {q['bloco']} na prova e {r['bloco']} no gabarito")
        if sorted(q["alternativas"]) != list("abcde"):
            problemas.append(f"Q{q['n']}: alternativas {sorted(q['alternativas'])}")
        alt = q["alternativas"].get(r["letra"].lower(), "")
        if normaliza(alt) != normaliza(r["texto_resposta"]):
            problemas.append(f"Q{q['n']}: texto da resposta difere\n   alt: {alt!r}\n   gab: {r['texto_resposta']!r}")
        if not r["comentario"] or not r["conceito"] or not r["referencia"] or not r["nivel"]:
            problemas.append(f"Q{q['n']}: comentário incompleto")
        q["nivel"] = r["nivel"]
        q["resposta"] = r["letra"].lower()
        q["comentario"] = r["comentario"]
        q["conceito"] = r["conceito"]
        q["referencia"] = r["referencia"]
    numeros = [q["n"] for q in questoes]
    if numeros != list(range(1, len(questoes) + 1)):
        problemas.append(f"numeração fora de ordem: {numeros}")
    for b in blocos:
        ns = [q["n"] for q in questoes if q["bloco"] == b["id"]]
        b["de"], b["ate"] = min(ns), max(ns)
    banco = {
        "titulo": "Estudo reverso · Prova escrita PPCA/UFRR 2027",
        "fonte": "Estudo_Reverso_PPCA_2027.pdf",
        "blocos": blocos,
        "questoes": questoes,
    }
    return banco, problemas


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    pdf, saida = sys.argv[1], sys.argv[2]
    banco, problemas = montar(pdf)
    qs = banco["questoes"]
    print(f"{len(banco['blocos'])} blocos, {len(qs)} questões, "
          f"{sum(1 for q in qs for it in q['enunciado'] if it['t'] == 'code')} quadros de código")
    for nivel in ("fácil", "médio", "difícil"):
        print(f"  {nivel}: {sum(1 for q in qs if q.get('nivel') == nivel)}")
    for b in banco["blocos"]:
        print(f"  {b['id']:02d} {b['nome']}: {b['de']}–{b['ate']} ({b.get('resumo', '')})")
    if problemas:
        print("PROBLEMAS:")
        for p in problemas:
            print(" -", p)
        sys.exit(1)
    dados = json.dumps(banco, ensure_ascii=False, separators=(",", ":"))
    with open(saida, "w", encoding="utf-8") as f:
        f.write("// Gerado por scripts/extrair_questoes.py a partir do PDF. Não edite à mão.\n")
        f.write(f"window.BANCO = {dados};\n")
    print(f"gravado em {saida}")


if __name__ == "__main__":
    main()
