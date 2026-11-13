#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Etapa 2: novos indicadores Cadmus no Metabase v0.65.3.

Simulacao: python3 cadmus_metabase_etapa2.py
Aplicacao: python3 cadmus_metabase_etapa2.py --apply
Requisitos: MB_API_KEY no ambiente; Metabase local 127.0.0.1:3000.
Somente API REST: nao altera tabelas do GLPI, views ou banco do Metabase.
Fonte: card 40, banco 2, colecao 6. Preserva cards existentes.
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
COLLECTION = 6
DATABASE = 2
NAVY = "#0D2A43"
GREEN = "#70DC68"
ORANGE = "#FF873F"
GRAY = "#80868B"

def api(method, path, payload=None):
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE + "/api" + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as e:
        sys.exit("ERRO HTTP %s em %s: %s" % (e.code, path, e.read().decode(errors="replace")[:1300]))
    except urllib.error.URLError as e:
        sys.exit("Falha de conexao: %s" % e)

def native_tags(stage):
    raw = stage.get("template-tags", [])
    if not isinstance(raw, list):
        sys.exit("Esperado template-tags como lista; revise card 40.")
    return raw

def metadata_field_id(table_name, field_name):
    # Descobre o ID na propria fonte, sem depender de IDs de homologacao.
    md = api("GET", "/database/%d/metadata" % DATABASE)
    for table in md.get("tables", []):
        if table.get("name") == table_name:
            for fld in table.get("fields", []):
                if fld.get("name") == field_name:
                    return fld.get("id")
    return None

def configure(template, date_field=None, omit_period=False):
    query = copy.deepcopy(template["dataset_query"])
    stage = query["stages"][0]
    params = copy.deepcopy(template.get("parameters") or [])
    if omit_period:
        stage["template-tags"] = [p for p in native_tags(stage) if p["name"] != "periodo"]
        params = [p for p in params if p.get("slug") != "periodo" and p.get("name") != "Periodo"]
    elif date_field is not None:
        field_id, alias = date_field
        tag = next(x for x in native_tags(stage) if x["name"] == "periodo")
        tag["dimension"][2] = field_id
        tag["alias"] = alias
    return query, params

def series_style(field, color):
    return {"graph.colors": [color], "series_settings": {field: {"color": color}}}

