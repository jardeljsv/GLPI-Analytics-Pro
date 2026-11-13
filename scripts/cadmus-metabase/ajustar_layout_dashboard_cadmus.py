#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cadmus - ajuste do dashboard 3 no Metabase 0.65.3.

- Preserva as imagens nas laterais do cabeçalho e os filtros globais.
- Padroniza o texto central.
- Insere titulos de secao e reorganiza os indicadores.
- Reduz o cartao de SLA; equilibra os de satisfacao.
- Cria backup JSON antes de aplicar. Nao altera perguntas/SQL.

Uso:
  python3 ajustar_layout_dashboard_cadmus.py
  python3 ajustar_layout_dashboard_cadmus.py --apply
  python3 ajustar_layout_dashboard_cadmus.py --restore arquivo_backup.json --apply

Requer MB_API_KEY no ambiente. Executar no servidor do Metabase.
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
DASH_ID = 3
EXPECTED_NAME = "Central de Serviços | Cadmus"

# IDs dos cartoes DO DASHBOARD, nao IDs das perguntas.
HEADER_LEFT = 53
HEADER_RIGHT = 54
HEADER_TITLE = 55
POSITIONS = {
    53: (0, 0, 7, 3),
    55: (7, 0, 10, 3),
    54: (17, 0, 7, 3),
    # Indicadores gerenciais: cinco cartes na mesma linha
    37: (0, 5, 5, 4),   # Abertos
    38: (5, 5, 5, 4),   # Solucionados
    39: (10, 5, 5, 4),  # Nao solucionados do periodo
    40: (15, 5, 5, 4),  # Fora do prazo
    41: (20, 5, 4, 4),  # Backlog atual
    # Volumetria
    42: (0, 11, 12, 8),  # Aberturas por mes
    43: (12, 11, 12, 8), # Solucoes por mes
    44: (0, 19, 24, 8), # Organizacoes: grafico em largura total
    # SLA e backlog
    45: (0, 29, 8, 5),  # Percentual SLA mais compacto
    48: (8, 29, 16, 8), # Backlog atual por categoria
    # Categorias e atrasos
    46: (0, 39, 12, 9),
    47: (12, 39, 12, 9),
    # Tecnicos
    49: (0, 50, 24, 9),
    # Satisfacao
    50: (0, 61, 8, 5),
    51: (8, 61, 16, 7),
    # Detalhamento
    52: (0, 70, 24, 11),
}
SECTIONS = [
    ("Visão geral", 3),
    ("Volumetria de chamados", 9),
    ("SLA e backlog", 27),
    ("Categorias e atrasos", 37),
    ("Produtividade por técnico", 48),
    ("Satisfação dos usuários", 59),
    ("Detalhamento de chamados fora do prazo", 68),
]
TITLE_TEXT = "## CENTRAL DE SERVIÇOS\n**Dashboard Gerencial | Cadmus & PeoplePro**"
MARK = "CS_CADMUS_SECTION_V1"


