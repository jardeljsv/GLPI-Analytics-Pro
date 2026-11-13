#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Paleta visual Cadmus - Metabase v0.65.3

Atualiza somente visualization_settings das perguntas com graficos existentes:
  43 - Volumetria por Organizacao
  44 - Top 10 Categorias
  46 - Aberturas por Mes

Simulacao: python3 padronizar_cores_cadmus.py
Aplicar:   python3 padronizar_cores_cadmus.py --apply

Requer MB_API_KEY no ambiente. Nao altera SQL, filtros, bancos ou cards numericos.
NOTA: uma unica serie no grafico por organizacao usa uma so cor.
Para Cadmus azul / PeoplePro laranja no mesmo grafico sera necessario
um grafico com series distintas (ou visualizacao com mapeamento por categoria).
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
NAVY = "#0D2A43"       # azul-marinho Cadmus, aproximacao das capturas
GREEN = "#70DC68"      # solucionados / SLA, aproximacao
ORANGE = "#FF873F"     # PeoplePro, aproximacao
GRAY = "#80868B"       # backlog, aproximacao
BG = "#E4EBF1"         # referencia visual para dashboard/embedding
CARDS = {
    43: ("chamados_abertos", NAVY),
    44: ("total_chamados", NAVY),
    46: ("abertos", NAVY),
}

def api(method, path, data=None):
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    payload = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE + "/api" + path, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as res:
            return json.load(res)
    except urllib.error.HTTPError as exc:
        sys.exit("HTTP %s em %s: %s" % (exc.code, path, exc.read().decode(errors="replace")[:2000]))
    except urllib.error.URLError as exc:
        sys.exit("Conexao: %s" % exc)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    if not KEY:
        sys.exit("MB_API_KEY nao definida. Configure localmente no servidor.")
    print("Paleta: Cadmus %s | Solucionados %s | PeoplePro %s | Backlog %s" % (NAVY, GREEN, ORANGE, GRAY))
    print("Fundo de referencia (nao aplicado): %s" % BG)
    for card_id, (series_key, color) in CARDS.items():
        card = api("GET", "/card/%d" % card_id)
        if card.get("database_id") != 2 or card.get("collection_id") != 6:
            sys.exit("Card %s nao pertence a banco 2/colecao 6" % card_id)
        if card.get("display") not in ("bar", "row", "line", "area"):
            sys.exit("Card %s nao e grafico esperado (%s)" % (card_id, card.get("display")))
        viz = copy.deepcopy(card.get("visualization_settings") or {})
        # series_settings isola alteracoes por serie sem substituir outras configuracoes.
        series = viz.setdefault("series_settings", {})
        item = series.setdefault(series_key, {})
        item["color"] = color
        viz["graph.colors"] = [color]
        if viz == (card.get("visualization_settings") or {}):
            print("OK %s: cor ja configurada" % card_id)
            continue
        print("%s %s - %s -> %s" % ("APLICAR" if args.apply else "SIMULAR", card_id, series_key, color))
        if args.apply:
            api("PUT", "/card/%d" % card_id, {"visualization_settings": viz})
            check = api("GET", "/card/%d" % card_id).get("visualization_settings") or {}
            if check.get("series_settings", {}).get(series_key, {}).get("color") != color:
                sys.exit("Falha de verificacao na pergunta %s" % card_id)
            print("  CONFIRMADO")
    if not args.apply:
        print("Simulacao concluida. Execute --apply para atualizar.")
    else:
        print("Cores basicas aplicadas. Atualize a pagina do Metabase (Ctrl+F5).")
        print("Cards numericos e tema global NAO foram alterados.")

if __name__ == "__main__":
    main()
