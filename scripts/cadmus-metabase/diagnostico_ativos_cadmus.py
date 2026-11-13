#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostico somente leitura para o dashboard Gestao de Ativos | Cadmus.

Execute no servidor do GLPI; nao modifica banco nem Metabase.
Usa autenticacao MariaDB local, mesma forma usada em manutencoes anteriores.
Exemplo: python3 diagnostico_ativos_cadmus.py
         GLPI_DB=glpidb MYSQL_USER=root python3 diagnostico_ativos_cadmus.py
"""
import datetime
import json
import os
import subprocess
import sys

DB = os.environ.get("GLPI_DB", "glpidb")
USER = os.environ.get("MYSQL_USER", "root")
HOST = os.environ.get("MYSQL_HOST")
PORT = os.environ.get("MYSQL_PORT")
OUT = "diagnostico_ativos_cadmus_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"

def query(sql):
    cmd = ["mariadb", "--batch", "--raw", "--skip-column-names",
           "--default-character-set=utf8mb4", "-u", USER]
    if HOST:
        cmd.extend(["-h", HOST])
    if PORT:
        cmd.extend(["-P", PORT])
    cmd.extend([DB, "-e", sql])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=75)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip()[:1200])
    return [line.split("\t") for line in proc.stdout.splitlines() if line.strip()]

def quote_name(name):
    if not name.replace("_", "").isalnum():
        raise ValueError("Identificador invalido")
    return "`" + name + "`"

def main():
    tables_rows = query(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=DATABASE() AND "
        "(TABLE_NAME LIKE 'glpi_%') ORDER BY TABLE_NAME"
    )
    tables = [r[0] for r in tables_rows]
    priority = [
        "glpi_computers", "glpi_monitors", "glpi_printers", "glpi_peripherals",
        "glpi_phones", "glpi_networkequipments", "glpi_devicesimcards",
        "glpi_racks", "glpi_enclosures", "glpi_states", "glpi_locations",
        "glpi_entities", "glpi_users", "glpi_computertypes",
        "glpi_manufacturers", "glpi_computermodels",
        "glpi_items_deviceharddrives", "glpi_items_deviceprocessors",
        "glpi_infocoms", "glpi_contracts", "glpi_contracts_items",
        "glpi_tickets", "glpi_itilcategories", "glpi_tickets_users",
        "glpi_plugin_formcreator_forms", "glpi_plugin_formcreator_issues"
    ]
    relevant_plugins = [x for x in tables
                        if x.startswith("glpi_plugin_")
                        and any(word in x for word in
                                ["asset", "inventory", "stock", "transfer",
                                 "delivery", "onboard", "offboard", "form"])]
    selected = sorted(set(priority).intersection(tables) | set(relevant_plugins))
    columns = query(
        "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME, ORDINAL_POSITION"
    )
    column_map = {}
    for table, name, ctype in columns:
        if table in selected:
            column_map.setdefault(table, []).append({"name": name, "type": ctype})
    counts = {}
    for table in selected:
        if table.startswith("glpi_plugin_"):
            continue
        if table in ("glpi_users", "glpi_tickets", "glpi_tickets_users"):
            continue
        try:
            counts[table] = int(query("SELECT COUNT(*) FROM " + quote_name(table))[0][0])
        except (RuntimeError, ValueError, IndexError):
            counts[table] = None
    names = [c["name"] for c in column_map.get("glpi_computers", [])]
    entity_summary = []
    if "entities_id" in names:
        cols = ["entities_id", "COUNT(*) AS total"]
        if "is_deleted" in names:
            where = " WHERE is_deleted=0"
        else:
            where = ""
        entity_summary = query(
            "SELECT entities_id,COUNT(*) FROM glpi_computers" + where +
            " GROUP BY entities_id ORDER BY COUNT(*) DESC LIMIT 30"
        )
    categories = []
    if "glpi_itilcategories" in tables:
        categories = query(
            "SELECT id, LEFT(completename,160) FROM glpi_itilcategories "
            "WHERE LOWER(completename) REGEXP "
            "'onboard|offboard|admiss|deslig|devolu|equipamento|movimenta|troca|estoque' "
            "ORDER BY completename LIMIT 100"
        )
    record = {
        "database": DB,
        "generated": datetime.datetime.now().isoformat(),
        "selected_tables": selected,
        "columns": column_map,
        "table_counts": counts,
        "computers_by_entity": entity_summary,
        "lifecycle_candidate_categories": categories
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print("DIAGNOSTICO GESTAO DE ATIVOS - CADMUS")
    print("Tabelas encontradas:", len(selected))
    print("Tabelas de ativos e contratos:")
    for name in selected:
        if not name.startswith("glpi_plugin_"):
            print("  %-34s %s" % (name, counts.get(name, "(sem contagem)")))
    print("\nCAMPOS PARA VALIDAR REGRAS DE NEGOCIO")
    focused = ("glpi_computers", "glpi_infocoms", "glpi_contracts",
               "glpi_contracts_items", "glpi_states", "glpi_locations",
               "glpi_entities", "glpi_computertypes", "glpi_computermodels")
    for table in focused:
        if table in column_map:
            print("\n" + table + ":")
            print(", ".join(x["name"] for x in column_map[table]))
    print("\nCOMPUTADORES POR ENTIDADE (ID, TOTAL)")
    for row in entity_summary:
        print("  " + " | ".join(row))
    print("\nCATEGORIAS CANDIDATAS PARA ONBOARDING/OFFBOARDING")
    for row in categories:
        print("  " + " | ".join(row))
    print("\nARQUIVO JSON LOCAL:", os.path.abspath(OUT))
    print("Nao envie credenciais. Este arquivo contem metadados de tabelas e contagens.")

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as e:
        sys.exit("ERRO: " + str(e))
