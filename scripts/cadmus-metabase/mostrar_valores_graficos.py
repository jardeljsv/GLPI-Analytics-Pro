#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Habilita "Mostrar valores nos pontos de dados" nos graficos Cadmus.

Metabase v0.65.3. Percorre a colecao 6 e ativa graph.show_values
nos graficos compativeis, preservando as demais configuracoes.
Nao altera SQL, filtros, banco de dados ou graficos nao compativeis.

Uso:
    python3 mostrar_valores_graficos.py
    python3 mostrar_valores_graficos.py --apply
Requer MB_API_KEY no ambiente.
"""
import argparse
import copy
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("MB_URL", "http://127.0.0.1:3000").rstrip("/")
KEY = os.environ.get("MB_API_KEY", "")
COLLECTION_ID = 6
CHART_DISPLAYS = {"bar", "row", "line", "area", "combo", "scatter", "waterfall"}

def api(method, path, payload=None):
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + "/api" + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            raw = res.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        msg = exc.read().decode("utf-8", errors="replace")
        sys.exit("HTTP %s em %s: %s" % (exc.code, path, msg[:1500]))
    except urllib.error.URLError as exc:
        sys.exit("Falha na conexao: %s" % exc)

def list_collection_cards():
    offset = 0
    limit = 100
    found = []
    seen = set()
    while True:
        path = "/collection/%s/items?models=card&limit=%s&offset=%s" % (COLLECTION_ID, limit, offset)
        response = api("GET", path)
        records = response.get("data", []) if isinstance(response, dict) else response
        if not isinstance(records, list):
            sys.exit("Resposta inesperada na listagem da colecao.")
        for item in records:
            cid = item.get("id")
            if cid not in seen and item.get("model") in ("card", None):
                seen.add(cid)
                found.append(item)
        total = response.get("total") if isinstance(response, dict) else None
        if not records or (total is not None and offset + len(records) >= total) or len(records) < limit:
            break
        offset += len(records)
    return found

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Persiste a configuracao")
    args = parser.parse_args()
    if not KEY:
        sys.exit("MB_API_KEY nao definida no terminal.")
    cards = list_collection_cards()
    print("Perguntas localizadas na colecao %s: %s" % (COLLECTION_ID, len(cards)))
    changed = 0
    skipped = 0
    for item in cards:
        cid = item["id"]
        card = api("GET", "/card/%s" % cid)
        if card.get("collection_id") != COLLECTION_ID or card.get("archived"):
            continue
        display = card.get("display")
        if display not in CHART_DISPLAYS:
            print("IGNORADO %s [%s] - %s" % (cid, display, card.get("name")))
            skipped += 1
            continue
        old = card.get("visualization_settings") or {}
        if old.get("graph.show_values") is True:
            print("OK %s [%s] - valores ja habilitados" % (cid, display))
            continue
        new = copy.deepcopy(old)
        new["graph.show_values"] = True
        print("%s %s [%s] - %s" % (
            "APLICANDO" if args.apply else "SIMULAR", cid, display, card.get("name")))
        if args.apply:
            api("PUT", "/card/%s" % cid, {"visualization_settings": new})
            check = api("GET", "/card/%s" % cid)
            if (check.get("visualization_settings") or {}).get("graph.show_values") is not True:
                sys.exit("Falha ao confirmar o card %s" % cid)
            print("  CONFIRMADO")
        changed += 1
    print("Resumo: %s graficos %s; %s perguntas nao compativeis ignoradas." % (
        changed, "atualizados" if args.apply else "para atualizar", skipped))
    if not args.apply:
        print("Simulacao finalizada sem alteracoes. Para aplicar, execute com --apply.")
    else:
        print("Atualize as paginas do Metabase para conferir os rotulos de dados.")

if __name__ == "__main__":
    main()
