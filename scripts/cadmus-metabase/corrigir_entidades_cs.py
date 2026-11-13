#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Amplia a Central de Serviços para entidades de Administrativo, Gestão de Ativos e TI.

Admin: 137,138,139,140,141,142; Gestão de Ativos: 162; TI: 159,160,161,164,165.
Exclui PeopleTech(156), PPPRO(157), Beefor(158).
Não inclui ROOT(0) e LIGA ÁGIL(83).

Atualiza perguntas 40,42..56, lista de Técnicos (41), fontes dos filtros
Entidade/Grupo Técnico (se existentes), e opções de Organização.
Cadmus e PeoplePro mantêm cores; Outras entidades em cinza nos gráficos
43 e 54. Não altera GLPI, blocos, filtros restantes ou posição dos gráficos.

Simular: python3 corrigir_entidades_cs.py
Aplicar: python3 corrigir_entidades_cs.py --apply
Reverter: python3 corrigir_entidades_cs.py --restore BACKUP.json --apply
"""
import argparse,copy,datetime,json,os,re,sys,urllib.request,urllib.error
BASE=os.getenv("MB_URL","http://127.0.0.1:3000").rstrip("/")
KEY=os.getenv("MB_API_KEY","")
IDS=[40]+list(range(42,57))
SCOPE="(137,138,139,140,141,142,159,160,161,162,164,165)"
ORGS=["Cadmus","PeoplePro","VENTRON","SETÚRIA","LIGA ÁGIL","ADMINISTRATIVO","TI","GESTÃO DE ATIVOS","RPA","SEGINFO E SITES"]
CASE="""CASE
 WHEN t.entities_id IN (138,160) THEN 'Cadmus'
 WHEN t.entities_id IN (140,161) THEN 'PeoplePro'
 WHEN t.entities_id=139 THEN 'VENTRON'
 WHEN t.entities_id=141 THEN 'SETÚRIA'
 WHEN t.entities_id=142 THEN 'LIGA ÁGIL'
 WHEN t.entities_id=137 THEN 'ADMINISTRATIVO'
 WHEN t.entities_id=159 THEN 'TI'
 WHEN t.entities_id=162 THEN 'GESTÃO DE ATIVOS'
 WHEN t.entities_id=164 THEN 'SEGINFO E SITES'
 WHEN t.entities_id=165 THEN 'RPA'
 END"""
CASE_RX=re.compile(r"CASE\s+WHEN\s+t\.entities_id\s+IN\s*\(\s*138\s*,\s*160\s*\)\s+THEN\s+'Cadmus'\s+(?:WHEN\s+t\.entities_id\s+IN\s*\(\s*140\s*,\s*161\s*\)\s+THEN\s+'PeoplePro'|ELSE\s+'PeoplePro')\s+END",re.I)
SCOPE_RX=re.compile(r"\bt\.entities_id\s+IN\s*\(\s*(?:138\s*,\s*140\s*,\s*160\s*,\s*161|137\s*,\s*138\s*,\s*139\s*,\s*140\s*,\s*141\s*,\s*142\s*,\s*159\s*,\s*160\s*,\s*161\s*,\s*164\s*,\s*165)\s*\)",re.I)
KEEP=("id","card_id","row","col","size_x","size_y","parameter_mappings",
      "visualization_settings","dashboard_tab_id","action_id","inline_parameters")

def api(method,path,body=None):
 h={"X-API-Key":KEY,"Accept":"application/json"}
 data=None
 if body is not None:
  h["Content-Type"]="application/json"
  data=json.dumps(body,ensure_ascii=False).encode()
 req=urllib.request.Request(BASE+"/api"+path,headers=h,data=data,method=method)
 try:
  with urllib.request.urlopen(req,timeout=90) as res:
   raw=res.read()
   return json.loads(raw.decode()) if raw else {}
 except urllib.error.HTTPError as ex:
  raise RuntimeError("HTTP %s %s: %s"%(ex.code,path,ex.read().decode(errors="replace")[:1600]))
 except urllib.error.URLError as ex: raise RuntimeError("Conexão: %s"%ex)

def query_get(c):
 d=c["dataset_query"]
 if d.get("stages") and isinstance(d["stages"][0].get("native"),str):
  return d["stages"][0]["native"],"stages"
 if isinstance(d.get("native"),dict) and isinstance(d["native"].get("query"),str):
  return d["native"]["query"],"legacy"
 raise RuntimeError("SQL nativo ausente: %d"%c["id"])

def query_set(c,sql,fmt):
 q=copy.deepcopy(c["dataset_query"])
 if fmt=="stages": q["stages"][0]["native"]=sql
 else: q["native"]["query"]=sql
 return q

def helper_sql(name):
 scope=SCOPE
 if name=="Filtro CS | Entidade":
  return ("SELECT DISTINCT e.completename AS valor FROM glpi_entities e "
          "WHERE e.id IN %s AND e.completename IS NOT NULL "
          "AND e.completename<>'' ORDER BY valor"%scope)
 if name=="Filtro CS | Grupo Técnico":
  return ("SELECT DISTINCT CONCAT(g.name,' [',g.id,']') AS valor "
          "FROM glpi_groups g JOIN glpi_groups_tickets gt ON gt.groups_id=g.id "
          "AND gt.type=2 JOIN glpi_tickets t ON t.id=gt.tickets_id "
          "WHERE t.is_deleted=0 AND t.entities_id IN %s "
          "AND g.name IS NOT NULL AND TRIM(g.name)<>'' ORDER BY valor"%scope)

# O relatório de auditoria confirmou escopo com 11 entidades (sem 162).
# Ajuste a cláusula externa da consulta, sem substituir os grupos Cadmus/PeoplePro.
SCOPE_OLD11=re.compile(r"\\bt\\.entities_id\\s+IN\\s*\\(\\s*137\\s*,\\s*138\\s*,\\s*139\\s*,\\s*140\\s*,\\s*141\\s*,\\s*142\\s*,\\s*159\\s*,\\s*160\\s*,\\s*161\\s*,\\s*164\\s*,\\s*165\\s*\\)",re.I)
SCOPE_NEW=re.compile(r"\\bt\\.entities_id\\s+IN\\s*\\(\\s*137\\s*,\\s*138\\s*,\\s*139\\s*,\\s*140\\s*,\\s*141\\s*,\\s*142\\s*,\\s*159\\s*,\\s*160\\s*,\\s*161\\s*,\\s*162\\s*,\\s*164\\s*,\\s*165\\s*\\)",re.I)
COMPACT_CASE_RX=re.compile(r"CASE\\s+WHEN\\s+t\\.entities_id\\s+IN\\s*\\(\\s*138\\s*,\\s*160\\s*\\)\\s+THEN\\s+'Cadmus'\\s+ELSE\\s+'PeoplePro'\\s+END",re.I)


def apply_scope(sql):
 sql=SCOPE_RX.sub("t.entities_id IN "+SCOPE,sql)
 sql=SCOPE_OLD11.sub("t.entities_id IN "+SCOPE,sql)
 sql=CASE_RX.sub(CASE,sql)
 sql=COMPACT_CASE_RX.sub(CASE,sql)
 # O CASE de Organização expandido existe em todos os cards da auditoria.
 # Acrescentar 162 apenas quando ainda não estiver presente.
 if "t.entities_id=162 THEN 'GESTÃO DE ATIVOS'" not in sql:
  needle="WHEN t.entities_id=164 THEN 'SEGINFO E SITES'"
  if needle in sql:
   sql=sql.replace(needle,
       "WHEN t.entities_id=162 THEN 'GESTÃO DE ATIVOS'\\n "+needle)
 if not SCOPE_NEW.search(sql):
  raise RuntimeError("Escopo de 12 entidades não localizado após transformação")
 if SCOPE_OLD11.search(sql):
  raise RuntimeError("Permaneceu escopo antigo de 11 entidades")
 if "t.entities_id=162 THEN 'GESTÃO DE ATIVOS'" not in sql:
  raise RuntimeError("CASE de Organização ainda não inclui Gestão de Ativos 162")
 return sql

def new_chart_series(sql,cid):
 if cid not in (43,54) or "AS PeoplePro" not in sql or "AS Outras" in sql: return sql,False
 location=re.search(r"\bFROM\s+glpi_tickets\s+t\b",sql,re.I)
 if not location: raise RuntimeError("FROM inesperado no gráfico %d"%cid)
 ident="t.id" if cid==43 else "s.id"
 col=("COUNT(DISTINCT CASE WHEN t.entities_id NOT IN (138,140,160,161) "
      "THEN %s END) AS Outras"%ident)
 return sql[:location.start()].rstrip()+",\n "+col+"\n"+sql[location.start():],True

def prepared_card(card):
 sql,fmt=query_get(card)
 if "FROM glpi_tickets t" not in sql: raise RuntimeError("FROM inesperado: %d"%card["id"])
 revised=apply_scope(sql)
 revised,third=new_chart_series(revised,card["id"])
 # Evita contabilizar outras empresas como PeoplePro
 if re.search(r"CASE\s+WHEN\s+t\.entities_id\s+IN\s*\(138\s*,\s*160\)\s+THEN\s+'Cadmus'\s+ELSE\s+'PeoplePro'",revised,re.I):
  raise RuntimeError("CASE inválido, precisa revisão no card %d"%card["id"])
 parameters=copy.deepcopy(card.get("parameters") or [])
 for p in parameters:
  if p.get("slug")=="organizacao":
   p.update({"values_query_type":"list","values_source_type":"static-list",
             "values_source_config":{"values":[[x] for x in ORGS]}})
 viz=copy.deepcopy(card.get("visualization_settings") or {})
 if third:
  viz["graph.metrics"]=["Cadmus","PeoplePro","Outras"]
  viz["graph.colors"]=["#0D2A43","#FF873F","#80868B"]
  settings=viz.get("series_settings") or {}
  settings.update({"Cadmus":{"color":"#0D2A43"},
                   "PeoplePro":{"color":"#FF873F"},"Outras":{"color":"#80868B"}})
  viz["series_settings"]=settings
 return {"dataset_query":query_set(card,revised,fmt),
         "parameters":parameters,"visualization_settings":viz},sql!=revised

def list_cards():
 data=api("GET","/collection/6/items?models=card&limit=300")
 return data.get("data",[])

def patch_dashboard(d):
 params=copy.deepcopy(d.get("parameters") or [])
 org=[p for p in params if p.get("slug")=="organizacao" or p.get("name") in ("Organizacao","Organização")]
 if len(org)!=1: raise RuntimeError("Filtro Organização não encontrado de forma única")
 org[0].update({"values_query_type":"list","values_source_type":"static-list",
                "values_source_config":{"values":[[x] for x in ORGS]}})
 return {"name":d["name"],"width":d.get("width","full"),
         "parameters":params,"dashcards":[
             {k:copy.deepcopy(c[k]) for k in KEEP if k in c}
             for c in (d.get("dashcards") or d.get("ordered_cards") or [])]}

def run():
 p=argparse.ArgumentParser()
 p.add_argument("--apply",action="store_true")
 p.add_argument("--restore")
 a=p.parse_args()
 if not KEY: raise RuntimeError("MB_API_KEY não configurada")
 d=api("GET","/dashboard/3")
 if d.get("name")!="Central de Serviços | Cadmus": raise RuntimeError("Dashboard 3 incorreto")
 allc=list_cards()
 if a.restore:
  with open(a.restore,encoding="utf-8") as f: backup=json.load(f)
  if backup["dashboard"].get("id")!=3: raise RuntimeError("Backup incorreto")
  print("RESTAURAR",len(backup["cards"]),"perguntas")
  if not a.apply: return
  for card in backup["cards"]:
   api("PUT","/card/%d"%card["id"],{
       "dataset_query":card["dataset_query"],
       "parameters":card.get("parameters",[]),
       "visualization_settings":card.get("visualization_settings",{})})
  old=backup["dashboard"]
  api("PUT","/dashboard/3",{
      "name":old["name"],"width":old.get("width","full"),
      "parameters":old.get("parameters",[]),
      "dashcards":[{k:c[k] for k in KEEP if k in c}
                   for c in (old.get("dashcards") or old.get("ordered_cards") or [])]})
  print("RESTAURADO dashboard 3")
  return
 cards=[api("GET","/card/%d"%cid) for cid in IDS]
 for c in cards:
  if c.get("collection_id")!=6 or c.get("database_id")!=2:
   raise RuntimeError("Pergunta fora da coleção 6 / banco 2: %d"%c["id"])
 updates=[(c,prepared_card(c)) for c in cards]
 aux=[]
 # Atualiza também técnicos (pergunta 41) e listas de Entidade/Grupo.
 technical=api("GET","/card/41")
 if technical.get("collection_id")==6:
  aux.append(technical)
 for label in ("Filtro CS | Entidade","Filtro CS | Grupo Técnico"):
  found=[x for x in allc if x.get("name")==label]
  if len(found)>1: raise RuntimeError("Duas listas auxiliares "+label)
  if found: aux.append(api("GET","/card/%d"%found[0]["id"]))
 helpers=[]
 for c in aux:
  sql,fmt=query_get(c)
  label=c["name"]
  if c["id"]==41:
   new=SCOPE_RX.sub("t.entities_id IN "+SCOPE,sql)
   new=SCOPE_OLD11.sub("t.entities_id IN "+SCOPE,new)
   if not SCOPE_NEW.search(new):
    raise RuntimeError("Lista de técnicos não contém escopo 162")
  else:
   new=helper_sql(label)
  if new!=sql:
   helpers.append((c,{"dataset_query":query_set(c,new,fmt)}))
 patch=patch_dashboard(d)
 print("NOVO ESCOPO: Administrativo 137,138,139,140,141,142 | Gestão de Ativos 162 | TI 159,160,161,164,165")
 print("EXCLUÍDOS: 156,157,158; ROOT 0; LIGA ÁGIL 83")
 print("Perguntas a revisar:",len(updates),"| Listas auxiliares a ajustar:",len(helpers))
 for c,(payload,changed) in updates:
  print(c["id"],"SQL atualizado" if changed else "SQL sem alteração","-",c["name"])
 if not a.apply:
  print("SIMULAÇÃO. Nenhuma gravação. Execute --apply.")
  return
 fn="backup_escopo_cs_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".json"
 with open(fn,"w",encoding="utf-8") as f:
  json.dump({"dashboard":d,"cards":cards+aux},f,ensure_ascii=False,indent=2)
 print("BACKUP:",os.path.abspath(fn))
 for c,(payload,changed) in updates:
  api("PUT","/card/%d"%c["id"],payload)
  print("OK",c["id"])
 for c,payload in helpers:
  api("PUT","/card/%d"%c["id"],payload)
  print("OK lista",c["id"])
 api("PUT","/dashboard/3",patch)
 after=api("GET","/dashboard/3")
 print("Dashboard 3 atualizado | filtros:",len(after.get("parameters") or []))
 print("ABRIR:",BASE+"/dashboard/3")
 print("Teste Organização, Entidade e Grupo Técnico. Confira as métricas e as cores.")

if __name__=="__main__":
 try: run()
 except (RuntimeError,OSError,ValueError,KeyError) as e: sys.exit("ERRO: %s"%e)
