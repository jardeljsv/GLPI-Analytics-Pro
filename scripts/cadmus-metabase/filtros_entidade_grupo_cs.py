#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Central de Serviços | Cadmus — filtros globais Entidade e Grupo Técnico.

Compatível com estrutura de API observada no Metabase 0.65.3.
Escopo: coleção 6; dashboard 3; perguntas SQL 40 e 42–56.
Mantém filtros Período, Organização, Categoria e Técnico, além das cores,
textos, imagens e posições do dashboard. Não modifica registros GLPI.

Entidade: glpi_entities.completename, restrita às 4 entidades dos tickets.
Grupo Técnico: grupos atribuídos aos tickets (glpi_groups_tickets.type=2).
EXISTS evita multiplicação de tickets que possuem múltiplos grupos.

Simular: python3 filtros_entidade_grupo_cs.py
Aplicar: python3 filtros_entidade_grupo_cs.py --apply
Restaurar: python3 filtros_entidade_grupo_cs.py --restore BACKUP.json --apply
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
import uuid

BASE=os.getenv("MB_URL","http://127.0.0.1:3000").rstrip("/")
KEY=os.getenv("MB_API_KEY","")
COL=6
DASH=3
DB=2
CARD_IDS=[40]+list(range(42,57))
VALUES={
 "entidade":{
    "label":"Entidade",
    "helper":"Filtro CS | Entidade",
    "sql":"""SELECT DISTINCT e.completename AS valor
FROM glpi_entities e
WHERE e.id IN (138,140,160,161)
  AND e.completename IS NOT NULL AND e.completename <> ''
ORDER BY valor""",
    "filter":"""[[AND EXISTS (
    SELECT 1 FROM glpi_entities filtro_ent
    WHERE filtro_ent.id=t.entities_id
      AND filtro_ent.completename={{entidade}}
)]]"""
 },
 "grupo_tecnico":{
    "label":"Grupo Técnico",
    "helper":"Filtro CS | Grupo Técnico",
    "sql":"""SELECT DISTINCT CONCAT(g.name,' [',g.id,']') AS valor
FROM glpi_groups g
JOIN glpi_groups_tickets gt ON gt.groups_id=g.id AND gt.type=2
JOIN glpi_tickets t ON t.id=gt.tickets_id
WHERE t.is_deleted=0
  AND t.entities_id IN (138,140,160,161)
  AND g.name IS NOT NULL AND TRIM(g.name)<>''
ORDER BY valor""",
    "filter":"""[[AND EXISTS (
    SELECT 1 FROM glpi_groups_tickets filtro_gt
    JOIN glpi_groups filtro_g ON filtro_g.id=filtro_gt.groups_id
    WHERE filtro_gt.tickets_id=t.id AND filtro_gt.type=2
      AND CONCAT(filtro_g.name,' [',filtro_g.id,']')={{grupo_tecnico}}
)]]"""
 }
}
MARK="filtro_gt.tickets_id=t.id"
WHERE_RE=re.compile(r"\bWHERE\s+t\.is_deleted\s*=\s*0\b",re.I)
KEEP=("id","card_id","row","col","size_x","size_y","parameter_mappings",
      "visualization_settings","dashboard_tab_id","action_id","inline_parameters")

def api(method,path,obj=None):
    headers={"X-API-Key":KEY,"Accept":"application/json"}
    data=None
    if obj is not None:
        headers["Content-Type"]="application/json"
        data=json.dumps(obj,ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(BASE+"/api"+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=90) as res:
            raw=res.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s em %s: %s" %
                           (e.code,path,e.read().decode(errors="replace")[:2200]))
    except urllib.error.URLError as e:
        raise RuntimeError("Conexão com Metabase: %s" % e)

def all_cards():
    result=[]
    off=0
    while True:
        response=api("GET","/collection/%d/items?models=card&limit=100&offset=%d"%(COL,off))
        batch=response.get("data",[])
        result+=batch
        if not batch or len(batch)<100 or (
            response.get("total") is not None and off+len(batch)>=response["total"]):
            return result
        off+=len(batch)

def dashcards(d):
    return d.get("dashcards") or d.get("ordered_cards") or []

def sql_details(c):
    q=c.get("dataset_query",{})
    if q.get("stages"):
        stage=q["stages"][0]
        if isinstance(stage.get("native"),str):
            return "stages",stage["native"],stage.get("template-tags",[])
    native=q.get("native",{})
    if isinstance(native,dict) and isinstance(native.get("query"),str):
        return "legacy",native["query"],native.get("template-tags",{})
    raise RuntimeError("Formato de SQL desconhecido para card %d"%c["id"])

