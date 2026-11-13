#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove comentarios CS_CADMUS_SECTION_V1 visiveis nos blocos de texto do dashboard 3.

Modo seguro: altera apenas visualization_settings.text dos cards virtuais que
contem a marca. Mantem titulo, imagens, filtros, posicoes e graficos.
Cria backup JSON completo antes de aplicar.

Uso:
  python3 corrigir_titulos_secoes.py
  python3 corrigir_titulos_secoes.py --apply
"""
import argparse
import copy
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("MB_URL", "http://127.0.0.1:3000").rstrip("/")
KEY = os.environ.get("MB_API_KEY", "")
MARK = "CS_CADMUS_SECTION_V1"
PATTERN = re.compile(r"\\?<!--\s*" + MARK + r":[^\r\n]*?-->", flags=re.I)
# Reconhece tambem a forma escapada em texto Markdown.
ESCAPED = re.compile(r"\\?<!--\s*" + MARK + r":[^\r\n]*?-->")

def api(method, path, obj=None):
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    payload = None
    if obj is not None:
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + "/api" + path, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = resp.read()
            return json.loads(data.decode("utf-8")) if data else {}
    except urllib.error.HTTPError as err:
        sys.exit("HTTP %s em %s: %s" % (err.code, path, err.read().decode(errors="replace")[:1500]))

def items(d):
    return d.get("dashcards") or d.get("ordered_cards") or []

def scrub(text):
    # O script original salvou comentarios HTML literais que o Metabase mostra.
    # Remove apenas comentarios com a marca exata da nossa automacao.
    result = ESCAPED.sub("", text)
    result = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", result).strip()
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not KEY:
        sys.exit("Variavel MB_API_KEY ausente.")
    d = api("GET", "/dashboard/3")
    if d.get("name") != "Central de Serviços | Cadmus":
        sys.exit("Nome do dashboard inesperado: nenhuma alteracao.")
    original = items(d)
    updated = []
    changed = []
    for item in original:
        x = copy.deepcopy(item)
        viz = copy.deepcopy(x.get("visualization_settings") or {})
        text = viz.get("text", "")
        if MARK in text:
            cleaned = scrub(text)
            if not cleaned or cleaned == text:
                sys.exit("Nao foi possivel limpar o card %s de forma segura" % x.get("id"))
            viz["text"] = cleaned
            x["visualization_settings"] = viz
            changed.append((x.get("id"), cleaned))
        keep = ("id", "card_id", "row", "col", "size_x", "size_y",
                "parameter_mappings", "visualization_settings", "dashboard_tab_id",
                "action_id", "inline_parameters")
        updated.append({k: x[k] for k in keep if k in x})

    print("Secoes a limpar:", len(changed))
    for card_id, title in changed:
        print("  Card %s => %r" % (card_id, title))
    if not changed:
        print("Nenhum comentario da automacao encontrado; nada a fazer.")
        return
    if not args.apply:
        print("SIMULACAO. Execute com --apply para corrigir.")
        return

    filename = "backup_dashboard_cadmus_3_antes_limpar_comentarios_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
    with open(filename, "w", encoding="utf-8") as out:
        json.dump(d, out, ensure_ascii=False, indent=2)
    print("Backup:", os.path.abspath(filename))
    api("PUT", "/dashboard/3", {
        "name": d["name"], "width": d.get("width", "full"),
        "parameters": d.get("parameters", []),
        "dashcards": updated
    })
    confirmed = api("GET", "/dashboard/3")
    remain = [(c.get("id"), (c.get("visualization_settings") or {}).get("text", ""))
              for c in items(confirmed)
              if MARK in (c.get("visualization_settings") or {}).get("text", "")]
    if remain:
        sys.exit("Ainda ha comentarios nos cards: %s" % [x[0] for x in remain])
    print("CORRIGIDO: %d titulos; imagens, filtros e graficos preservados." % len(changed))
    print("Abra %s/dashboard/3 e atualize com Ctrl+F5." % BASE)

if __name__ == "__main__":
    main()
