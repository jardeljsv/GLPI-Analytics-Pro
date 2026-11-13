#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Filtros globais para Gestão de Ativos | Cadmus - Metabase 0.65.3.

Filtros: Tipo, Estado, Modelo, Localização e Entidade (listas dinâmicas).
Aplica a todas as perguntas numeradas 01-19 sem restringir entidades.
As consultas consultam ativos não excluídos/não-modelos das 5 tabelas GLPI.
Mantém cabeçalho, posições, títulos, layout e cores dos gráficos.

IMPORTANTE: padroniza o SQL das 19 perguntas para usar filtros consistentes.
O campo de modelo é tratado conforme a tabela de cada tipo de ativo.
O estado/entidade/localização são extraídos dos cadastros GLPI.

Simular: python3 filtros_ativos_etapa1.py
Aplicar: python3 filtros_ativos_etapa1.py --apply

Precisa MB_API_KEY no ambiente. MB_URL opcional.
Cria backup JSON no diretório atual antes da alteração.
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
import uuid

BASE = os.environ.get("MB_URL", "http://127.0.0.1:3000").rstrip("/")
KEY = os.environ.get("MB_API_KEY", "")
DB = 2
COL_NAME = "Gestão de Ativos | Cadmus"
DASH_NAME = "Gestão de Ativos | Cadmus"
FILTERS = [
    ("tipo", "Tipo de ativo"),
    ("estado", "Estado"),
    ("modelo", "Modelo"),
    ("localizacao", "Localização"),
    ("entidade", "Entidade"),
]
ASSETS = [
    ("Computador", "glpi_computers", "computermodels_id", "glpi_computermodels"),
    ("Monitor", "glpi_monitors", "monitormodels_id", "glpi_monitormodels"),
    ("Periférico", "glpi_peripherals", "peripheralmodels_id", "glpi_peripheralmodels"),
    ("Telefone", "glpi_phones", "phonemodels_id", "glpi_phonemodels"),
    ("Impressora", "glpi_printers", "printermodels_id", "glpi_printermodels"),
]

def api(method, path, obj=None):
    headers = {"X-API-Key": KEY, "Accept": "application/json"}
    data = None
    if obj is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE + "/api" + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as err:
        raise RuntimeError("HTTP %s %s: %s" % (
            err.code, path, err.read().decode("utf-8", errors="replace")[:2200]))
    except urllib.error.URLError as err:
        raise RuntimeError("Conexão Metabase: %s" % err)

def list_collection(collection_id, model):
    out, offset, limit = [], 0, 100
    while True:
        res = api("GET", "/collection/%d/items?models=%s&limit=%d&offset=%d" %
                  (collection_id, model, limit, offset))
        rows = res.get("data", [])
        out.extend(rows)
        if not rows or len(rows) < limit or (
                res.get("total") is not None and offset + len(rows) >= res["total"]):
            return out
        offset += len(rows)

def find_resources():
    res = api("GET", "/collection")
    collections = res if isinstance(res, list) else res.get("data", [])
    found = [r for r in collections if r.get("name") == COL_NAME and not r.get("archived")]
    if len(found) != 1:
        raise RuntimeError("Coleção '%s' não identificada de forma única" % COL_NAME)
    cid = found[0]["id"]
    matches = [d for d in list_collection(cid, "dashboard") if d.get("name") == DASH_NAME]
    if len(matches) != 1:
        raise RuntimeError("Dashboard '%s' não identificado de forma única" % DASH_NAME)
    return cid, matches[0]["id"]

def metadata():
    result = api("GET", "/database/%d/metadata" % DB)
    cols = {t["name"]: {f["name"] for f in t.get("fields", []) if f.get("name")}
            for t in result.get("tables", []) if t.get("name")}
    needed = [t for _, t, _, _ in ASSETS] + [
        "glpi_states", "glpi_locations", "glpi_entities", "glpi_infocoms",
        "glpi_computermodels",
    ]
    absent = [t for t in needed if t not in cols]
    if absent:
        raise RuntimeError("Tabelas ausentes nos metadados DB 2: %s" % absent)
    for _, table, _, _ in ASSETS:
        missing = {"id", "name", "entities_id", "states_id", "locations_id",
                   "is_deleted", "is_template", "users_id"} - cols[table]
        if missing:
            raise RuntimeError("Colunas obrigatórias ausentes em %s: %s" % (table, missing))
    return cols

def norm_expr(alias, cols, field, fallback="NULL"):
    return alias + "." + field if field in cols else fallback

