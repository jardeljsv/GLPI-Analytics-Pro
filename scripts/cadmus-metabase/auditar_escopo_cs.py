#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria SOMENTE LEITURA: Central de Serviços dashboard 3, coleção 6.
Não envia POST nem PUT. Não exige permissões de escrita.
Gera relatório local contendo SQL das perguntas 40–56 e filtros existentes.
NÃO divulgue MB_API_KEY (o relatório não inclui a chave).
"""
import json,os,urllib.request,urllib.error,datetime,re
BASE=os.getenv("MB_URL","http://127.0.0.1:3000").rstrip("/")
KEY=os.getenv("MB_API_KEY","")
IDS=[40,41]+list(range(42,57))
if not KEY: raise SystemExit("MB_API_KEY ausente")
def get(path):
    req=urllib.request.Request(BASE+"/api"+path,headers={"X-API-Key":KEY,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=45) as r:return json.load(r)
def sql_of(c):
    q=c.get("dataset_query") or {}
    if q.get("stages"):
        return q["stages"][0].get("native",""),q["stages"][0].get("template-tags",[])
    n=q.get("native") or {}
    return n.get("query",""),n.get("template-tags",{})
dash=get("/dashboard/3")
col=get("/collection/6")
if dash.get("collection_id")!=6: raise SystemExit("Dashboard 3 fora da coleção 6")
cards={}
for i in IDS:
    obj=get("/card/"+str(i))
    if obj.get("collection_id")!=6: raise SystemExit("Pergunta %d fora da coleção 6"%i)
    sql,tags=sql_of(obj)
    data={
        "id":i, "name":obj.get("name"),
        "sql":sql,
        "template_tags":[{"name":x.get("name"),"type":x.get("type")}
             for x in (tags if isinstance(tags,list) else tags.values())],
        "parameters":[{"slug":x.get("slug"),"name":x.get("name"),"type":x.get("type"),
             "values_source_type":x.get("values_source_type"),
             "values_source_config":x.get("values_source_config")}
             for x in obj.get("parameters",[])],
        "entity_predicates":re.findall(r"(?:\b\w+\.)?entities_id\s+(?:IN\s*\([^)]*\)|=\s*\d+)",sql,re.I),
        "organization_case":bool(re.search(r"CASE[\s\S]*?t\.entities_id",sql,re.I)),
        "groups":bool(re.search("glpi_groups_tickets",sql,re.I)),
    }
    cards[str(i)]=data
report={"collection":col.get("name"),"dashboard":dash.get("name"),
        "dashboard_filters":dash.get("parameters",[]),"cards":cards}
fn="auditoria_cs_escopo_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".json"
with open(fn,"w",encoding="utf-8") as f:json.dump(report,f,ensure_ascii=False,indent=2)
print("AUDITORIA SOMENTE LEITURA | Dashboard 3 | Coleção 6")
print("Relatório:",os.path.abspath(fn))
print("Filtros globais:",[(x.get("name"),x.get("slug")) for x in dash.get("parameters",[])])
for i in IDS:
    x=cards[str(i)]
    print("CARD",i,x["name"])
    print("  ENTIDADES:",x["entity_predicates"])
    print("  TAGS:",[t["name"] for t in x["template_tags"]])
    print("  ORGANIZACAO CASE:",x["organization_case"])
    if i in (40,41,43,54):
        print("  SQL COMPLETO:",x["sql"])
print("Nenhuma alteração realizada.")