def definition(name, display, selected, where="", group="", mode="date", color=NAVY, join_s=False, explanation=""):
    return dict(name=name, display=display, selected=selected, where=where, group=group, mode=mode, color=color, join_s=join_s, explanation=explanation)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    if not KEY:
        sys.exit("Defina MB_API_KEY na sessao do terminal.")

    reference = api("GET", "/card/%d" % SOURCE)
    if reference.get("database_id") != DATABASE or reference.get("collection_id") != COLLECTION:
        sys.exit("Card 40 nao pertence a banco 2/colecao 6.")
    base = reference["dataset_query"]["stages"][0]["native"]
    if "FROM glpi_tickets t" not in base or "[[AND {{periodo}}]]" not in base:
        sys.exit("SQL do card 40 alterado; nao e seguro clonar.")
    base = base[base.index("FROM glpi_tickets t"):].strip().rstrip(";").strip()
    if "LEFT JOIN glpi_itilcategories c" not in base:
        sys.exit("Card 40 sem alias c de categoria.")
    expected = {"periodo", "organizacao", "categoria", "tecnico"}
    if {t["name"] for t in native_tags(reference["dataset_query"]["stages"][0])} != expected:
        sys.exit("Os quatro filtros do card 40 mudaram; inspecione.")
    if not reference.get("parameters"):
        sys.exit("Card 40 sem configuracao de controles de filtros.")

    date_answered_id = metadata_field_id("glpi_ticketsatisfactions", "date_answered")
    print("Campo data_resposta (glpi_ticketsatisfactions.date_answered):", date_answered_id)
    # Sem ID, nao criamos perguntas de satisfacao com periodo inadequado.
    defs = [
      definition("CS Cadmus | 08 - Nao Solucionados do Periodo", "scalar",
        "SELECT COUNT(DISTINCT t.id) AS nao_solucionados",
        "AND t.status NOT IN (5,6)", mode="date",
        explanation="Chamados abertos no periodo que permanecem nao solucionados AGORA."),
      definition("CS Cadmus | 09 - Backlog Atual", "scalar",
        "SELECT COUNT(DISTINCT t.id) AS backlog_atual",
        "AND t.status NOT IN (5,6)", mode="none", color=GRAY,
        explanation="Total nao solucionado AGORA; sem parametro periodo, deliberadamente."),
      definition("CS Cadmus | 10 - Solucoes por Mes", "bar",
        "SELECT DATE_FORMAT(t.solvedate, '%Y-%m-01') AS mes, COUNT(DISTINCT t.id) AS solucionados",
        "AND t.solvedate IS NOT NULL",
        "GROUP BY DATE_FORMAT(t.solvedate, '%Y-%m-01') ORDER BY mes", mode="solved",
        color=GREEN, explanation="Serie mensal pela DATA DE SOLUCAO."),
      definition("CS Cadmus | 11 - Backlog Atual por Categoria", "row",
        "SELECT COALESCE(NULLIF(c.completename,''),'Sem categoria') AS categoria, COUNT(DISTINCT t.id) AS backlog",
        "AND t.status NOT IN (5,6)",
        "GROUP BY c.id,c.completename ORDER BY backlog DESC", mode="none", color=GRAY,
        explanation="Backlog atual por categoria; nao deve receber filtro periodo."),
      definition("CS Cadmus | 12 - Fora do Prazo por Categoria", "row",
        "SELECT COALESCE(NULLIF(c.completename,''),'Sem categoria') AS categoria, COUNT(DISTINCT t.id) AS atrasados",
        "AND t.solvedate IS NOT NULL AND t.time_to_resolve IS NOT NULL AND t.solvedate > t.time_to_resolve",
        "GROUP BY c.id,c.completename ORDER BY atrasados DESC LIMIT 10", mode="solved",
        explanation="Top 10 atrasos TTR por data de solucao."),
      definition("CS Cadmus | 13 - Nota Media de Satisfacao", "scalar",
        "SELECT ROUND(AVG(s.satisfaction_scaled_to_5),2) AS nota_media",
        "AND s.date_answered IS NOT NULL AND s.satisfaction_scaled_to_5 IS NOT NULL",
        mode="answered", join_s=True,
        explanation="Media de respostas recebidas no periodo selecionado."),
      definition("CS Cadmus | 14 - Pesquisas Respondidas por Organizacao", "bar",
        """SELECT CASE WHEN t.entities_id IN (138,160) THEN 'Cadmus'
                    ELSE 'PeoplePro' END AS organizacao,
               COUNT(DISTINCT s.id) AS respostas""",
        "AND s.date_answered IS NOT NULL",
        "GROUP BY organizacao ORDER BY respostas DESC", mode="answered", join_s=True,
        explanation="Respostas por organizacao, filtradas por data de resposta."),
      definition("CS Cadmus | 15 - Atendimentos por Tecnico", "row",
        """SELECT TRIM(CONCAT_WS(' ',NULLIF(TRIM(u2.firstname),''),NULLIF(TRIM(u2.realname),''))) AS tecnico,
               COUNT(DISTINCT t.id) AS atendimentos""",
        """AND t.solvedate IS NOT NULL
           AND u2.is_deleted = 0
           AND TRIM(CONCAT_WS(' ',NULLIF(TRIM(u2.firstname),''),NULLIF(TRIM(u2.realname),''))) <> ''""",
        "GROUP BY u2.id,u2.firstname,u2.realname ORDER BY atendimentos DESC LIMIT 20", mode="solved",
        explanation="Chamados solucionados por tecnico atribuido; um chamado pode contar para varios tecnicos."),
      definition("CS Cadmus | 16 - Chamados Fora do Prazo Detalhamento", "table",
        """SELECT t.id AS chamado, t.name AS titulo,
           CASE WHEN t.entities_id IN (138,160) THEN 'Cadmus' ELSE 'PeoplePro' END AS organizacao,
           COALESCE(c.completename,'Sem categoria') AS categoria,
           t.date AS abertura, t.solvedate AS solucao, t.time_to_resolve AS prazo_ttr,
           (SELECT GROUP_CONCAT(DISTINCT TRIM(CONCAT_WS(' ',NULLIF(TRIM(ut.firstname),''),NULLIF(TRIM(ut.realname),''))) SEPARATOR ', ')
              FROM glpi_tickets_users tu2
              JOIN glpi_users ut ON ut.id=tu2.users_id
              WHERE tu2.tickets_id=t.id AND tu2.type=2) AS tecnicos""",
        "AND t.solvedate IS NOT NULL AND t.time_to_resolve IS NOT NULL AND t.solvedate > t.time_to_resolve",
        "ORDER BY t.solvedate DESC LIMIT 2000", mode="solved",
        explanation="Detalhe de chamados com TTR vencido ao solucionar."),
    ]

    # Duas perguntas incluem uma JOIN extra para os nomes de tecnico sem alterar
    # o filtro tecnico original (que usa EXISTS e evita duplicacao).
    available = api("GET", "/collection/%d/items?models=card&limit=500" % COLLECTION)
    items = available.get("data", []) if isinstance(available, dict) else available
    seen = {c.get("name"): c.get("id") for c in items if isinstance(c, dict)}
    print("Total planejado:", len(defs))
    for d in defs:
        if d["name"] in seen:
            print("EXISTE: %s (ID %s)" % (d["name"], seen[d["name"]]))
            continue
        if d["mode"] == "answered" and not date_answered_id:
            print("ADIADA (campo de data nao encontrado):", d["name"])
            continue
        date_map = {"date": (6159, "t.date"), "solved": (6161, "t.solvedate"),
                    "answered": (date_answered_id, "s.date_answered")}
        query, params = configure(reference, date_map.get(d["mode"]), omit_period=(d["mode"] == "none"))
        sql_base = base
        if d["mode"] == "none":
            sql_base = sql_base.replace("[[AND {{periodo}}]]", "")
        if d["join_s"]:
            pos = sql_base.index("WHERE")
            sql_base = sql_base[:pos] + "LEFT JOIN glpi_ticketsatisfactions s ON s.tickets_id = t.id\n" + sql_base[pos:]
        if "Atendimentos por Tecnico" in d["name"]:
            pos = sql_base.index("WHERE")
            sql_base = sql_base[:pos] + ("JOIN glpi_tickets_users tu2 ON tu2.tickets_id=t.id AND tu2.type=2\n"
                                        "JOIN glpi_users u2 ON u2.id=tu2.users_id\n") + sql_base[pos:]
        sql = d["selected"] + "\n" + sql_base + "\n" + d["where"] + "\n" + d["group"]
        query["stages"][0]["native"] = sql.strip()
        color_keys = {"CS Cadmus | 10 - Solucoes por Mes": "solucionados",
                      "CS Cadmus | 11 - Backlog Atual por Categoria": "backlog",
                      "CS Cadmus | 12 - Fora do Prazo por Categoria": "atrasados",
                      "CS Cadmus | 14 - Pesquisas Respondidas por Organizacao": "respostas",
                      "CS Cadmus | 15 - Atendimentos por Tecnico": "atendimentos"}
        style = series_style(color_keys[d["name"]], d["color"]) if d["name"] in color_keys else {}
        payload = {"name": d["name"], "description": d["explanation"],
                   "display": d["display"], "collection_id": COLLECTION,
                   "database_id": DATABASE, "dataset_query": query,
                   "parameters": params, "visualization_settings": style}
        print(("%s: " % ("CRIAR" if args.apply else "SIMULAR")) + d["name"] + " [" + d["mode"] + "]")
        if args.apply:
            created = api("POST", "/card", payload)
            print("  ID:", created.get("id"))
    if not args.apply:
        print("Nenhuma gravacao. Aplique com --apply.")
    else:
        print("Concluido. Teste as novas perguntas com filtros antes de montar dashboard.")
        print("IMPORTANTE: Backlog atual ignora periodo; historico exato requer eventos de reabertura.")

if __name__ == "__main__":
    main()