def patch_question(card):
    fmt,sql,tags=sql_details(card)
    if "FROM glpi_tickets t" not in sql or not WHERE_RE.search(sql):
        raise RuntimeError("Card %d sem FROM glpi_tickets t / WHERE t.is_deleted=0. "
                           "Revisão manual necessária; nada será alterado." % card["id"])
    existing_tags=(tags if isinstance(tags,list) else list(tags.values()))
    names={x.get("name") for x in existing_tags}
    params=copy.deepcopy(card.get("parameters") or [])
    params_names={p.get("slug") for p in params}
    added=[]
    for key,definition in VALUES.items():
        present=key in names
        has_sql="{{"+key+"}}" in sql
        if present != has_sql:
            raise RuntimeError("Card %d tem tag/SQL parcialmente configurado: %s"%
                               (card["id"],key))
        if not present:
            added.append(key)
    # Inserir ambos depois do WHERE externo, de forma segura.
    if added:
        match=WHERE_RE.search(sql)
        sql=sql[:match.end()] + "\n" + "\n".join(VALUES[k]["filter"] for k in added) + sql[match.end():]
    for key in added:
        t_id=str(uuid.uuid4())
        existing_tags.append({"id":t_id,"name":key,"display-name":VALUES[key]["label"],
                              "type":"text","required":False})
    for key in VALUES:
        if key not in params_names:
            # id será preservado se o card já tiver a tag (caso de execução parcial).
            tag=next(x for x in existing_tags if x["name"]==key)
            params.append({
                "id":tag["id"],"slug":key,"name":VALUES[key]["label"],
                "type":"string/=","isMultiSelect":False,
                "values_query_type":"list","values_source_type":"card",
                "values_source_config":None, # será preenchido antes de gravar
                "target":["variable",["template-tag",key]]
            })
    q=copy.deepcopy(card["dataset_query"])
    if fmt=="stages":
        q["stages"][0]["native"]=sql
        q["stages"][0]["template-tags"]=existing_tags
    else:
        q["native"]["query"]=sql
        q["native"]["template-tags"]={x["name"]:x for x in existing_tags}
    return {"dataset_query":q,"parameters":params}

def source_config(cid):
    return {
        "card_id":cid,
        "value_field":["field","valor",{"base-type":"type/Text"}],
        "label_field":["field","valor",{"base-type":"type/Text"}]
    }

def create_helpers(existing,apply):
    result={}
    for key,info in VALUES.items():
        found=[x for x in existing if x.get("name")==info["helper"]]
        if len(found)>1:
            raise RuntimeError("Pergunta auxiliar duplicada: "+info["helper"])
        if found:
            result[key]=found[0]["id"]
            print("LISTA EXISTENTE:",info["helper"],"ID",result[key])
        elif apply:
            card=api("POST","/card",{
                "name":info["helper"],
                "description":"Valores para filtro global da Central de Serviços.",
                "database_id":DB,"collection_id":COL,"display":"table",
                "dataset_query":{"database":DB,"type":"native",
                    "native":{"query":info["sql"],"template-tags":{}}},
                "visualization_settings":{}
            })
            result[key]=card["id"]
            print("LISTA CRIADA:",info["helper"],"ID",card["id"])
        else:
            result[key]=None
            print("CRIARIA LISTA:",info["helper"])
    return result

def patch_dashboard(d,helpers):
    existing=copy.deepcopy(d.get("parameters") or [])
    by_slug={p.get("slug"):p for p in existing}
    by_name={p.get("name"):p for p in existing}
    ids={}
    for key,info in VALUES.items():
        p=by_slug.get(key) or by_name.get(info["label"])
        if p is None:
            p={"id":str(uuid.uuid4()),"slug":key,
               "name":info["label"],"type":"string/=",
               "isMultiSelect":False,"values_query_type":"list",
               "values_source_type":"card",
               "values_source_config":source_config(helpers[key])}
            existing.append(p)
        else:
            p["values_source_type"]="card"
            p["values_query_type"]="list"
            p["values_source_config"]=source_config(helpers[key])
        ids[key]=p["id"]

    result=[]
    touched=0
    for item in dashcards(d):
        c={k:copy.deepcopy(item[k]) for k in KEEP if k in item}
        cid=c.get("card_id")
        if cid in CARD_IDS:
            mappings=[m for m in c.get("parameter_mappings",[])
                      if m.get("parameter_id") not in ids.values()]
            for key in VALUES:
                mappings.append({"parameter_id":ids[key],"card_id":cid,
                                 "target":["variable",["template-tag",key]]})
            c["parameter_mappings"]=mappings
            touched+=1
        result.append(c)
    if touched!=len(CARD_IDS):
        raise RuntimeError("Dashboard tem %d dos %d cards previstos. Abortado." %
                           (touched,len(CARD_IDS)))
    return {
        "name":d["name"],
        "width":d.get("width","full"),
        "parameters":existing,
        "dashcards":result,
    }

