#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ajusta somente o filtro periodo dos cards 42,45,47 para solvedate.

Metabase v0.65.3. Requer MB_API_KEY.
Dry-run: python3 ajustar_periodo_solucao.py
Aplicar: python3 ajustar_periodo_solucao.py --apply
"""
import argparse
import copy
import json
import os
import sys
import urllib.request
import urllib.error

BASE = os.environ.get("MB_URL", "http://127.0.0.1:3000").rstrip("/")
KEY = os.environ.get("MB_API_KEY", "")
CARDS = (42, 45, 47)
DATE_FIELD = 6159
SOLVED_FIELD = 6161

def api(method, path, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + "/api" + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        sys.exit("HTTP %s %s: %s" % (error.code, path, error.read().decode(errors="replace")[:2000]))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not KEY:
        sys.exit("MB_API_KEY nao definida nesta sessao.")
    for card_id in CARDS:
        card = api("GET", "/card/%s" % card_id)
        if card.get("database_id") != 2 or card.get("collection_id") != 6:
            sys.exit("Card %s nao pertence ao banco 2/colecao 6." % card_id)
        query = copy.deepcopy(card["dataset_query"])
        stage = query["stages"][0]
        sql = stage.get("native", "")
        if "FROM glpi_tickets t" not in sql or "{{periodo}}" not in sql:
            sys.exit("SQL inesperado no card %s; nao alterado." % card_id)
        if "solvedate" not in sql:
            sys.exit("Card %s nao referencia solvedate; revisao necessaria." % card_id)
        tags = stage.get("template-tags")
        if isinstance(tags, dict):
            tag = tags.get("periodo")
        elif isinstance(tags, list):
            tag = next((item for item in tags if item.get("name") == "periodo"), None)
        else:
            tag = None
        if not tag or tag.get("type") != "dimension":
            sys.exit("Filtro periodo nao encontrado como Field Filter em %s." % card_id)
        dimension = tag.get("dimension")
        if not (isinstance(dimension, list) and len(dimension) >= 3 and dimension[0] == "field"):
            sys.exit("Referencia do campo periodo inesperada em %s." % card_id)
        current = dimension[2]
        if current == SOLVED_FIELD:
            print("OK (ja corrigido): %s - %s" % (card_id, card["name"]))
            continue
        if current != DATE_FIELD:
            sys.exit("Campo periodo inesperado em %s: %s" % (card_id, current))
        dimension[2] = SOLVED_FIELD
        print("%s: %s | periodo %s -> %s" % (card_id, card["name"], DATE_FIELD, SOLVED_FIELD))
        if args.apply:
            api("PUT", "/card/%s" % card_id, {"dataset_query": query})
            check = api("GET", "/card/%s" % card_id)
            new_tags = check["dataset_query"]["stages"][0].get("template-tags")
            check_tag = new_tags.get("periodo") if isinstance(new_tags, dict) else next(x for x in new_tags if x.get("name") == "periodo")
            if check_tag["dimension"][2] != SOLVED_FIELD:
                sys.exit("Falha de verificacao no card %s." % card_id)
            print("  ATUALIZADO e verificado.")
    if not args.apply:
        print("SIMULACAO: nenhuma pergunta alterada. Utilize --apply para atualizar.")
    print("Obs: teste o filtro periodo=Setembro/2026 em cada pergunta apos a atualizacao.")

if __name__ == "__main__":
    main()