def api(method, path, payload=None):
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(BASE + "/api" + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            body = response.read()
            return json.loads(body.decode("utf-8")) if body else {}
    except urllib.error.HTTPError as error:
        raise RuntimeError("HTTP %s %s: %s" % (
            error.code, path, error.read().decode("utf-8", errors="replace")[:1700]))
    except urllib.error.URLError as error:
        raise RuntimeError("Conexao Metabase: %s" % error)


def items(dashboard):
    return dashboard.get("dashcards") or dashboard.get("ordered_cards") or []


def validate_dashboard(dashboard):
    if dashboard.get("id") != DASH_ID or dashboard.get("name") != EXPECTED_NAME:
        raise RuntimeError("Dashboard inesperado; operacao cancelada.")
    found = {item.get("id") for item in items(dashboard)}
    absent = sorted(set(POSITIONS) - found)
    if absent:
        raise RuntimeError("IDs de cards nao encontrados: %s. Revise layout manualmente." % absent)
    if len(dashboard.get("parameters") or []) != 4:
        raise RuntimeError("Numero de filtros globais diferente de quatro; nao alterar.")
    for hid in (HEADER_LEFT, HEADER_RIGHT):
        original = next(c for c in items(dashboard) if c.get("id") == hid)
        viz = original.get("visualization_settings") or {}
        if "dashboard-metabase.png" not in viz.get("text", ""):
            raise RuntimeError("Imagem do cabecalho mudou no card %s; abortando." % hid)


def dashboard_patch(dashboard):
    current = items(dashboard)
    known = {c["id"]: c for c in current}
    new = []
    for item in current:
        card = copy.deepcopy(item)
        cid = card.get("id")
        if cid in POSITIONS:
            x, y, w, h = POSITIONS[cid]
            card.update(col=x, row=y, size_x=w, size_y=h)
        if cid == HEADER_TITLE:
            settings = copy.deepcopy(card.get("visualization_settings") or {})
            settings["text"] = TITLE_TEXT
            card["visualization_settings"] = settings
        # Remove apenas campos de leitura, preservando mappings e configuracoes visuais.
        allowed = ("id", "card_id", "row", "col", "size_x", "size_y",
                   "parameter_mappings", "visualization_settings",
                   "dashboard_tab_id", "action_id", "inline_parameters",
                   "series", "series_settings")
        card = {key: card[key] for key in allowed if key in card}
        new.append(card)

    existing_sections = set()
    for card in new:
        text = (card.get("visualization_settings") or {}).get("text", "")
        if MARK in text:
            existing_sections.add(text.split(MARK + ":")[-1].strip())

    next_id = -1
    for label, y in SECTIONS:
        if label in existing_sections:
            continue
        while any(x.get("id") == next_id for x in new):
            next_id -= 1
        new.append({
            "id": next_id,
            "card_id": None,
            "row": y,
            "col": 0,
            "size_x": 24,
            "size_y": 2,
            "parameter_mappings": [],
            "visualization_settings": {
                "virtual_card": {
                    "name": None, "display": "text",
                    "visualization_settings": {}, "archived": False
                },
                "text": "### " + label + "\n<!-- " + MARK + ":" + label + " -->"
            }
        })
        next_id -= 1

    # A API do Metabase exige que mapeamentos e posicionamento dos cards sejam preservados.
    return {
        "name": dashboard["name"],
        "width": "full",
        "parameters": dashboard["parameters"],
        "dashcards": new,
    }


def snapshot(dashboard):
    filename = "backup_dashboard_cadmus_3_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
    with open(filename, "w", encoding="utf-8") as fp:
        json.dump(dashboard, fp, ensure_ascii=False, indent=2)
    print("Backup local:", os.path.abspath(filename))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore", help="Restaura layout, filtros e textos de backup gerado por este script")
    args = parser.parse_args()
    if not KEY:
        raise RuntimeError("MB_API_KEY nao definida nesta sessao.")

    current = api("GET", "/dashboard/3")
    if args.restore:
        with open(args.restore, encoding="utf-8") as fp:
            old = json.load(fp)
        if old.get("id") != 3 or old.get("name") != EXPECTED_NAME:
            raise RuntimeError("Backup nao corresponde ao dashboard 3.")
        patch = {
            "name": old["name"],
            "width": old.get("width", "full"),
            "parameters": old.get("parameters", []),
            "dashcards": [
                {k: card[k] for k in (
                    "id", "card_id", "row", "col", "size_x", "size_y",
                    "parameter_mappings", "visualization_settings",
                    "dashboard_tab_id", "action_id", "inline_parameters"
                ) if k in card}
                for card in items(old)
            ]
        }
        print("Restauracao:", args.restore)
    else:
        validate_dashboard(current)
        patch = dashboard_patch(current)
        print("Layout planejado: %d cards (incluindo secoes)" % len(patch["dashcards"]))
        for label, y in SECTIONS:
            print("  Secao linha %-2s %s" % (y, label))
        print("  Cabecalho imagens preservadas; titulo central atualizado")
        print("  SLA reduzido; satisfacao alinhada; demais indicadores redistribuidos")

    if not args.apply:
        print("SIMULACAO: nenhuma alteracao realizada. Execute com --apply.")
        return

    snapshot(current)
    api("PUT", "/dashboard/3", patch)
    after = api("GET", "/dashboard/3")
    print("Dashboard atualizado: ID", after.get("id"))
    print("Cards retornados:", len(items(after)))
    print("Filtros globais:", len(after.get("parameters") or []))
    print("Largura:", after.get("width"))
    if len(items(after)) != len(patch["dashcards"]):
        print("ATENCAO: contagem de cards divergiu. Confira a interface e o backup.")
    else:
        print("Layout salvo. Atualize a pagina com Ctrl+F5.")
    print(BASE + "/dashboard/3")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError) as exc:
        sys.exit("ERRO: %s" % exc)
