#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Corrige mapeamento de alias em Field Filters do Metabase Cadmus.

Uso:
    python3 corrigir_alias_filtros.py
    python3 corrigir_alias_filtros.py --apply

Altera apenas o atributo 'alias' de template tags do tipo dimension.
Nao altera SQL, cards, banco GLPI ou banco de aplicacao diretamente.
"""
import argparse
import copy
import json
import os
import sys
import urllib.request
import urllib.error

BASE = os.environ.get("MB_URL", "http://127.0.0.1:3000").rstrip("/")
KEY = os.environ.get("MB_API_KEY")
CARDS = (40, 42, 43, 44, 45, 46, 47)
DATE_IDS = {6159: "t.date", 6161: "t.solvedate"}
CAT_ID = 2616

def api(method, path, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + "/api" + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        sys.exit("HTTP %s em %s: %s" % (e.code, path, e.read().decode(errors="replace")[:1200]))

def named_tags(stage):
    tags = stage.get("template-tags", [])
    if isinstance(tags, list):
        return {t.get("name"): t for t in tags}
    if isinstance(tags, dict):
        return tags
    sys.exit("Formato de template-tags inesperado")

def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--apply", action="store_true")
    args = arg.parse_args()
    if not KEY:
        sys.exit("Configure MB_API_KEY antes de executar.")
    for card_id in CARDS:
        card = api("GET", "/card/%d" % card_id)
        if card.get("database_id") != 2 or card.get("collection_id") != 6:
            sys.exit("Card %s fora do banco 2 / colecao 6. Nada alterado para este card." % card_id)
        query = copy.deepcopy(card["dataset_query"])
        stage = query["stages"][0]
        sql = stage.get("native", "")
        if "FROM glpi_tickets t" not in sql:
            sys.exit("SQL da pergunta %s nao tem alias t esperado." % card_id)
        tags = named_tags(stage)
        edits = []
        for name, field, mapping in (
            ("periodo", DATE_IDS, None),
            ("categoria", None, "c.completename")
        ):
            tag = tags.get(name)
            if not tag or tag.get("type") != "dimension":
                continue
            dim = tag.get("dimension", [])
            if not isinstance(dim, list) or len(dim) < 3 or dim[0] != "field":
                sys.exit("Referencia inesperada para %s em %s." % (name, card_id))
            field_id = dim[2]
            expected = field.get(field_id) if field else (mapping if field_id == CAT_ID else None)
            if not expected:
                sys.exit("Campo inesperado %s (%s) na pergunta %s." % (name, field_id, card_id))
            if name == "categoria" and "JOIN glpi_itilcategories c" not in sql:
                sys.exit("Card %s nao tem JOIN de categoria c." % card_id)
            if tag.get("alias") != expected:
                edits.append((name, tag.get("alias"), expected))
                tag["alias"] = expected
        if not edits:
            print("OK %s - %s (aliases ja configurados)" % (card_id, card["name"]))
            continue
        for name, before, after in edits:
            print("%s | %s: %s | %r -> %r" % (card_id, card["name"], name, before, after))
        if args.apply:
            api("PUT", "/card/%d" % card_id, {"dataset_query": query})
            check = named_tags(api("GET", "/card/%d" % card_id)["dataset_query"]["stages"][0])
            for name, _, after in edits:
                if check[name].get("alias") != after:
                    sys.exit("ERRO: alias nao persistido em %s (%s)" % (card_id, name))
            print("  ATUALIZADO E VERIFICADO")
    if not args.apply:
        print("SIMULACAO concluida. Para aplicar: python3 corrigir_alias_filtros.py --apply")
    else:
        print("Correcoes persistidas. Teste o filtro Periodo e Categoria nas perguntas.")

if __name__ == "__main__":
    main()
