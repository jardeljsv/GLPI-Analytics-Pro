#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Melhorias Gestão de Ativos Cadmus — Metabase 0.65.3.

Adiciona 4 perguntas:
16 | Estoque disponível por modelo (computadores)
17 | Qualidade cadastral - pendências por campo
18 | Disponíveis com usuário vinculado (possível divergência)
19 | Inventário detalhado de ativos

Acrescenta seção e 4 cards ao FINAL do dashboard existente,
sem apagar/reorganizar cabeçalho, filtros, seções ou cards anteriores.

Escopo: entidades GLPI 83, 137, 162, equipamentos ativos/não-modelo.
Não atribui equipamentos a Cadmus/PeoplePro sem prova.
Valida colunas reais antes da criação. Cria backup JSON local antes
de atualizar o dashboard. Preserva banco GLPI (somente consultas SELECT).

Uso:
    python3 melhorias_ativos_cadmus.py
    python3 melhorias_ativos_cadmus.py --apply
Opcional: MB_URL=http://127.0.0.1:3000
Requer MB_API_KEY exportada no ambiente.
"""
import argparse
import copy
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("MB_URL", "http://127.0.0.1:3000").rstrip("/")
KEY = os.environ.get("MB_API_KEY", "")
DB = 2
COLLECTION = "Gestão de Ativos | Cadmus"
DASHBOARD = "Gestão de Ativos | Cadmus"
SCOPED_ENTITIES = "83,137,162"
BLUE = "#0D2A43"
ORANGE = "#FF873F"
GRAY = "#80868B"
TABLES = [
    ("Computador", "glpi_computers", "computermodels_id", "glpi_computermodels"),
    ("Monitor", "glpi_monitors", "monitormodels_id", "glpi_monitormodels"),
    ("Periférico", "glpi_peripherals", "peripheralmodels_id", "glpi_peripheralmodels"),
    ("Telefone", "glpi_phones", "phonemodels_id", "glpi_phonemodels"),
    ("Impressora", "glpi_printers", "printermodels_id", "glpi_printermodels"),
]
SECTION_TITLE = "### Qualidade cadastral e inventário detalhado"
SECTION_TEXT = (
    SECTION_TITLE + "\n"
    "Estoque disponível por modelo, pendências de preenchimento, "
    "possíveis inconsistências entre disponibilidade e vínculo com usuário "
    "e relação detalhada de equipamentos.\n\n"
    "*Disponível significa estado GLPI 5. Ativo sem usuário não é "
    "automaticamente estoque disponível. Patrimônio corresponde ao campo "
    "Número de inventário (otherserial).*"
)

def api(method, path, data=None):
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    raw = None
    if data is not None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + "/api" + path, headers=headers, data=raw, method=method)
    try:
        with urllib.request.urlopen(req, timeout=100) as r:
            body = r.read()
            return json.loads(body.decode("utf-8")) if body else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s em %s: %s" %
                           (e.code, path, e.read().decode("utf-8", errors="replace")[:2000]))
    except urllib.error.URLError as e:
        raise RuntimeError("Não foi possível conectar ao Metabase: %s" % e)

def find_collection():
    result = api("GET", "/collection")
    collection_list = result if isinstance(result, list) else result.get("data", [])
    matches = [x for x in collection_list if x.get("name") == COLLECTION and not x.get("archived")]
    if len(matches) != 1:
        raise RuntimeError("Esperada 1 coleção '%s'; encontradas %d." % (COLLECTION, len(matches)))
    return matches[0]["id"]

def find_dashboard(collection_id):
    result = api("GET", "/collection/%s/items?models=dashboard&limit=100" % collection_id)
    matches = [x for x in result.get("data", []) if x.get("name") == DASHBOARD]
    if len(matches) != 1:
        raise RuntimeError("Esperado 1 dashboard '%s'; encontrados %d." % (DASHBOARD, len(matches)))
    return matches[0]["id"]

def items(dashboard):
    return dashboard.get("dashcards") or dashboard.get("ordered_cards") or []

def load_columns():
    meta = api("GET", "/database/%s/metadata" % DB)
    table_columns = {}
    for t in meta.get("tables", []):
        name = t.get("name")
        if name:
            table_columns[name] = {field["name"] for field in t.get("fields", [])
                                   if field.get("name")}
    if not all(t[1] in table_columns for t in TABLES):
        raise RuntimeError("Metadados do DB %s incompletos: tabelas de ativo não encontradas. "
                           "Confira permissões e sincronização do banco." % DB)
    return table_columns

def expr(columns, table, field, alias, fallback="NULL"):
    return alias + "." + field if field in columns.get(table, set()) else fallback

def source_sql(columns):
    union = []
    for asset_type, table, model_col, model_table in TABLES:
        fields = columns[table]
        required = {"id", "entities_id", "is_deleted", "is_template",
                    "states_id", "users_id", "locations_id", "name"}
        missing = required - fields
        if missing:
            raise RuntimeError("Faltam colunas na tabela %s: %s" %
                               (table, sorted(missing)))
        def opt(field, fallback="NULL"):
            return expr(columns, table, field, "a", fallback)
        # CUIDADO: não duplica ativos por junções de Infocoms.
        item = (
            "SELECT '%s' AS tipo, a.id, a.entities_id, "
            "%s AS nome, %s AS numero_serie, %s AS patrimonio, "
            "a.states_id, a.users_id, a.locations_id, "
            "%s AS modelo_id, "
            "%s AS data_cadastro, %s AS atualizado_em, "
            "%s AS inventario_em "
            "FROM %s a "
            "WHERE a.is_deleted=0 AND a.is_template=0 AND a.entities_id IN (%s)"
        ) % (asset_type,
             opt("name", "''"), opt("serial", "''"), opt("otherserial", "''"),
             opt(model_col, "NULL"), opt("date_creation"),
             opt("date_mod"), opt("last_inventory_update"),
             table, SCOPED_ENTITIES)
        union.append(item)
    return "(\n" + "\nUNION ALL\n".join(union) + "\n) a"

def model_name_sql(columns):
    # Os nomes dos modelos são consultados por JOIN com a tabela adequada.
    # Se uma tabela de modelos não estiver disponível na metadata, usa 'Sem modelo'.
    subqueries = []
    for asset_type, table, model_col, model_table in TABLES:
        if model_table in columns and {"id", "name"} <= columns[model_table]:
            subqueries.append(
                "WHEN a.tipo='%s' THEN "
                "(SELECT m.name FROM %s m WHERE m.id=a.modelo_id)" %
                (asset_type, model_table))
    return "CASE " + " ".join(subqueries) + " ELSE NULL END"

def definitions(columns):
    src = source_sql(columns)
    models = model_name_sql(columns)
    return [
        {
            "name": "16 | Estoque disponível por modelo (computadores)",
            "display": "row", "color": BLUE,
            "sql": (
                "SELECT COALESCE(NULLIF(TRIM(m.name),''),'Sem modelo') AS modelo,"
                "COUNT(*) AS quantidade\n"
                "FROM glpi_computers c "
                "LEFT JOIN glpi_computermodels m ON m.id=c.computermodels_id\n"
                "WHERE c.is_deleted=0 AND c.is_template=0 AND c.states_id=5 "
                "AND c.entities_id IN (%s)\n"
                "GROUP BY c.computermodels_id,m.name "
                "ORDER BY quantidade DESC,modelo LIMIT 30"
            ) % SCOPED_ENTITIES
        },
        {
            "name": "17 | Qualidade cadastral - pendências por campo",
            "display": "bar", "color": ORANGE,
            "sql": (
                "SELECT 'Sem patrimônio' AS pendencia,"
                " SUM(CASE WHEN NULLIF(TRIM(COALESCE(a.patrimonio,'')),'') IS NULL THEN 1 ELSE 0 END) AS quantidade "
                "FROM %s\n"
                "UNION ALL SELECT 'Sem número de série',"
                " SUM(CASE WHEN NULLIF(TRIM(COALESCE(a.numero_serie,'')),'') IS NULL THEN 1 ELSE 0 END) FROM %s\n"
                "UNION ALL SELECT 'Sem modelo',"
                " SUM(CASE WHEN COALESCE(a.modelo_id,0)=0 THEN 1 ELSE 0 END) FROM %s\n"
                "UNION ALL SELECT 'Sem localização',"
                " SUM(CASE WHEN COALESCE(a.locations_id,0)=0 THEN 1 ELSE 0 END) FROM %s\n"
                "UNION ALL SELECT 'Sem estado',"
                " SUM(CASE WHEN COALESCE(a.states_id,0)=0 THEN 1 ELSE 0 END) FROM %s"
            ) % ((src,) * 5),
            "description": "As categorias de pendência não são mutuamente exclusivas; "
                           "o mesmo equipamento pode ter mais de um campo incompleto."
        },
        {
            "name": "18 | Disponíveis com usuário vinculado",
            "display": "scalar", "color": None,
            "sql": ("SELECT COUNT(*) AS inconsistencias_potenciais FROM %s "
                    "WHERE a.states_id=5 AND COALESCE(a.users_id,0)<>0" % src),
            "description": "Alerta de possível divergência; confirmar regras de negócio "
                           "antes de interpretar como erro cadastral."
        },
        {
            "name": "19 | Inventário detalhado de ativos",
            "display": "table", "color": None,
            "sql": (
                "SELECT a.tipo AS tipo, a.id AS id_glpi, a.nome AS equipamento, "
                "a.patrimonio AS patrimonio, a.numero_serie AS numero_serie, "
                "COALESCE(NULLIF(TRIM(%s),''),'Sem modelo') AS modelo, "
                "COALESCE(NULLIF(s.completename,''),NULLIF(s.name,''),'Sem estado') AS estado, "
                "COALESCE(NULLIF(l.completename,''),NULLIF(l.name,''),'Sem localização') AS localizacao, "
                "CASE WHEN COALESCE(a.users_id,0)=0 THEN 'Sem usuário' "
                "ELSE TRIM(CONCAT_WS(' ',NULLIF(TRIM(u.firstname),''),"
                "NULLIF(TRIM(u.realname),''))) END AS usuario, "
                "a.entities_id AS entidade_id, a.data_cadastro, a.atualizado_em, "
                "a.inventario_em\n"
                "FROM %s\n"
                "LEFT JOIN glpi_states s ON s.id=a.states_id "
                "LEFT JOIN glpi_locations l ON l.id=a.locations_id "
                "LEFT JOIN glpi_users u ON u.id=a.users_id "
                "ORDER BY a.tipo,a.id LIMIT 5000"
            ) % (models, src),
            "description": "Inventário detalhado das entidades 83,137,162, "
                           "incluindo patrimônio (otherserial), número de série, modelo e responsável."
        }
    ]

def native_query(sample, sql):
    # Usa o mesmo formato de dataset_query da pergunta original para
    # manter compatibilidade com a versão instalada do Metabase.
    dataset = copy.deepcopy(sample["dataset_query"])
    if "stages" in dataset:
        if not dataset["stages"] or "native" not in dataset["stages"][0]:
            raise RuntimeError("Pergunta de referência não é SQL nativa.")
        stage = dataset["stages"][0]
        stage["native"] = sql
        stage["template-tags"] = []
    elif dataset.get("type") == "native":
        dataset["native"] = {"query": sql, "template-tags": {}}
    else:
        raise RuntimeError("Formato de consulta Metabase inesperado.")
    dataset["database"] = DB
    return dataset

def backup_dashboard(dashboard):
    filename = ("backup_ativos_dashboard_%s_melhorias_%s.json" %
                (dashboard["id"], datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)
    print("Backup:", os.path.abspath(filename))

def safe_dashcard(c):
    keys = ("id", "card_id", "row", "col", "size_x", "size_y",
            "parameter_mappings", "visualization_settings",
            "dashboard_tab_id", "action_id", "inline_parameters")
    return {k: copy.deepcopy(c[k]) for k in keys if k in c}

def new_text(identifier, row):
    return {
        "id": identifier, "card_id": None, "row": row, "col": 0,
        "size_x": 24, "size_y": 3,
        "parameter_mappings": [],
        "visualization_settings": {
            "virtual_card": {
                "name": None, "display": "text",
                "visualization_settings": {}, "archived": False
            },
            "text": SECTION_TEXT
        }
    }

def build_dashcards(dashboard, card_ids):
    current = items(dashboard)
    card_id_set = {item.get("card_id") for item in current if item.get("card_id")}
    heading_found = any(
        SECTION_TITLE in (item.get("visualization_settings") or {}).get("text", "")
        for item in current if item.get("card_id") is None
    )
    updated = [safe_dashcard(c) for c in current]
    max_row = max((int(x.get("row", 0)) + int(x.get("size_y", 1)) for x in current), default=0)
    next_row = max_row + 1
    fake_id = -1
    def fresh():
        nonlocal fake_id
        while any(x.get("id") == fake_id for x in updated):
            fake_id -= 1
        val = fake_id
        fake_id -= 1
        return val
    if not heading_found:
        updated.append(new_text(fresh(), next_row))
        next_row += 3
    # Se os cards já estão no dashboard, não reposicionamos nada.
    positions = [
        (0, 12, 8),    # estoque por modelo
        (12, 12, 8),   # pendencias
        (0, 8, 4),     # possivel inconsistencia
        (0, 24, 11)    # tabela
    ]
    added = []
    for index, cid in enumerate(card_ids):
        if cid in card_id_set:
            continue
        col, width, height = positions[index]
        # Terceiro cartao usa linha separada; tabela aparece por ultimo
        if index == 0:
            row = next_row
        elif index == 1:
            row = next_row
        elif index == 2:
            row = next_row + 8
        else:
            row = next_row + 12
        updated.append({
            "id": fresh(), "card_id": cid, "row": row, "col": col,
            "size_x": width, "size_y": height,
            "parameter_mappings": [], "visualization_settings": {}
        })
        added.append(cid)
    return updated, added

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not KEY:
        raise RuntimeError("MB_API_KEY não está disponível na sessão.")

    collection_id = find_collection()
    dash_id = find_dashboard(collection_id)
    dashboard = api("GET", "/dashboard/%s" % dash_id)
    if dashboard.get("name") != DASHBOARD:
        raise RuntimeError("Nome de dashboard inesperado.")

    contents = api("GET", "/collection/%s/items?models=card&limit=200" % collection_id)
    existing = {x["name"]: x["id"] for x in contents.get("data", [])}
    sample_card_id = next((cid for name, cid in existing.items()
                           if name.startswith("01 | Total de ativos")), None)
    if not sample_card_id:
        raise RuntimeError("Não encontrei a pergunta '01 | Total de ativos' na coleção.")
    sample_card = api("GET", "/card/%s" % sample_card_id)
    if sample_card.get("database_id") != DB:
        raise RuntimeError("Banco da pergunta de referência não é o 2.")

    columns = load_columns()
    queries = definitions(columns)
    print("Gestão de Ativos | Cadmus. Dashboard ID %s, coleção %s" %
          (dash_id, collection_id))
    print("Escopo GLPI: entidades %s. Não altera perguntas anteriores." % SCOPED_ENTITIES)

    final_ids = []
    for entry in queries:
        name = entry["name"]
        if name in existing:
            final_ids.append(existing[name])
            print("EXISTE:", existing[name], name)
            continue
        print("%s: %s" % ("CRIAR" if args.apply else "SIMULAR", name))
        if not args.apply:
            final_ids.append(None)
            continue
        viz = {}
        if entry["display"] in ("bar", "row"):
            viz = {"graph.show_values": True, "graph.colors": [entry["color"]]}
        payload = {
            "name": name,
            "description": entry.get("description", "Inventário GLPI das entidades 83, 137 e 162."),
            "collection_id": collection_id,
            "database_id": DB,
            "display": entry["display"],
            "dataset_query": native_query(sample_card, entry["sql"]),
            "visualization_settings": viz,
            "parameters": []
        }
        created = api("POST", "/card", payload)
        final_ids.append(created["id"])
        print("  CRIADA: pergunta", created["id"])

    if not args.apply:
        print("SIMULAÇÃO concluída. Nenhuma alteração. Execute com --apply.")
        return

    latest = api("GET", "/dashboard/%s" % dash_id)
    if len(latest.get("parameters") or []) != len(dashboard.get("parameters") or []):
        raise RuntimeError("Filtros mudaram durante a execução. Aborte.")
    dashcards, added = build_dashcards(latest, final_ids)
    if not added and len(dashcards) == len(items(latest)):
        print("OK: todas as perguntas já estão no dashboard.")
        return
    backup_dashboard(latest)
    api("PUT", "/dashboard/%s" % dash_id, {
        "name": latest["name"],
        "width": "full",
        "parameters": latest.get("parameters") or [],
        "dashcards": dashcards
    })
    confirmed = api("GET", "/dashboard/%s" % dash_id)
    present = {x.get("card_id") for x in items(confirmed)}
    absent = set(final_ids) - present
    if absent:
        raise RuntimeError("Cards ausentes após salvar: %s" % sorted(absent))
    print("SUCESSO: %d perguntas anexadas nesta execução." % len(added))
    print("Total de blocos no dashboard:", len(items(confirmed)))
    print("Painel:", BASE + "/dashboard/" + str(dash_id))
    print("Atualize a página com Ctrl+F5.")
    print("ATENÇÃO: valide a consistência do estoque e de modelos junto à operação.")

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        sys.exit("ERRO: %s" % exc)
