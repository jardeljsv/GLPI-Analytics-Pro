#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replica os controles da pergunta 40 para as perguntas 42 a 47.

Metabase Cadmus v0.65.3 - API REST.
Simulacao: python3 replicar_listas_filtros.py
Aplicar:   python3 replicar_listas_filtros.py --apply
Requer MB_API_KEY no ambiente. Nao altera GLPI, SQL ou template-tags.
"""
import argparse
import copy
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("MB_URL", "http://127.0.0.1:3000").rstrip("/")
KEY = os.environ.get("MB_API_KEY", "")
SOURCE = 40
TARGETS = (42, 43, 44, 45, 46, 47)
NAMES = ("periodo", "organizacao", "categoria", "tecnico")

def api(method, path, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + "/api" + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        sys.exit("HTTP %s em %s: %s" % (exc.code, path, exc.read().decode(errors="replace")[:1600]))
    except urllib.error.URLError as exc:
        sys.exit("Erro de conexao: %s" % exc)

def tags_by_name(card):
    raw = card["dataset_query"]["stages"][0]["template-tags"]
    return {t["name"]: t for t in (raw.values() if isinstance(raw, dict) else raw)}

def param_name(p):
    target = p.get("target", [])
    if isinstance(target, list) and len(target) > 1 and isinstance(target[1], list) and len(target[1]) > 1:
        return target[1][1]
    return p.get("slug")

def params_by_name(card):
    return {param_name(p): p for p in card.get("parameters", [])}

def validate_card(card):
    if card.get("database_id") != 2 or card.get("collection_id") != 6:
        sys.exit("Pergunta %s fora do banco 2/colecao 6." % card.get("id"))
    tags = tags_by_name(card)
    if not set(NAMES).issubset(tags):
        sys.exit("Pergunta %s sem os quatro template tags." % card["id"])
    if "FROM glpi_tickets t" not in card["dataset_query"]["stages"][0]["native"]:
        sys.exit("Pergunta %s SQL divergente." % card["id"])
    return tags

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not KEY:
        sys.exit("MB_API_KEY nao definida. Configure na mesma sessao.")

    source = api("GET", "/card/%s" % SOURCE)
    source_tags = validate_card(source)
    source_params = params_by_name(source)
    if not set(NAMES).issubset(source_params):
        sys.exit("Pergunta 40 nao tem os quatro parametros no campo parameters.")
    organization = source_params["organizacao"]
    technician = source_params["tecnico"]
    if organization.get("values_source_type") != "static-list":
        sys.exit("Organizacao da pergunta 40 nao esta como lista estatica.")
    if technician.get("values_source_type") != "card" or technician.get("values_source_config", {}).get("card_id") != 41:
        sys.exit("Tecnico da pergunta 40 nao esta usando a pergunta 41.")
    print("ORIGEM: card 40 | Organizacao: lista fixa | Tecnico: pergunta 41")

    for card_id in TARGETS:
        card = api("GET", "/card/%s" % card_id)
        tags = validate_card(card)
        previous = params_by_name(card)
        updated = []
        for name in NAMES:
            item = copy.deepcopy(source_params[name])
            # O ID e o target devem ser da pergunta de destino; por seguranca
            # exigimos que os IDs dos template-tags tenham sido copiados do 40.
            if tags[name].get("id") != source_tags[name].get("id"):
                sys.exit("ID de template-tag divergente para %s no card %s. Sem escrita neste card." % (name, card_id))
            item["id"] = tags[name]["id"]
            if name in previous and previous[name].get("target") is not None:
                item["target"] = copy.deepcopy(previous[name]["target"])
            updated.append(item)
        if card.get("parameters") == updated:
            print("OK %s - %s: ja corresponde a pergunta 40" % (card_id, card["name"]))
            continue
        print("%s %s | Organizacao: lista fixa | Tecnico: card 41 | Periodo: %s" % (
            "ATUALIZAR" if args.apply else "SIMULAR", card_id,
            tags["periodo"]["dimension"][2]))
        if args.apply:
            api("PUT", "/card/%s" % card_id, {"parameters": updated})
            check = api("GET", "/card/%s" % card_id)
            saved = params_by_name(check)
            for name in NAMES:
                if saved.get(name, {}).get("values_source_type") != source_params[name].get("values_source_type"):
                    sys.exit("Verificacao falhou: %s em card %s" % (name, card_id))
            if saved["tecnico"].get("values_source_config", {}).get("card_id") != 41:
                sys.exit("Fonte de tecnico nao persistida em %s" % card_id)
            print("  GRAVADO E VERIFICADO")
    if not args.apply:
        print("SIMULACAO: nenhuma alteracao realizada. Use --apply para gravar.")
    else:
        print("Concluido. Os aliases/date fields do SQL foram preservados.")
        print("Abra as perguntas no Metabase e valide a apresentacao dos controles.")

if __name__ == "__main__":
    main()