def asset_union(cols):
    chunks = []
    for name, table, model_field, model_table in ASSETS:
        fields = cols[table]
        model = norm_expr("x", fields, model_field, "NULL")
        if model_table in cols and {"id", "name"} <= cols[model_table] and model_field in fields:
            model_join = "LEFT JOIN %s md ON md.id=x.%s" % (model_table, model_field)
            model_value = "COALESCE(NULLIF(TRIM(md.name),''),'Sem modelo')"
        else:
            model_join = ""
            model_value = "'Sem modelo'"
        parts = [
            "'%s' AS tipo" % name,
            "x.id AS id",
            "x.entities_id AS entities_id",
            "x.states_id AS states_id",
            "x.locations_id AS locations_id",
            "x.users_id AS users_id",
            norm_expr("x", fields, "name", "''") + " AS nome",
            norm_expr("x", fields, "serial", "''") + " AS numero_serie",
            norm_expr("x", fields, "otherserial", "''") + " AS patrimonio",
            norm_expr("x", fields, "date_creation") + " AS data_cadastro",
            norm_expr("x", fields, "date_mod") + " AS atualizado_em",
            norm_expr("x", fields, "last_inventory_update") + " AS inventario_em",
            model_value + " AS modelo",
            "'" + {"Computador":"Computer","Monitor":"Monitor","Periférico":"Peripheral","Telefone":"Phone","Impressora":"Printer"}[name] + "' AS itemtype",
        ]
        chunks.append(
            "SELECT " + ", ".join(parts) +
            " FROM %s x %s WHERE x.is_deleted=0 AND x.is_template=0" %
            (table, model_join))
    return "\nUNION ALL\n".join(chunks)

def base_sql(cols, filtered=True):
    # Filtros textuais usam igualdade exata. As listas são alimentadas
    # por perguntas auxiliares, mantendo as grafias reais do GLPI.
    body = "(\n" + asset_union(cols) + "\n) src "
    joins = (
        "LEFT JOIN glpi_states st ON st.id=src.states_id\n"
        "LEFT JOIN glpi_locations lo ON lo.id=src.locations_id\n"
        "LEFT JOIN glpi_entities en ON en.id=src.entities_id\n"
    )
    cols_sql = (
        "src.*, "
        "COALESCE(NULLIF(st.completename,''),NULLIF(st.name,''),'Sem estado') AS estado, "
        "COALESCE(NULLIF(lo.completename,''),NULLIF(lo.name,''),'Sem localização') AS localizacao, "
        "COALESCE(NULLIF(en.completename,''),NULLIF(en.name,''),'Sem entidade') AS entidade "
    )
    filt = ""
    if filtered:
        filt = (
            "\n[[AND src.tipo = {{tipo}}]]"
            "\n[[AND COALESCE(NULLIF(st.completename,''),NULLIF(st.name,''),'Sem estado') = {{estado}}]]"
            "\n[[AND src.modelo = {{modelo}}]]"
            "\n[[AND COALESCE(NULLIF(lo.completename,''),NULLIF(lo.name,''),'Sem localização') = {{localizacao}}]]"
            "\n[[AND COALESCE(NULLIF(en.completename,''),NULLIF(en.name,''),'Sem entidade') = {{entidade}}]]"
        )
    return "(SELECT " + cols_sql + " FROM " + body + joins + " WHERE 1=1" + filt + "\n) a"

