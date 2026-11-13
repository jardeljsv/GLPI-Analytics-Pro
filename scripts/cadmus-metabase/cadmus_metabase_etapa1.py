#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cadmus GLPI / Metabase v0.65.3 - perguntas da Central de Servicos.

Requisitos: Python 3 (stdlib), MB_API_KEY no ambiente.
Simulacao: python3 cadmus_metabase_etapa1.py
Criacao:   python3 cadmus_metabase_etapa1.py --apply

Usa API REST; nao escreve nas tabelas de glpidb nem metabase.
Preserva as perguntas 40 (Chamados abertos) e 41 (Tecnicos).
"""
import argparse
import copy
import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("MB_URL", "http://127.0.0.1:3000").rstrip("/")
API_KEY = os.environ.get("MB_API_KEY", "")
REF_CARD_ID = 40
COLLECTION_ID = 6
DATABASE_ID = 2

def api(method, path, payload=None):
    headers = {"X-API-Key": API_KEY, "Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(BASE_URL + "/api" + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=50) as res:
            body = res.read()
            return json.loads(body.decode()) if body else {}
    except urllib.error.HTTPError as exc:
        sys.exit("HTTP %s em %s: %s" % (exc.code, path, exc.read().decode(errors="replace")[:1300]))
    except urllib.error.URLError as exc:
        sys.exit("Conexao indisponivel: %s" % exc)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Cria as perguntas via API")
    args = parser.parse_args()
    if not API_KEY:
        sys.exit("Defina MB_API_KEY na mesma sessao do terminal; nao salve a chave no script.")

    ref = api("GET", "/card/%s" % REF_CARD_ID)
    if ref.get("database_id") != DATABASE_ID or ref.get("collection_id") != COLLECTION_ID:
        sys.exit("Pergunta 40 nao corresponde a banco 2 / colecao 6.")
    query = ref["dataset_query"]
    stage = query["stages"][0]
    tags = stage.get("template-tags", [])
    original_sql = stage["native"]
    expected = {"periodo", "organizacao", "categoria", "tecnico"}
    if not expected.issubset({tag["name"] for tag in tags}):
        sys.exit("A pergunta 40 nao possui os quatro filtros esperados.")
    if "FROM glpi_tickets t" not in original_sql:
        sys.exit("Estrutura SQL da pergunta 40 mudou. Inspecione antes de executar.")

    # Utiliza exatamente os mesmos relacionamentos/filtros da pergunta 40.
    base_sql = original_sql[original_sql.index("FROM glpi_tickets t"):]
    # Remove possivel ';' final, para permitir acrescentar agrupamentos.
    base_sql = base_sql.rstrip().rstrip(";")
    # Garante que a consulta de referencia nao termine com clausulas agregadoras.
    if any("\nGROUP BY" in base_sql.upper() for _ in [0]):
        sys.exit("Consulta 40 passou a conter GROUP BY; revise o script.")

    definitions = [
      ("CS Cadmus | 02 - Chamados Solucionados", "scalar",
       "SELECT COUNT(DISTINCT t.id) AS chamados_solucionados\n", "AND t.solvedate IS NOT NULL", ""),
      ("CS Cadmus | 03 - Volumetria por Organização", "bar",
       """SELECT CASE WHEN t.entities_id IN (138,160) THEN 'Cadmus'
                    ELSE 'PeoplePro' END AS organizacao,
       COUNT(DISTINCT t.id) AS chamados_abertos
""", "", "GROUP BY organizacao ORDER BY chamados_abertos DESC"),
      ("CS Cadmus | 04 - Top 10 Categorias", "row",
       """SELECT COALESCE(NULLIF(c.completename,''),'Sem categoria') AS categoria,
       COUNT(DISTINCT t.id) AS total_chamados
""", "", "GROUP BY c.id, c.completename ORDER BY total_chamados DESC LIMIT 10"),
      ("CS Cadmus | 05 - Chamados Fora do Prazo TTR", "scalar",
       "SELECT COUNT(DISTINCT t.id) AS fora_do_prazo_ttr\n",
       "AND t.solvedate IS NOT NULL AND t.time_to_resolve IS NOT NULL AND t.solvedate > t.time_to_resolve", ""),
      ("CS Cadmus | 06 - Aberturas por Mês", "bar",
       "SELECT DATE_FORMAT(t.date, '%Y-%m-01') AS mes, COUNT(DISTINCT t.id) AS abertos\n",
       "", "GROUP BY DATE_FORMAT(t.date, '%Y-%m-01') ORDER BY mes"),
      ("CS Cadmus | 07 - Cumprimento SLA TTR", "scalar",
       """SELECT ROUND(100 * COUNT(DISTINCT CASE WHEN t.solvedate IS NOT NULL
          AND t.time_to_resolve IS NOT NULL AND t.solvedate <= t.time_to_resolve
          THEN t.id END) / NULLIF(COUNT(DISTINCT CASE WHEN t.solvedate IS NOT NULL
          AND t.time_to_resolve IS NOT NULL THEN t.id END),0),2) AS percentual_dentro_prazo
""", "", ""),
    ]

    # Observacao: todas as perguntas desta etapa usam periodo pela DATA DE ABERTURA
    # (copiando o filtro da consulta 40). Para series de SOLUCOES por solvedate,
    # faremos ajuste explicito do Field Filter depois de validar esta etapa.
    existing = api("GET", "/collection/%d/items?models=card&limit=500" % COLLECTION_ID)
    items = existing.get("data", existing if isinstance(existing, list) else [])
    names = {item.get("name"): item.get("id") for item in items if isinstance(item, dict)}
    print("Origem: pergunta 40 | Banco 2 | Colecao 6")
    print("ATENCAO: periodo nesta etapa referencia a data de ABERTURA do chamado.")
    print("Indicadores de solucao/SLAs sao coortes de chamados ABERTOS no periodo.")
    for name, display, select, where, grouping in definitions:
        if name in names:
            print("JA EXISTE: %s (ID %s)" % (name, names[name]))
            continue
        sql = select + base_sql
        if where:
            sql += "\n" + where
        if grouping:
            sql += "\n" + grouping
        payload = {
            "name": name,
            "display": display,
            "collection_id": COLLECTION_ID,
            "database_id": DATABASE_ID,
            "dataset_query": {
                "lib/type": "mbql/query",
                "database": DATABASE_ID,
                "stages": [{
                    "lib/type": "mbql.stage/native",
                    "native": sql,
                    "template-tags": copy.deepcopy(tags)
                }]
            },
            "visualization_settings": {}
        }
        if args.apply:
            created = api("POST", "/card", payload)
            print("CRIADA: %s (ID %s)" % (name, created.get("id")))
        else:
            print("SIMULACAO: criaria %s [%s]" % (name, display))
    if not args.apply:
        print("Nenhuma alteracao realizada. Para criar: python3 cadmus_metabase_etapa1.py --apply")

if __name__ == "__main__":
    main()
