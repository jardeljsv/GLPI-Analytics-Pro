#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Padroniza o dashboard Gestao de Ativos | Cadmus com cabecalho e secoes.

- Usa as MESMAS duas imagens do BI Central de Servicos e titulo no centro.
- Distribui as 15 perguntas existentes, sem recriar ou alterar SQL/filtros.
- Acrescenta explicacoes curtas de cada secao em Markdown puro.
- Preserva os cards e seus IDs, cria backup local antes de aplicar.
- Descobre o ID do dashboard por nome na colecao Gestao de Ativos | Cadmus.
- Seguranca: nao sobrescreve widgets desconhecidos e nao duplica cabecalho.

Simulacao: python3 ajustar_cabecalho_dashboard_ativos.py
Aplicar:   python3 ajustar_cabecalho_dashboard_ativos.py --apply
Restaurar: python3 ajustar_cabecalho_dashboard_ativos.py --restore BACKUP.json --apply

Requer MB_API_KEY exportada no terminal. MB_URL opcional.
"""
import argparse
import copy
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("MB_URL", "http://127.0.0.1:3000").rstrip("/")
KEY = os.environ.get("MB_API_KEY", "")
COLLECTION = "Gestão de Ativos | Cadmus"
DASH_NAME = "Gestão de Ativos | Cadmus"
LOGO = "https://raw.githubusercontent.com/jardeljsv/projects/refs/heads/main/dashboard-metabase.png"

# Posicoes (coluna, linha, largura, altura) numa grade de 24 colunas.
LAYOUT = {
    "01": (0, 9, 6, 4),
    "02": (6, 9, 6, 4),
    "03": (12, 9, 6, 4),
    "04": (18, 9, 6, 4),
    "05": (0, 16, 12, 8),
    "06": (12, 16, 12, 8),
    "07": (0, 35, 12, 8),
    "08": (12, 35, 12, 8),
    "09": (0, 43, 24, 9),
    "10": (12, 24, 12, 8),
    "11": (0, 55, 12, 4),
    "12": (12, 55, 12, 4),
    "13": (0, 59, 12, 9),
    "14": (0, 24, 12, 8),
    "15": (12, 59, 12, 9),
}

# Apenas Markdown, SEM comentarios HTML/identificadores visiveis.
TEXT_CARDS = [
    ("logo_esquerda",  (0, 0, 7, 3),
     "![Identidade visual Cadmus](%s)" % LOGO),
    ("titulo_central", (7, 0, 10, 3),
     "## GESTÃO DE ATIVOS\n**Inventário e Ciclo de Vida | Cadmus**"),
    ("logo_direita",   (17, 0, 7, 3),
     "![Identidade visual Cadmus](%s)" % LOGO),
    ("introducao",     (0, 3, 24, 4),
     "### Painel de Gestão de Ativos\n"
     "Acompanhamento do parque, disponibilidade, vinculação de usuários, "
     "distribuição física e ciclo de vida dos equipamentos.\n\n"
     "*Escopo inicial: registros das entidades GLPI 83, 137 e 162. "
     "Os ativos ainda não estão segregados entre Cadmus e PeoplePro no inventário.*"),
    ("visao_geral",    (0, 7, 24, 2),
     "### Visão geral"),
    ("parque",         (0, 13, 24, 3),
     "### Parque de equipamentos\n"
     "Distribuição por tipo, estado, modelo e combinação de tipo × estado. "
     "A análise de modelos considera computadores cadastrados no GLPI."),
    ("estoque",        (0, 32, 24, 3),
     "### Disponibilidade, vinculação e localização\n"
     "Equipamentos disponíveis conforme estado GLPI, ativos sem usuário "
     "e principais localizações. *Sem usuário não significa disponível.*"),
    ("ciclo_de_vida",  (0, 52, 24, 3),
     "### Garantias, descarte e idade do parque\n"
     "Garantias próximas do vencimento, equipamentos em estado de descarte "
     "e idade estimada dos computadores com data de compra registrada."),
]
HEADINGS = {key: value.splitlines()[0] for key, _, value in TEXT_CARDS
            if key not in ("logo_esquerda", "logo_direita")}
KEEP_FIELDS = (
    "id", "card_id", "row", "col", "size_x", "size_y",
    "parameter_mappings", "visualization_settings", "dashboard_tab_id",
    "action_id", "inline_parameters"
)

def api(method, path, payload=None):
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        BASE + "/api" + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as res:
            data = res.read()
            return json.loads(data.decode("utf-8")) if data else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            "HTTP %s %s: %s" %
            (exc.code, path, exc.read().decode(errors="replace")[:1800]))
    except urllib.error.URLError as exc:
        raise RuntimeError("Falha de conexao com Metabase: %s" % exc)

def cards(dashboard):
    return dashboard.get("dashcards") or dashboard.get("ordered_cards") or []

def collection_id():
    result = api("GET", "/collection")
    objects = result if isinstance(result, list) else result.get("data", [])
    matching = [x for x in objects if x.get("name") == COLLECTION and not x.get("archived")]
    if len(matching) != 1:
        raise RuntimeError(
            "Esperada uma colecao '%s', encontradas %s. "
            "Execute primeiro o script de criacao do painel." % (COLLECTION, len(matching)))
    return matching[0]["id"]

def find_dashboard(cid):
    result = api("GET", "/collection/%s/items?models=dashboard&limit=100" % cid)
    data = result.get("data", [])
    found = [x for x in data if x.get("name") == DASH_NAME]
    if len(found) != 1:
        raise RuntimeError("Esperado um dashboard '%s' na colecao; encontrados %s."
                           % (DASH_NAME, len(found)))
    return found[0]["id"]

def prepare_card(card):
    return {field: copy.deepcopy(card[field]) for field in KEEP_FIELDS if field in card}

def sequence_number(card):
    name = ((card.get("card") or {}).get("name") or "").strip()
    # Nomes do script original: '01 | Total de ativos', ... '15 | ...'
    if len(name) >= 5 and name[0:2].isdigit() and name[2:5] == " | ":
        return name[0:2]
    return None

def kind(card):
    viz = card.get("visualization_settings") or {}
    virtual = viz.get("virtual_card") or {}
    return virtual.get("display", "unknown")

def assign_text_ids(existing):
    """Identifica somente textos ja padronizados e associa ID; evita duplicar."""
    matched = {}
    others = []
    logos = []
    for card in existing:
        if card.get("card_id") is not None:
            continue
        if kind(card) != "text":
            others.append(card)
            continue
        text = (card.get("visualization_settings") or {}).get("text", "").strip()
        if text == "![Identidade visual Cadmus](%s)" % LOGO:
            logos.append(card)
            continue
        found = [
            key for key, heading in HEADINGS.items()
            if text.splitlines() and text.splitlines()[0].strip() == heading
        ]
        if len(found) != 1 or found[0] in matched:
            others.append(card)
        else:
            matched[found[0]] = card
    if len(logos) > 2:
        raise RuntimeError("Mais de duas imagens do cabecalho padronizado.")
    logos.sort(key=lambda x: x.get("col", 0))
    if logos:
        matched["logo_esquerda"] = logos[0]
    if len(logos) == 2:
        matched["logo_direita"] = logos[1]
    if others:
        raise RuntimeError(
            "Ha %d cartoes visuais/textos desconhecidos no dashboard. "
            "Cancelado para preservar edicoes manuais. IDs: %s"
            % (len(others), [c.get("id") for c in others]))
    return matched

def new_text_card(card_id, pos, content):
    col, row, width, height = pos
    return {
        "id": card_id,
        "card_id": None,
        "row": row,
        "col": col,
        "size_x": width,
        "size_y": height,
        "parameter_mappings": [],
        "visualization_settings": {
            "virtual_card": {
                "name": None, "display": "text",
                "visualization_settings": {}, "archived": False
            },
            "text": content
        }
    }

def backup(dashboard):
    filename = ("backup_dashboard_ativos_%s_%s.json" %
                (dashboard["id"], dt.datetime.now().strftime("%Y%m%d_%H%M%S")))
    with open(filename, "w", encoding="utf-8") as out:
        json.dump(dashboard, out, ensure_ascii=False, indent=2)
    print("Backup salvo:", os.path.abspath(filename))

def make_layout(dashboard):
    existing = cards(dashboard)
    originals = {}
    for item in existing:
        if item.get("card_id") is None:
            continue
        no = sequence_number(item)
        if not no or no not in LAYOUT or no in originals:
            raise RuntimeError(
                "Card inesperado/duplicado ID %s. Nome: %s" %
                (item.get("id"), (item.get("card") or {}).get("name")))
        originals[no] = item
    missing = set(LAYOUT) - set(originals)
    if missing:
        raise RuntimeError("Perguntas ausentes no dashboard: %s" % ", ".join(sorted(missing)))
    matched = assign_text_ids(existing)
    result = []
    for no in sorted(LAYOUT):
        card = prepare_card(originals[no])
        x, y, w, h = LAYOUT[no]
        card.update(col=x, row=y, size_x=w, size_y=h)
        result.append(card)
    negative_id = -1
    for key, placement, text in TEXT_CARDS:
        if key in matched:
            card = prepare_card(matched[key])
            card["visualization_settings"]["text"] = text
            x, y, w, h = placement
            card.update(col=x, row=y, size_x=w, size_y=h)
        else:
            while any(c.get("id") == negative_id for c in result):
                negative_id -= 1
            card = new_text_card(negative_id, placement, text)
            negative_id -= 1
        result.append(card)
    return {
        "name": dashboard["name"],
        "width": "full",
        "parameters": copy.deepcopy(dashboard.get("parameters") or []),
        "dashcards": result
    }

def restore_patch(saved):
    return {
        "name": saved["name"],
        "width": saved.get("width", "full"),
        "parameters": copy.deepcopy(saved.get("parameters") or []),
        "dashcards": [prepare_card(c) for c in cards(saved)]
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore", metavar="BACKUP_JSON")
    args = parser.parse_args()
    if not KEY:
        raise RuntimeError("MB_API_KEY nao definida. Exporte a chave no terminal.")
    cid = collection_id()
    dashboard_id = find_dashboard(cid)
    current = api("GET", "/dashboard/%s" % dashboard_id)
    if current.get("name") != DASH_NAME:
        raise RuntimeError("Nome do dashboard inesperado: cancelado.")
    if args.restore:
        with open(args.restore, encoding="utf-8") as source:
            saved = json.load(source)
        if saved.get("id") != dashboard_id or saved.get("name") != DASH_NAME:
            raise RuntimeError("O backup informado nao pertence a este dashboard.")
        patch = restore_patch(saved)
        print("RESTAURO a partir de:", args.restore)
    else:
        patch = make_layout(current)
        print("AJUSTE DE LAYOUT | Dashboard ID:", dashboard_id)
        print("15 perguntas preservadas; 3 blocos de cabecalho; 5 textos de secao/introducao")
        print("Cabecalho: imagens 7+7 e titulo central 10 colunas")
        print("Largura: full | secoes em Markdown puro")
    print("Total de elementos previstos:", len(patch["dashcards"]))
    if not args.apply:
        print("SIMULACAO. Nenhuma alteracao foi realizada. Execute com --apply.")
        return
    backup(current)
    api("PUT", "/dashboard/%s" % dashboard_id, patch)
    after = api("GET", "/dashboard/%s" % dashboard_id)
    print("Elementos apos salvar:", len(cards(after)))
    print("Filtros globais preservados:", len(after.get("parameters") or []))
    print("Largura:", after.get("width"))
    if len(cards(after)) != len(patch["dashcards"]):
        raise RuntimeError("Dashboard alterado, mas contagem divergiu: confira o backup.")
    print("SUCESSO:", BASE + "/dashboard/" + str(dashboard_id))
    print("Atualize a pagina com Ctrl+F5.")

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        sys.exit("ERRO: %s" % exc)