def definitions(cols):
    src = base_sql(cols)
    def agg(expr, where="", group="", order="", joins=""):
        return ("SELECT "+expr+"\nFROM "+src+"\n"+joins+
                ("\nWHERE "+where if where else "")+
                ("\n"+group if group else "")+
                ("\n"+order if order else ""))
    info = (
        "JOIN (SELECT items_id, itemtype, MAX(warranty_date) AS warranty_date "
        "FROM glpi_infocoms WHERE itemtype IN "
        "('Computer','Monitor','Peripheral','Phone','Printer') "
        "GROUP BY items_id,itemtype) i ON i.items_id=a.id AND i.itemtype=a.itemtype"
    )
    age_join = (
        "JOIN (SELECT items_id, MIN(buy_date) AS buy_date "
        "FROM glpi_infocoms WHERE itemtype='Computer' AND buy_date IS NOT NULL "
        "GROUP BY items_id) i ON i.items_id=a.id"
    )
    age_case = (
        "CASE WHEN TIMESTAMPDIFF(YEAR,i.buy_date,CURDATE()) < 2 THEN 'Menos de 2 anos' "
        "WHEN TIMESTAMPDIFF(YEAR,i.buy_date,CURDATE()) < 4 THEN '2 a 3 anos' "
        "WHEN TIMESTAMPDIFF(YEAR,i.buy_date,CURDATE()) < 6 THEN '4 a 5 anos' "
        "ELSE '6 anos ou mais' END"
    )
    # Mantém semântica dos 19 indicadores já existentes. Campos textuais
    # de filtros são avaliados antes das agregações.
    return {
        1: agg("COUNT(*) AS total_ativos"),
        2: agg("COUNT(*) AS disponiveis", "a.states_id=5"),
        3: agg("COUNT(*) AS sem_usuario", "COALESCE(a.users_id,0)=0"),
        4: agg("COUNT(*) AS sem_inventario",
               "a.tipo='Computador' AND a.inventario_em IS NULL"),
        5: agg("a.tipo AS tipo,COUNT(*) AS quantidade",
               group="GROUP BY a.tipo",order="ORDER BY quantidade DESC"),
        6: agg("a.estado AS estado,COUNT(*) AS quantidade",
               group="GROUP BY a.estado",order="ORDER BY quantidade DESC"),
        7: agg("a.tipo AS tipo,COUNT(*) AS quantidade","a.states_id=5",
               "GROUP BY a.tipo","ORDER BY quantidade DESC"),
        8: agg("a.tipo AS tipo,COUNT(*) AS quantidade","COALESCE(a.users_id,0)=0",
               "GROUP BY a.tipo","ORDER BY quantidade DESC"),
        9: agg("a.localizacao AS localizacao,COUNT(*) AS quantidade",
               group="GROUP BY a.localizacao",order="ORDER BY quantidade DESC LIMIT 20"),
        10: agg("a.modelo AS modelo,COUNT(*) AS quantidade", "a.tipo='Computador'",
                "GROUP BY a.modelo","ORDER BY quantidade DESC LIMIT 20"),
        11: agg("COUNT(*) AS garantias_a_vencer",
                "i.warranty_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(),INTERVAL 90 DAY)",
                joins=info),
        12: agg("COUNT(*) AS em_descarte", "a.states_id=4"),
        13: agg(age_case+" AS faixa_etaria,COUNT(*) AS computadores",
                "a.tipo='Computador' AND i.buy_date<=CURDATE()",
                "GROUP BY faixa_etaria",
                "ORDER BY MIN(TIMESTAMPDIFF(YEAR,i.buy_date,CURDATE()))",
                age_join),
        14: agg("a.tipo AS tipo,a.estado AS estado,COUNT(*) AS quantidade",
                group="GROUP BY a.tipo,a.estado",
                order="ORDER BY a.tipo,quantidade DESC"),
        15: agg("DATE_FORMAT(i.warranty_date,'%Y-%m') AS mes_vencimento,"
                "COUNT(*) AS quantidade",
                "i.warranty_date>=CURDATE() "
                "AND i.warranty_date<DATE_ADD(CURDATE(),INTERVAL 12 MONTH)",
                "GROUP BY DATE_FORMAT(i.warranty_date,'%Y-%m')",
                "ORDER BY mes_vencimento",info),
        16: agg("a.modelo AS modelo,COUNT(*) AS quantidade",
                "a.tipo='Computador' AND a.states_id=5",
                "GROUP BY a.modelo","ORDER BY quantidade DESC LIMIT 30"),
        17: (
            "SELECT 'Sem patrimônio' AS pendencia,"
            " SUM(CASE WHEN NULLIF(TRIM(COALESCE(a.patrimonio,'')),'') IS NULL THEN 1 ELSE 0 END) AS quantidade "
            "FROM "+src+"\n"
            "UNION ALL SELECT 'Sem número de série',"
            " SUM(CASE WHEN NULLIF(TRIM(COALESCE(a.numero_serie,'')),'') IS NULL THEN 1 ELSE 0 END) FROM "+src+"\n"
            "UNION ALL SELECT 'Sem modelo',"
            " SUM(CASE WHEN a.modelo='Sem modelo' THEN 1 ELSE 0 END) FROM "+src+"\n"
            "UNION ALL SELECT 'Sem localização',"
            " SUM(CASE WHEN COALESCE(a.locations_id,0)=0 THEN 1 ELSE 0 END) FROM "+src+"\n"
            "UNION ALL SELECT 'Sem estado',"
            " SUM(CASE WHEN COALESCE(a.states_id,0)=0 THEN 1 ELSE 0 END) FROM "+src
        ),
        18: agg("COUNT(*) AS inconsistencias_potenciais",
                "a.states_id=5 AND COALESCE(a.users_id,0)<>0"),
        19: agg(
            "a.tipo AS tipo,a.id AS id_glpi,a.nome AS equipamento,"
            "a.patrimonio,a.numero_serie,a.modelo,a.estado,a.localizacao,"
            "CASE WHEN COALESCE(a.users_id,0)=0 THEN 'Sem usuário' "
            "ELSE TRIM(CONCAT_WS(' ',NULLIF(TRIM(u.firstname),''),"
            "NULLIF(TRIM(u.realname),''))) END AS usuario,"
            "a.entities_id AS entidade_id,a.entidade,"
            "a.data_cadastro,a.atualizado_em,a.inventario_em",
            order="ORDER BY a.tipo,a.id LIMIT 5000",
            joins="LEFT JOIN glpi_users u ON u.id=a.users_id"),
    }