def make_backup(d,cards):
    file="backup_cs_entidade_grupo_"+dt.datetime.now().strftime("%Y%m%d_%H%M%S")+".json"
    with open(file,"w",encoding="utf-8") as out:
        json.dump({"dashboard":d,"cards":cards},out,ensure_ascii=False,indent=2)
    print("BACKUP:",os.path.abspath(file))

def restore(file,apply):
    with open(file,encoding="utf-8") as f:
        backup=json.load(f)
    d=backup["dashboard"]
    if d.get("id")!=DASH:
        raise RuntimeError("Backup é de outro dashboard")
    print("Restaurar",len(backup["cards"]),"perguntas e dashboard",DASH)
    if not apply:
        print("Simulação de restauração. Acrescente --apply.")
        return
    for c in backup["cards"]:
        api("PUT","/card/%s"%c["id"],{
            "dataset_query":c["dataset_query"],"parameters":c.get("parameters",[])
        })
    saved_cards=[{k:copy.deepcopy(item[k]) for k in KEEP if k in item}
                 for item in dashcards(d)]
    api("PUT","/dashboard/%d"%DASH,{
        "name":d["name"],"width":d.get("width","full"),
        "parameters":d.get("parameters",[]),"dashcards":saved_cards
    })
    print("RESTAURADO. Perguntas auxiliares permanecem na coleção.")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--restore",metavar="BACKUP_JSON")
    args=parser.parse_args()
    if not KEY:
        raise RuntimeError("MB_API_KEY ausente")
    if args.restore:
        restore(args.restore,args.apply)
        return
    d=api("GET","/dashboard/%d"%DASH)
    if d.get("name")!="Central de Serviços | Cadmus":
        raise RuntimeError("Dashboard 3 não corresponde à Central de Serviços | Cadmus")
    collection=api("GET","/collection/%d"%COL)
    print("Coleção:",COL,collection.get("name"))
    existing=all_cards()
    cards={}
    for cid in CARD_IDS:
        c=api("GET","/card/%d"%cid)
        if c.get("database_id")!=DB or c.get("collection_id")!=COL:
            raise RuntimeError("Card %d fora do DB2 / coleção 6"%cid)
        cards[cid]=c
    # Preflight ALL SQL before writing anything.
    staged={cid:patch_question(c) for cid,c in cards.items()}
    print("Perguntas validadas:",len(staged))
    print("FILTROS EXISTENTES: Período, Organização, Categoria, Técnico")
    print("NOVOS FILTROS: Entidade, Grupo Técnico")
    if len(d.get("parameters") or []) not in (4,6):
        raise RuntimeError("Esperados quatro ou seis filtros atuais no dashboard")
    if not args.apply:
        create_helpers(existing,False)
        print("SIMULAÇÃO: sem modificações. Execute com --apply.")
        return

    make_backup(d,list(cards.values()))
    helpers=create_helpers(existing,True)
    for cid,modified in sorted(staged.items()):
        for p in modified["parameters"]:
            if p.get("slug") in helpers:
                p["values_source_config"]=source_config(helpers[p["slug"]])
        api("PUT","/card/%d"%cid,modified)
        print("OK: pergunta",cid)
    latest=api("GET","/dashboard/%d"%DASH)
    patch=patch_dashboard(latest,helpers)
    api("PUT","/dashboard/%d"%DASH,patch)
    validated=api("GET","/dashboard/%d"%DASH)
    print("DASHBOARD:",DASH)
    print("Filtros globais:",len(validated.get("parameters") or []))
    print("Cards:",len(dashcards(validated)))
    print("SUCESSO:",BASE+"/dashboard/3")
    print("Valide filtrando uma entidade e um grupo técnico.")
    print("Nota: grupo técnico = grupo ATRIBUÍDO ao chamado (type=2), "
          "não grupo solicitante ou do observador.")

if __name__=="__main__":
    try:
        main()
    except (RuntimeError,OSError,ValueError,KeyError) as e:
        sys.exit("ERRO: %s"%e)
