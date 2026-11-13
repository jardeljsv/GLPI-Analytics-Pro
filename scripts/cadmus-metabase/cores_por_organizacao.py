#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Metabase Cadmus: cores fixas por empresa em graficos de volumetria.

Perguntas afetadas:
43 - Volumetria por Organizacao (chamados abertos)
14 - Pesquisas Respondidas por Organizacao (localizada pelo nome, se existir)

Os dados passam a ter DUAS series SQL (Cadmus e PeoplePro). Grafico
de barras agrupadas: Cadmus #0D2A43; PeoplePro #FF873F.
Preserva os filtros, parametros, alias, banco e colecao.
Nao modifica GLPI ou banco interno do Metabase diretamente.

Uso: python3 cores_por_organizacao.py [--apply]
Requer MB_API_KEY no ambiente.
"""
import argparse
import copy
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("MB_URL", "http://127.0.0.1:3000").rstrip("/")
KEY = os.environ.get("MB_API_KEY", "")
BLUE = "#0D2A43"
ORANGE = "#FF873F"
COLLECTION = 6
DATABASE = 2

def api(method, path, obj=None):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8") if obj is not None else None
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    if obj is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + "/api" + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        sys.exit("HTTP %s %s: %s" % (exc.code, path, exc.read().decode(errors="replace")[:1600]))
    except urllib.error.URLError as exc:
        sys.exit("Conexao: %s" % exc)

def replace_grouped_sql(sql, kind):
    if "FROM glpi_tickets t" not in sql:
        raise ValueError("Nao localizei FROM glpi_tickets t.")
    _, rest = sql.split("FROM glpi_tickets t", 1)
    # Somente remove o GROUP BY externo esperado ao final da consulta.
    group_tail = re.search(r"\nGROUP BY organizacao\s+ORDER BY\s+\w+\s+DESC\s*;?\s*$", rest, re.I)
    if not group_tail:
        raise ValueError("GROUP BY final inesperado. SQL mantido sem modificacoes.")
    rest = rest[:group_tail.start()].rstrip().rstrip(";")
    if kind == "tickets":
        cadmus_expr = "COUNT(DISTINCT CASE WHEN t.entities_id IN (138, 160) THEN t.id END)"
        people_expr = "COUNT(DISTINCT CASE WHEN t.entities_id IN (140, 161) THEN t.id END)"
    elif kind == "satisfacao":
        if "glpi_ticketsatisfactions s" not in rest:
            raise ValueError("Pesquisa de satisfacao sem JOIN s.")
        cadmus_expr = "COUNT(DISTINCT CASE WHEN t.entities_id IN (138, 160) THEN s.id END)"
        people_expr = "COUNT(DISTINCT CASE WHEN t.entities_id IN (140, 161) THEN s.id END)"
    else:
        raise ValueError("Tipo invalido")
    return (
        "SELECT 'Organizações' AS grupo,\n"
        "       " + cadmus_expr + " AS Cadmus,\n"
        "       " + people_expr + " AS PeoplePro\n"
        "FROM glpi_tickets t" + rest
    )

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    if not KEY:
        sys.exit("Defina MB_API_KEY na sessao.")

    cards = [(43, "tickets")]
    listing = api("GET", "/collection/%s/items?models=card&limit=500" % COLLECTION)
    for item in listing.get("data", []):
        if item.get("name") == "CS Cadmus | 14 - Pesquisas Respondidas por Organizacao":
            cards.append((item["id"], "satisfacao"))
            break

    for card_id, kind in cards:
        card = api("GET", "/card/%s" % card_id)
        if card.get("database_id") != DATABASE or card.get("collection_id") != COLLECTION:
            sys.exit("Card %s fora do banco 2/colecao 6" % card_id)
        query = copy.deepcopy(card["dataset_query"])
        stage = query["stages"][0]
        sql = stage["native"]
        if "AS Cadmus" in sql and "AS PeoplePro" in sql:
            updated_sql = sql
        else:
            try:
                updated_sql = replace_grouped_sql(sql, kind)
            except ValueError as e:
                sys.exit("Card %s: %s" % (card_id, e))
        stage["native"] = updated_sql
        viz = copy.deepcopy(card.get("visualization_settings") or {})
        viz["graph.dimensions"] = ["grupo"]
        viz["graph.metrics"] = ["Cadmus", "PeoplePro"]
        viz["graph.colors"] = [BLUE, ORANGE]
        viz["series_settings"] = {
            "Cadmus": {"color": BLUE},
            "PeoplePro": {"color": ORANGE},
        }
        viz["graph.show_values"] = True
        payload = {"dataset_query": query, "display": "bar", "visualization_settings": viz}
        if updated_sql == sql and card.get("display") == "bar" and (card.get("visualization_settings") or {}) == viz:
            print("OK %s - ja padronizado" % card_id)
            continue
        print("%s %s - Cadmus %s | PeoplePro %s" % (
            "APLICAR" if args.apply else "SIMULAR", card_id, BLUE, ORANGE))
        if args.apply:
            api("PUT", "/card/%s" % card_id, payload)
            after = api("GET", "/card/%s" % card_id)
            settings = after.get("visualization_settings") or {}
            if settings.get("graph.colors") != [BLUE, ORANGE] or "AS PeoplePro" not in after["dataset_query"]["stages"][0]["native"]:
                sys.exit("Card %s: falha de verificacao" % card_id)
            print("  GRAVADO E VERIFICADO")

    if len(cards) == 1:
        print("Pergunta 14 de pesquisas por organizacao nao encontrada; pode rodar novamente depois de cria-la.")
    if not args.apply:
        print("Simulacao concluida, nada modificado. Para aplicar: --apply")
    else:
        print("Pronto. Recarregue as perguntas no Metabase e confira as duas series.")

if __name__ == "__main__":
    main()