def card_num(name):
    match = re.match(r"^(0[1-9]|1[0-9])\s*\|", name or "")
    return int(match.group(1)) if match else None

def as_sql(card):
    q = card.get("dataset_query") or {}
    if q.get("stages") and isinstance(q["stages"][0].get("native"), str):
        return "stages"
    if isinstance((q.get("native") or {}).get("query"), str):
        return "legacy"
    raise RuntimeError("Formato de SQL não suportado no card %s" % card["id"])

def modify_card(card, sql, helper_ids):
    query = copy.deepcopy(card["dataset_query"])
    settings = copy.deepcopy(card.get("parameters") or [])
    # IDs estáveis por pergunta, se já existirem.
    current_by_name = {p.get("slug"):p for p in settings if p.get("slug")}
    param_tags = []
    top_params = []
    for key, label in FILTERS:
        prev = current_by_name.get(key, {})
        tag_id = prev.get("id") or str(uuid.uuid4())
        param_tags.append({
            "id": tag_id, "name": key, "display-name": label,
            "type": "text", "required": False
        })
        top_params.append({
            "id": tag_id, "slug": key, "name": label,
            "type": "string/=", "isMultiSelect": False,
            "values_query_type": "list",
            "values_source_type": "card",
            "values_source_config": {
                "card_id": helper_ids[key],
                "value_field": ["field", "valor", {"base-type": "type/Text"}],
                "label_field": ["field", "valor", {"base-type": "type/Text"}],
            },
            "target": ["variable", ["template-tag", key]],
        })
    fmt = as_sql(card)
    if fmt == "stages":
        query["stages"][0]["native"] = sql
        query["stages"][0]["template-tags"] = param_tags
    else:
        query["native"]["query"] = sql
        query["native"]["template-tags"] = {
            t["name"]: t for t in param_tags
        }
    return {"dataset_query": query, "parameters": top_params}

def safe_dashcard(card):
    keep=("id","card_id","row","col","size_x","size_y",
          "parameter_mappings","visualization_settings","dashboard_tab_id",
          "action_id","inline_parameters")
    return {key:copy.deepcopy(card[key]) for key in keep if key in card}

def make_dashboard(dashboard, cards_by_id):
    output = [safe_dashcard(c) for c in (dashboard.get("dashcards") or dashboard.get("ordered_cards") or [])]
    params = copy.deepcopy(dashboard.get("parameters") or [])
    existing = {p.get("slug") or p.get("name"):p for p in params}
    global_ids={}
    for key,label in FILTERS:
        p=existing.get(key) or existing.get(label)
        if p is None:
            p={
                "id": str(uuid.uuid4()), "name":label,"slug":key,
                "type":"string/=", "isMultiSelect":False,
                "values_query_type":"list",
                "values_source_type":"card",
                "values_source_config":cards_by_id["helpers"][key],
            }
            p["values_source_config"]={
                "card_id": cards_by_id["helpers"][key],
                "value_field": ["field","valor",{"base-type":"type/Text"}],
                "label_field": ["field","valor",{"base-type":"type/Text"}],
            }
            params.append(p)
        global_ids[key]=p["id"]
    mapped=0
    for dashcard in output:
        cid = dashcard.get("card_id")
        if cid not in cards_by_id["questions"]:
            continue
        mappings=[m for m in dashcard.get("parameter_mappings", [])
                  if m.get("parameter_id") not in global_ids.values()]
        for key,_ in FILTERS:
            mappings.append({
                "parameter_id":global_ids[key],
                "card_id":cid,
                "target":["variable",["template-tag",key]],
            })
        dashcard["parameter_mappings"]=mappings
        mapped+=1
    if mapped!=19:
        raise RuntimeError("Esperados 19 gráficos no dashboard; encontrados %d" % mapped)
    return {
        "name":dashboard["name"],
        "width":dashboard.get("width","full"),
        "parameters":params,
        "dashcards":output
    }

