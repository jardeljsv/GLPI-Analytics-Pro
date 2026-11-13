#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cria a 1a versao do painel Gestao de Ativos | Cadmus no Metabase.

Somente API Metabase, sem escrita no GLPI. Fonte: glpidb via DB 2.
Escopo operacional inicial, observado no diagnostico: entidades 83, 137, 162.
Ativos das tabelas computers, monitors, peripherals, phones e printers.
Nao atribui ativos a Cadmus/PeoplePro sem fonte comprovada.

Simular: python3 criar_dashboard_ativos_cadmus.py
Criar:    python3 criar_dashboard_ativos_cadmus.py --apply
MB_API_KEY obrigatoria. MB_URL opcional (padrao http://127.0.0.1:3000).

A operacao e idempotente por NOME de colecao, pergunta e dashboard.
Nao altera perguntas de mesmo nome ja existentes.
"""
import argparse
import copy
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE=os.environ.get("MB_URL","http://127.0.0.1:3000").rstrip("/")
KEY=os.environ.get("MB_API_KEY","")
DB=2
COLLECTION_NAME="Gestão de Ativos | Cadmus"
DASHBOARD_NAME="Gestão de Ativos | Cadmus"
ENTITIES="83,137,162"
BLUE="#0D2A43"
GREEN="#70DC68"
ORANGE="#FF873F"
GRAY="#80868B"
ASSETS=[
 ("Computador","glpi_computers","Computer"),
 ("Monitor","glpi_monitors","Monitor"),
 ("Periférico","glpi_peripherals","Peripheral"),
 ("Telefone","glpi_phones","Phone"),
 ("Impressora","glpi_printers","Printer")
]
def api(method, path, obj=None):
    headers={"X-API-Key":KEY,"Accept":"application/json"}
    data=None
    if obj is not None:
        headers["Content-Type"]="application/json"
        data=json.dumps(obj,ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(BASE+"/api"+path,headers=headers,data=data,method=method)
    try:
        with urllib.request.urlopen(req,timeout=90) as response:
            raw=response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s %s: %s"%(e.code,path,e.read().decode(errors="replace")[:1800]))
    except urllib.error.URLError as e:
        raise RuntimeError("Conexao Metabase: %s"%e)

# SQL de inventario padronizado. Escopo explicito, nao usa entidades de tickets.
UNION="\nUNION ALL\n".join(
    "SELECT '%s' AS tipo, a.id, a.entities_id, a.states_id, a.locations_id, "
    "a.users_id, a.name, a.serial, a.date_creation, a.date_mod, "
    "%s AS last_inventory_update, '%s' AS itemtype "
    "FROM %s a WHERE a.is_deleted=0 AND a.is_template=0 "
    "AND a.entities_id IN (%s)"%(
        label, "a.last_inventory_update" if itemtype=="Computer" else "NULL",
        itemtype,table,ENTITIES)
    for label,table,itemtype in ASSETS)
BASE_ASSETS="(\n"+UNION+"\n) a"
NOTES = ("Escopo inicial: entidades GLPI 83, 137 e 162; apenas equipamentos "
         "nao excluidos e nao modelo. Nao ha separacao comprovada entre "
         "Cadmus e PeoplePro no cadastro centralizado de ativos.")

def sql(select, join="",where="",group="",order=""):
    return ("SELECT "+select+"\nFROM "+BASE_ASSETS+"\n"+join+"\n"
            +("WHERE "+where+"\n" if where else "")
            +(group+"\n" if group else "")
            +(order+"\n" if order else "")).strip()

DEF=[
 ("01 | Total de ativos","scalar",sql("COUNT(*) AS total_ativos"),None,3),
 ("02 | Disponíveis (estado 5)","scalar",sql("COUNT(*) AS disponiveis",where="a.states_id=5"),None,3),
 ("03 | Sem usuário vinculado","scalar",sql("COUNT(*) AS sem_usuario",where="COALESCE(a.users_id,0)=0"),None,3),
 ("04 | Computadores sem data de inventário","scalar",
   sql("COUNT(*) AS sem_inventario",where="a.tipo='Computador' AND a.last_inventory_update IS NULL"),None,3),
 ("05 | Parque por tipo","bar",
   sql("a.tipo AS tipo, COUNT(*) AS quantidade",group="GROUP BY a.tipo",order="ORDER BY quantidade DESC"),BLUE,8),
 ("06 | Parque por estado","row",
   sql("COALESCE(NULLIF(s.completename,''),NULLIF(s.name,''),'Sem estado') AS estado, COUNT(*) AS quantidade",
       join="LEFT JOIN glpi_states s ON s.id=a.states_id",group="GROUP BY a.states_id,s.completename,s.name",
       order="ORDER BY quantidade DESC"),BLUE,8),
 ("07 | Estoque disponível por tipo","bar",
   sql("a.tipo AS tipo, COUNT(*) AS quantidade",where="a.states_id=5",
       group="GROUP BY a.tipo",order="ORDER BY quantidade DESC"),GREEN,8),
 ("08 | Ativos sem usuário por tipo","bar",
   sql("a.tipo AS tipo, COUNT(*) AS quantidade",where="COALESCE(a.users_id,0)=0",
       group="GROUP BY a.tipo",order="ORDER BY quantidade DESC"),ORANGE,8),
 ("09 | Ativos por localização","row",
   sql("COALESCE(NULLIF(l.completename,''),NULLIF(l.name,''),'Sem localização') AS localizacao, COUNT(*) AS quantidade",
       join="LEFT JOIN glpi_locations l ON l.id=a.locations_id",
       group="GROUP BY a.locations_id,l.completename,l.name",
       order="ORDER BY quantidade DESC LIMIT 20"),BLUE,9),
 ("10 | Computadores por modelo","row",
   """COALESCE(NULLIF(m.name,''),'Sem modelo') AS modelo, COUNT(*) AS quantidade""",
   None,9),
 ("11 | Garantias a vencer em 90 dias","scalar",
   sql("COUNT(*) AS garantias_a_vencer",
       join="JOIN (SELECT items_id,itemtype,MAX(warranty_date) AS warranty_date "
            "FROM glpi_infocoms WHERE itemtype IN ('Computer','Monitor','Peripheral','Phone','Printer') "
            "GROUP BY items_id,itemtype) i ON i.items_id=a.id AND i.itemtype=a.itemtype",
       where="i.warranty_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 90 DAY)"),
   None,4),
 ("12 | Ativos em descarte","scalar",sql("COUNT(*) AS em_descarte",where="a.states_id=4"),None,4),
 ("13 | Idade do parque de computadores","bar",
   None,GRAY,8),
 ("14 | Ativos por estado e tipo","bar",
   sql("a.tipo AS tipo, COALESCE(NULLIF(s.name,''),'Sem estado') AS estado,COUNT(*) AS quantidade",
       join="LEFT JOIN glpi_states s ON s.id=a.states_id",
       group="GROUP BY a.tipo,a.states_id,s.name",
       order="ORDER BY a.tipo,quantidade DESC"),BLUE,8),
 ("15 | Garantias por vencimento","row",
   None,ORANGE,8)
]
# Correcoes especificas que usam modelo, infocoms ou datas.
for idx,(name,display,statement,color,_) in enumerate(DEF):
    if name.startswith("10 |"):
        statement=sql(
          "COALESCE(NULLIF(m.name,''),'Sem modelo') AS modelo,COUNT(*) AS quantidade",
          join="LEFT JOIN glpi_computermodels m ON m.id=a.id_model",
          where="a.tipo='Computador'",
          group="GROUP BY a.id_model,m.name",order="ORDER BY quantidade DESC LIMIT 20")
        # Esta consulta requer computermodels_id na fonte: fornecemos SQL separado
        statement=("SELECT COALESCE(NULLIF(m.name,''),'Sem modelo') AS modelo,COUNT(*) AS quantidade "
                   "FROM glpi_computers c LEFT JOIN glpi_computermodels m ON m.id=c.computermodels_id "
                   "WHERE c.is_deleted=0 AND c.is_template=0 AND c.entities_id IN ("+ENTITIES+") "
                   "GROUP BY c.computermodels_id,m.name ORDER BY quantidade DESC LIMIT 20")
        DEF[idx]=(name,display,statement,color,9)
    if name.startswith("13 |"):
        # Idade calculada somente quando buy_date foi preenchida.
        statement=("SELECT CASE "
                   "WHEN TIMESTAMPDIFF(YEAR,i.buy_date,CURDATE()) < 2 THEN 'Menos de 2 anos' "
                   "WHEN TIMESTAMPDIFF(YEAR,i.buy_date,CURDATE()) < 4 THEN '2 a 3 anos' "
                   "WHEN TIMESTAMPDIFF(YEAR,i.buy_date,CURDATE()) < 6 THEN '4 a 5 anos' "
                   "ELSE '6 anos ou mais' END AS faixa_etaria,COUNT(*) AS computadores "
                   "FROM glpi_computers c "
                   "JOIN (SELECT items_id,MIN(buy_date) AS buy_date FROM glpi_infocoms "
                   "WHERE itemtype='Computer' AND buy_date IS NOT NULL GROUP BY items_id) i "
                   "ON i.items_id=c.id "
                   "WHERE c.is_deleted=0 AND c.is_template=0 AND c.entities_id IN ("+ENTITIES+") "
                   "AND i.buy_date <= CURDATE() "
                   "GROUP BY faixa_etaria "
                   "ORDER BY MIN(TIMESTAMPDIFF(YEAR,i.buy_date,CURDATE()))")
        DEF[idx]=(name,display,statement,color,8)
    if name.startswith("15 |"):
        statement=sql(
          "DATE_FORMAT(i.warranty_date,'%Y-%m') AS mes_vencimento,COUNT(*) AS quantidade",
          join="JOIN (SELECT items_id,itemtype,MAX(warranty_date) AS warranty_date "
               "FROM glpi_infocoms WHERE itemtype IN ('Computer','Monitor','Peripheral','Phone','Printer') "
               "GROUP BY items_id,itemtype) i ON i.items_id=a.id AND i.itemtype=a.itemtype",
          where="i.warranty_date>=CURDATE() AND i.warranty_date < DATE_ADD(CURDATE(),INTERVAL 12 MONTH)",
          group="GROUP BY DATE_FORMAT(i.warranty_date,'%Y-%m')",
          order="ORDER BY mes_vencimento")
        DEF[idx]=(name,display,statement,color,8)

# Posicoes de 24 colunas. Header primeiro (texto via bloco virtual).
PLACEMENT=[
 (0,0,6,4),(6,0,6,4),(12,0,6,4),(18,0,6,4),
 (0,5,12,8),(12,5,12,8),
 (0,13,12,8),(12,13,12,8),
 (0,21,12,9),(12,21,12,9),
 (0,30,6,4),(6,30,6,4),
 (12,30,12,8),
 (0,38,12,8),(12,38,12,8)
]
def get_or_create_collection(apply):
    result=api("GET","/collection")
    entries=result if isinstance(result,list) else result.get("data",[])
    found=[c for c in entries if c.get("name")==COLLECTION_NAME and not c.get("archived")]
    if len(found)>1: raise RuntimeError("Multiplas colecoes com o mesmo nome.")
    if found: return found[0]["id"]
    if not apply: return None
    return api("POST","/collection",{"name":COLLECTION_NAME,"color":BLUE,
                                      "description":NOTES})["id"]

def collection_cards(cid):
    response=api("GET","/collection/%s/items?models=card&limit=200"%cid)
    return response.get("data",[])

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    if not KEY: raise RuntimeError("MB_API_KEY nao definida.")
    collection_id=get_or_create_collection(args.apply)
    existing_cards={} if collection_id is None else {
        x["name"]:x["id"] for x in collection_cards(collection_id)}
    print("Gestao de Ativos Cadmus - etapa inicial")
    print("Escopo: entidades",ENTITIES,"(sem diferenciacao Cadmus/PeoplePro)")
    print("Colecao:",collection_id or "(nova)")
    cards=[]
    for idx,(name,display,statement,color,height) in enumerate(DEF):
        if not statement: raise RuntimeError("Consulta sem SQL: "+name)
        if name in existing_cards:
            cid=existing_cards[name]
            print("EXISTE",cid,name)
        elif not args.apply:
            cid=None
            print("CRIARIA",name)
        else:
            settings={"graph.show_values":True}
            if color and display in ("bar","row"):
                settings["graph.colors"]=[color]
            payload={
                "name":name,
                "description":NOTES,
                "collection_id":collection_id,
                "database_id":DB,
                "display":display,
                "dataset_query":{"database":DB,"type":"native","native":{"query":statement,"template-tags":{}}},
                "visualization_settings":settings
            }
            created=api("POST","/card",payload)
            cid=created["id"]
            print("CRIADO",cid,name)
        cards.append(cid)
    if not args.apply:
        print("SIMULACAO. Nenhuma alteracao feita; execute --apply.")
        return

    dashboards=api("GET","/collection/%s/items?models=dashboard&limit=100"%collection_id).get("data",[])
    existing=next((d for d in dashboards if d.get("name")==DASHBOARD_NAME),None)
    if existing:
        print("Dashboard JA EXISTE (ID %s). Preservado sem alteracoes."%existing["id"])
        return

    dash=api("POST","/dashboard",{"name":DASHBOARD_NAME,"collection_id":collection_id,
                                   "description":NOTES})
    did=dash["id"]
    print("Dashboard criado:",did)
    dashcards=[]
    for idx,cid in enumerate(cards):
        col,row,w,h=PLACEMENT[idx]
        dashcards.append({
           "id":-idx-1,"card_id":cid,"col":col,"row":row,
           "size_x":w,"size_y":h,
           "parameter_mappings":[],"visualization_settings":{}
        })
    try:
        api("PUT","/dashboard/%s"%did,
            {"name":DASHBOARD_NAME,"width":"full","parameters":[],"dashcards":dashcards})
    except Exception as e:
        print("Dashboard ID %s foi criado, mas falhou a insercao dos cards."%did)
        raise
    check=api("GET","/dashboard/%s"%did)
    result=check.get("dashcards") or check.get("ordered_cards") or []
    print("VALIDADO: dashboard",did,"com",len(result),"indicadores")
    if len(result)!=len(cards): raise RuntimeError("Contagem de indicadores divergente.")
    print("ABRIR: %s/dashboard/%s"%(BASE,did))
    print("Proximas etapas: padronizar entidade por organizacao e mapear processos de movimentacao.")
if __name__=="__main__":
    try: main()
    except (RuntimeError,KeyError,ValueError) as err: sys.exit("ERRO: "+str(err))
