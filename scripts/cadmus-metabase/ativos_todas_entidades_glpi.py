#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gestão de Ativos Cadmus — ampliar consultas para TODAS as entidades GLPI.

ANTES: entidades_id IN (83,137,162)
DEPOIS: todas as entidades, inclusive ROOT (0) e quaisquer outras.

Mantém is_deleted=0 e is_template=0 onde já existem.
Altera SOMENTE as perguntas numeradas 01-19 na coleção Gestão de Ativos | Cadmus.
Não altera Central de Serviços nem tabelas GLPI.
Atualiza a observação textual de escopo no dashboard de Gestão de Ativos.
Cria backup local JSON com conteúdo das perguntas e do dashboard ANTES de gravar.
Pode restaurar com --restore CAMINHO_BACKUP.json --apply.
O processo é idempotente.

Simulação: python3 ativos_todas_entidades_glpi.py
Aplicação: python3 ativos_todas_entidades_glpi.py --apply

Requer MB_API_KEY no ambiente. Opcional MB_URL.
"""
import argparse
import copy
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

API_URL = os.environ.get("MB_URL", "http://127.0.0.1:3000").rstrip("/")
API_KEY = os.environ.get("MB_API_KEY", "")
COLLECTION_NAME = "Gestão de Ativos | Cadmus"
DASHBOARD_NAME = "Gestão de Ativos | Cadmus"
DATABASE_ID = 2

# Deliberadamente limitado ao filtro adotado pelos scripts desta coleção.
# Não transforma outros filtros SQL por entidade.
ENTITY_PATTERN = r"\b(?:[a-zA-Z_][a-zA-Z_0-9]*\.)?entities_id\s+IN\s*\(\s*83\s*,\s*137\s*,\s*162\s*\)"
AND_SCOPE_RE = re.compile(r"\s+AND\s+" + ENTITY_PATTERN + r"\b", re.IGNORECASE)
WHERE_SCOPE_RE = re.compile(r"\bWHERE\s+" + ENTITY_PATTERN + r"\s+AND\s+", re.IGNORECASE)
WHERE_ONLY_SCOPE_RE = re.compile(r"\bWHERE\s+" + ENTITY_PATTERN + r"\b", re.IGNORECASE)
SCOPE_PROSE_RE = re.compile(
    r"Escopo inicial:\s*registros das entidades GLPI\s*83,\s*137\s*e\s*162\.\s*"
    r"Os ativos ainda não estão segregados entre Cadmus e PeoplePro no inventário\.",
    re.IGNORECASE,
)
SCOPE_PROSE_NEW = (
    "Escopo: ativos de todas as entidades do GLPI, incluindo ROOT. "
    "Cadmus e PeoplePro não possuem segregação comprovada no cadastro do parque."
)
DESCRIPTION_REPLACEMENTS = [
    (re.compile(r"entidades\s+GLPI\s+83,\s*137\s+e\s+162", re.I), "todas as entidades do GLPI"),
    (re.compile(r"entidades\s+83,\s*137\s+e\s+162", re.I), "todas as entidades do GLPI"),
    (re.compile(r"entidades\s+83,\s*137,\s*162", re.I), "todas as entidades do GLPI"),
]

def api(method, path, payload=None):
    headers = {"X-API-Key": API_KEY, "Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API_URL + "/api" + path, data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            "HTTP %s em %s: %s" %
            (exc.code, path, exc.read().decode("utf-8", errors="replace")[:2400])
        )
    except urllib.error.URLError as exc:
        raise RuntimeError("Falha ao acessar Metabase: %s" % exc)

def list_items(collection_id, model):
    result = []
    offset = 0
    limit = 100
    while True:
        response = api(
            "GET",
            "/collection/%s/items?models=%s&limit=%s&offset=%s" %
            (collection_id, model, limit, offset),
        )
        batch = response.get("data", []) if isinstance(response, dict) else response
        result.extend(batch)
        total = response.get("total") if isinstance(response, dict) else None
        if not batch or (total is not None and offset + len(batch) >= total) or len(batch) < limit:
            break
        offset += len(batch)
    return result

def find_resources():
    raw = api("GET", "/collection")
    collections = raw if isinstance(raw, list) else raw.get("data", [])
    found = [c for c in collections if c.get("name") == COLLECTION_NAME and not c.get("archived")]
    if len(found) != 1:
        raise RuntimeError("Esperada uma coleção '%s'. Encontradas: %d" %
                           (COLLECTION_NAME, len(found)))
    collection_id = found[0]["id"]
    dashboard_matches = [
        d for d in list_items(collection_id, "dashboard")
        if d.get("name") == DASHBOARD_NAME
    ]
    if len(dashboard_matches) != 1:
        raise RuntimeError("Dashboard '%s' não localizado de forma única" % DASHBOARD_NAME)
    return collection_id, dashboard_matches[0]["id"]

def get_sql(card):
    q = card.get("dataset_query") or {}
    if "stages" in q:
        stages = q["stages"]
        if not stages or not isinstance(stages[0].get("native"), str):
            raise RuntimeError("Card %s não possui SQL nativo no formato stages" % card["id"])
        return stages[0]["native"], "stages"
    native = q.get("native")
    if isinstance(native, dict) and isinstance(native.get("query"), str):
        return native["query"], "legacy"
    raise RuntimeError("Card %s não possui SQL nativo conhecido" % card["id"])

def set_sql(query, sql, fmt):
    q = copy.deepcopy(query)
    if fmt == "stages":
        q["stages"][0]["native"] = sql
    else:
        q["native"]["query"] = sql
    return q

def strip_entity_scope(sql):
    original = sql
    # Não substitui outras condições e não elimina escopo de tickets.
    sql = AND_SCOPE_RE.sub("", sql)
    sql = WHERE_SCOPE_RE.sub("WHERE ", sql)
    sql = WHERE_ONLY_SCOPE_RE.sub("WHERE 1=1", sql)
    remaining = re.search(ENTITY_PATTERN, sql, flags=re.I)
    if remaining:
        raise RuntimeError("Ainda há filtro de entidade-alvo não removido: %s" %
                           remaining.group(0))
    return sql, sql != original

def section_changed(text):
    new_text = SCOPE_PROSE_RE.sub(SCOPE_PROSE_NEW, text)
    # Outras descrições pré-existentes dos scripts.
    new_text = re.sub(
        r"Escopo inicial:\s*entidades GLPI\s*83,\s*137\s*e\s*162",
        "Escopo: todas as entidades do GLPI", new_text, flags=re.I
    )
    return new_text

def updated_dashboard(dashboard):
    cards = dashboard.get("dashcards") or dashboard.get("ordered_cards") or []
    updates = []
    new_cards = []
    for item in cards:
        new = copy.deepcopy(item)
        viz = new.get("visualization_settings") or {}
        if new.get("card_id") is None and isinstance(viz.get("text"), str):
            old_text = viz["text"]
            new_text = section_changed(old_text)
            if old_text != new_text:
                viz["text"] = new_text
                new["visualization_settings"] = viz
                updates.append(new.get("id"))
        kept = (
            "id", "card_id", "row", "col", "size_x", "size_y",
            "parameter_mappings", "visualization_settings", "dashboard_tab_id",
            "action_id", "inline_parameters"
        )
        new_cards.append({k: copy.deepcopy(new[k]) for k in kept if k in new})
    return {
        "name": dashboard["name"],
        "width": dashboard.get("width", "full"),
        "parameters": copy.deepcopy(dashboard.get("parameters", [])),
        "dashcards": new_cards,
    }, updates

def description_update(text):
    current = text or ""
    result = current
    for rx, replacement in DESCRIPTION_REPLACEMENTS:
        result = rx.sub(replacement, result)
    return result

def make_backup(cards, dashboard):
    path = "backup_ativos_todas_entidades_%s.json" % dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "dashboard": dashboard,
            "cards": cards,
            "collection": COLLECTION_NAME,
            "created_at": dt.datetime.now().isoformat(),
        }, f, ensure_ascii=False, indent=2)
    print("Backup salvo:", os.path.abspath(path))

def restore(backup_path, apply):
    with open(backup_path, encoding="utf-8") as f:
        state = json.load(f)
    old_dashboard = state["dashboard"]
    old_cards = state["cards"]
    collection_id, dashboard_id = find_resources()
    if state.get("collection") != COLLECTION_NAME or old_dashboard.get("id") != dashboard_id:
        raise RuntimeError("Backup não corresponde ao dashboard atual")
    for saved in old_cards:
        remote = api("GET", "/card/%d" % saved["id"])
        if remote.get("collection_id") != collection_id:
            raise RuntimeError("Card %s mudou de coleção; restaurar cancelado" % saved["id"])
    print("Restaurar %d perguntas e layout do dashboard %d" % (len(old_cards), dashboard_id))
    if not apply:
        print("SIMULAÇÃO: para restaurar execute --restore ... --apply")
        return
    for saved in old_cards:
        api("PUT", "/card/%s" % saved["id"], {
            "dataset_query": saved["dataset_query"],
            "description": saved.get("description", ""),
        })
        print("RESTAURADO card", saved["id"])
    patch, _ = updated_dashboard(old_dashboard)
    # Restaurar o texto literal do backup, sem a transformação de escopo
    stored_cards = old_dashboard.get("dashcards") or old_dashboard.get("ordered_cards") or []
    for target, original in zip(patch["dashcards"], stored_cards):
        target["visualization_settings"] = original.get("visualization_settings", {})
    api("PUT", "/dashboard/%s" % dashboard_id, patch)
    print("RESTAURADO dashboard", dashboard_id)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Aplica atualização")
    parser.add_argument("--restore", metavar="BACKUP_JSON", help="Restaurar de backup")
    args = parser.parse_args()
    if not API_KEY:
        raise RuntimeError("MB_API_KEY não configurada")
    if args.restore:
        restore(args.restore, args.apply)
        return

    collection_id, dashboard_id = find_resources()
    dashboard = api("GET", "/dashboard/%s" % dashboard_id)
    if dashboard.get("name") != DASHBOARD_NAME:
        raise RuntimeError("Dashboard de nome inesperado")
    all_items = list_items(collection_id, "card")
    relevant = []
    for item in all_items:
        name = item.get("name", "")
        if re.match(r"^(?:0[1-9]|1[0-9])\s+\|", name):
            card = api("GET", "/card/%s" % item["id"])
            if card.get("database_id") != DATABASE_ID:
                raise RuntimeError("Banco inesperado para card %s" % card["id"])
            relevant.append(card)
    if not relevant:
        raise RuntimeError("Não foram encontradas perguntas numeradas 01-19")

    print("Gestão de Ativos | Cadmus. Dashboard ID:", dashboard_id)
    print("Perguntas localizadas:", len(relevant))
    print("Novo escopo: TODAS as entidades do GLPI, incluindo ROOT")
    modified = []
    for card in relevant:
        sql, fmt = get_sql(card)
        updated, changed = strip_entity_scope(sql)
        old_desc = card.get("description")
        desc = description_update(old_desc)
        if changed or (old_desc or "") != desc:
            modified.append((card, set_sql(card["dataset_query"], updated, fmt), desc))
            print("ALTERAR %s | %s | SQL=%s" %
                  (card["id"], card["name"], "sim" if changed else "não"))
        else:
            print("OK      %s | %s" % (card["id"], card["name"]))
    dashboard_patch, text_cards = updated_dashboard(dashboard)
    print("Elementos textuais do dashboard a atualizar:", text_cards)
    if not args.apply:
        print("SIMULAÇÃO concluída: %d perguntas a atualizar. Nada foi modificado." % len(modified))
        print("Para aplicar: python3 ativos_todas_entidades_glpi.py --apply")
        return
    if not modified and not text_cards:
        print("Tudo já está atualizado. Nenhuma alteração necessária.")
        return

    make_backup(relevant, dashboard)
    for card, query, description in modified:
        api("PUT", "/card/%s" % card["id"], {
            "dataset_query": query,
            "description": description,
        })
        print("ATUALIZADA pergunta", card["id"])
    if text_cards:
        api("PUT", "/dashboard/%s" % dashboard_id, dashboard_patch)
        print("ATUALIZADO texto do dashboard", dashboard_id)
    print("Concluído. Consultas de Gestão de Ativos agora incluem TODAS as entidades.")
    print("Recarregue o dashboard em:", API_URL + "/dashboard/" + str(dashboard_id))

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, KeyError, ValueError, OSError) as e:
        sys.exit("ERRO: %s" % e)