def create_helpers(cols, existing, cid, apply):
    base=base_sql(cols,filtered=False)
    ids={}
    for key,label in FILTERS:
        name="Filtro GA | "+label
        matches=[c for c in existing if c.get("name")==name]
        if len(matches)>1: raise RuntimeError("Perguntas auxiliares duplicadas: "+name)
        if matches:
            ids[key]=matches[0]["id"]
            print("LISTA EXISTENTE", ids[key], name)
            continue
        field = {"tipo":"tipo","estado":"estado","modelo":"modelo",
                 "localizacao":"localizacao","entidade":"entidade"}[key]
        query=("SELECT DISTINCT a.%s AS valor FROM %s "
               "WHERE a.%s IS NOT NULL AND a.%s<>'' "
               "ORDER BY valor LIMIT 10000") % (field,base,field,field)
        print("CRIAR LISTA:",name)
        if not apply:
            ids[key]=-1
            continue
        result=api("POST","/card",{
            "name":name,
            "description":"Fonte de valores do filtro global da Gestão de Ativos.",
            "collection_id":cid,"database_id":DB,
            "display":"table",
            "dataset_query":{
                "database":DB,"type":"native",
                "native":{"query":query,"template-tags":{}}
            },
            "visualization_settings":{}
        })
        ids[key]=result["id"]
        print("  CRIADA:",ids[key])
    return ids

def backup(questions, dashboard):
    filename="backup_filtros_ativos_etapa1_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".json"
    with open(filename,"w",encoding="utf-8") as f:
        json.dump({"dashboard":dashboard,"questions":questions},
                  f,ensure_ascii=False,indent=2)
    print("BACKUP:",os.path.abspath(filename))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    if not KEY: raise RuntimeError("MB_API_KEY não definida.")
    cid,did=find_resources()
    dash=api("GET","/dashboard/%d"%did)
    objects=list_collection(cid,"card")
    questions={}
    for entry in objects:
        num=card_num(entry.get("name"))
        if num is not None:
            if num in questions:
                raise RuntimeError("Número %s duplicado na coleção" % num)
            card=api("GET","/card/%s"%entry["id"])
            if card.get("database_id")!=DB or card.get("collection_id")!=cid:
                raise RuntimeError("Banco/coleção inesperados no card %s" % card["id"])
            questions[num]=card
    if set(questions)!=set(range(1,20)):
        raise RuntimeError("Esperadas perguntas 01-19. Encontradas: %s"%sorted(questions))
    cols=metadata()
    expected_sql=definitions(cols)
    print("Gestão de Ativos | Cadmus - filtros principais")
    print("Dashboard:",did,"Coleção:",cid)
    print("19 perguntas; 5 filtros; escopo todas as entidades GLPI.")
    print("Filtros: "+", ".join(label for _,label in FILTERS))
    helper_ids=create_helpers(cols,objects,cid,args.apply)
    for num in sorted(questions):
        print("%s pergunta %02d - ID %s"%(("ATUALIZAR" if args.apply else "SIMULAR"),num,questions[num]["id"]))
    if not args.apply:
        print("SIMULAÇÃO: nenhuma escrita efetuada. Para aplicar: --apply")
        return
    backup(list(questions.values()),dash)
    for num in sorted(questions):
        card=questions[num]
        payload=modify_card(card,expected_sql[num],helper_ids)
        api("PUT","/card/%d"%card["id"],payload)
        print("OK pergunta",num,card["id"])
    dash_latest=api("GET","/dashboard/%d"%did)
    patch=make_dashboard(dash_latest,{
        "helpers":helper_ids,
        "questions":{x["id"] for x in questions.values()},
    })
    api("PUT","/dashboard/%d"%did,patch)
    check=api("GET","/dashboard/%d"%did)
    print("DASHBOARD ATUALIZADO:",did)
    print("Filtros globais:",len(check.get("parameters") or []))
    print("Perguntas no dashboard:",len([x for x in
          (check.get("dashcards") or check.get("ordered_cards") or [])
          if x.get("card_id") in {q["id"] for q in questions.values()}]))
    print("Abra:",BASE+"/dashboard/"+str(did))
    print("TESTE: selecionar Estado=Disponivel, Tipo=Computador e conferir totais.")
    print("ATENÇÃO: a API valida os vínculos, mas não garante o retorno SQL de cada gráfico.")

if __name__=="__main__":
    try:main()
    except (RuntimeError,ValueError,KeyError,OSError) as exc:
        sys.exit("ERRO: "+str(exc))
