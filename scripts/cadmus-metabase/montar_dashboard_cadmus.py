#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Monta o dashboard Central de Servicos | Cadmus no Metabase v0.65.3.

Sem acesso direto de escrita ao banco Metabase ou GLPI.
Lê perguntas na coleção 6, cria dashboard com quatro filtros globais
e vincula parametros aos cards via API.

Uso:
  python3 montar_dashboard_cadmus.py            # simula
  python3 montar_dashboard_cadmus.py --apply    # cria
Requer MB_API_KEY no ambiente e permissoes de escrita.
"""
import argparse
import copy
import json
import os
import sys
import uuid
import urllib.error
import urllib.request

BASE = os.environ.get("MB_URL", "http://127.0.0.1:3000").rstrip("/")
KEY = os.environ.get("MB_API_KEY", "")
COLLECTION = 6
DATABASE = 2
DASHBOARD_NAME = "Central de Serviços | Cadmus"
REF = 40
# Cada tupla: (card_id, coluna, linha, largura, altura)
# Grade padrão Metabase tem 24 unidades.
LAYOUT = [
    (40, 0, 0, 5, 4),     # Abertos
    (42, 5, 0, 5, 4),     # Solucionados
    (48, 10, 0, 5, 4),    # Nao solucionados do periodo (status atual)
    (45, 15, 0, 5, 4),    # Fora do prazo
    (49, 20, 0, 4, 4),    # Backlog atual
    (46, 0, 4, 12, 8),    # Aberturas mes
    (50, 12, 4, 12, 8),   # Solucoes mes
    (43, 0, 12, 12, 8),   # Organizacoes
    (47, 12, 12, 12, 8), # SLA
    (44, 0, 20, 12, 9),  # Categorias
    (52, 12, 20, 12, 9), # Atrasos por categoria
    (51, 0, 29, 12, 9),  # Backlog atual por categoria
    (55, 12, 29, 12, 9), # Tecnicos
    (53, 0, 38, 8, 5),   # Nota satisfacao
    (54, 8, 38, 16, 8),  # Pesquisas por organizacao
    (56, 0, 46, 24, 11), # Detalhamento atrasos
]
FILTER_NAMES = ("periodo", "organizacao", "categoria", "tecnico")


def api(method, path, payload=None):
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(BASE + "/api" + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=90) as result:
            response = result.read()
            return json.loads(response.decode("utf-8")) if response else {}
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")[:2200]
        raise RuntimeError("HTTP %s em %s: %s" % (error.code, path, details))
    except urllib.error.URLError as error:
        raise RuntimeError("Falha de conexao: %s" % error)


def tag_names(card):
    tags = card["dataset_query"]["stages"][0].get("template-tags", [])
    if isinstance(tags, dict):
        return tags
    return {tag["name"]: tag for tag in tags}


def param_name(p):
    t = p.get("target", [])
    if isinstance(t, list) and len(t) > 1 and isinstance(t[1], list) and len(t[1]) > 1:
        return t[1][1]
    return p.get("slug")


def check_card(card, cid):
    if card.get("database_id") != DATABASE or card.get("collection_id") != COLLECTION:
        raise RuntimeError("Pergunta %d fora do banco 2/colecao 6" % cid)
    if card.get("archived"):
        raise RuntimeError("Pergunta %d arquivada" % cid)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not KEY:
        sys.exit("MB_API_KEY nao configurada nesta sessao.")

    ref = api("GET", "/card/%d" % REF)
    check_card(ref, REF)
    params = ref.get("parameters") or []
    ref_params = {param_name(p): p for p in params}
    if not set(FILTER_NAMES).issubset(ref_params):
        sys.exit("Consulta 40 nao possui as quatro configuracoes de filtros.")

    # O dashboard tem IDs de filtro PROPRIOS. Nao reutiliza IDs internos das perguntas.
    global_params = []
    param_ids = {}
    for name in FILTER_NAMES:
        p = copy.deepcopy(ref_params[name])
        fresh_id = str(uuid.uuid4())
        param_ids[name] = fresh_id
        p["id"] = fresh_id
        p.pop("target", None)
        p.pop("default", None)
        p.pop("slug", None)
        p["name"] = {"periodo": "Período", "organizacao": "Organização",
                     "categoria": "Categoria", "tecnico": "Técnico"}[name]
        global_params.append(p)

    saved_cards = {}
    dashcards = []
    print("Dashboard:", DASHBOARD_NAME, "| Colecao:", COLLECTION)
    for cid, col, row, sx, sy in LAYOUT:
        c = api("GET", "/card/%s" % cid)
        check_card(c, cid)
        saved_cards[cid] = c
        tags = tag_names(c)
        mappings = []
        for name in FILTER_NAMES:
            if name not in tags:
                continue
            # Backlog atual (sem data): nenhuma ligacao do periodo.
            card_parameters = {param_name(p): p for p in (c.get("parameters") or [])}
            target = card_parameters.get(name, {}).get("target")
            if not target:
                target = ["dimension" if tags[name].get("type") == "dimension" else "variable",
                          ["template-tag", name]]
            mappings.append({"parameter_id": param_ids[name],
                             "card_id": cid, "target": target})
        dashcards.append({
            "id": -(len(dashcards) + 1),
            "card_id": cid, "row": row, "col": col, "size_x": sx, "size_y": sy,
            "parameter_mappings": mappings,
            "visualization_settings": {}
        })
        print("  %d | %s | filtros: %s" % (
            cid, c.get("name"), ", ".join(n for n in FILTER_NAMES if n in tags) or "(nenhum)"))

    # Confirma que os parametros de lista do card 40 realmente foram configurados.
    if ref_params["organizacao"].get("values_source_type") != "static-list":
        sys.exit("Organizacao nao tem lista estatica na pergunta 40.")
    if (ref_params["tecnico"].get("values_source_type") != "card" or
            ref_params["tecnico"].get("values_source_config", {}).get("card_id") != 41):
        sys.exit("Tecnico nao esta usando a pergunta 41.")

    collection_items = api("GET", "/collection/%d/items?models=dashboard&limit=100" % COLLECTION)
    entries = collection_items.get("data", [])
    existing = next((x for x in entries if x.get("name") == DASHBOARD_NAME), None)
    if existing:
        sys.exit("Ja existe dashboard com esse nome, ID %s. Nenhuma alteracao realizada. "
                 "Nao vamos sobrescrever um dashboard existente." % existing.get("id"))

    print("Total:", len(dashcards), "cards e", len(global_params), "filtros.")
    if not args.apply:
        print("SIMULACAO. Nenhum dashboard criado. Execute --apply para criar.")
        return

    created = api("POST", "/dashboard", {
        "name": DASHBOARD_NAME,
        "description": ("Cadmus e PeoplePro - entidades 138,140,160,161. "
                        "Backlog: saldo atual; nao solucionados do periodo: situacao atual "
                        "dos chamados abertos no periodo."),
        "collection_id": COLLECTION
    })
    dash_id = created["id"]
    print("Dashboard criado (ID %s). Configurando cards e filtros..." % dash_id)
    try:
        api("PUT", "/dashboard/%s" % dash_id, {
            "parameters": global_params,
            "dashcards": dashcards,
            "name": DASHBOARD_NAME
        })
    except Exception as exc:
        sys.exit("Dashboard %s foi criado, mas a montagem falhou: %s\n"
                 "Confira a API antes de tentar novamente; dashboard vazio pode ser excluido "
                 "pela interface, se necessario." % (dash_id, exc))
    final = api("GET", "/dashboard/%s" % dash_id)
    final_cards = final.get("dashcards") or final.get("ordered_cards") or []
    final_params = final.get("parameters") or []
    print("Conferido na API: %d cards, %d filtros" % (len(final_cards), len(final_params)))
    if len(final_cards) != len(dashcards) or len(final_params) != 4:
        sys.exit("Dashboard criado, mas contagem diverge. Inspecione ID %s." % dash_id)
    print("SUCESSO: %s/dashboard/%s" % (BASE, dash_id))
    print("IMPORTANTE: teste cada filtro global no dashboard. "
          "A API valida os vinculos, mas nao valida todos os valores/combos.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        sys.exit("ERRO: %s" % exc)
