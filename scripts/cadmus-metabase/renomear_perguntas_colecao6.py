#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove 'Cadmus' dos nomes das perguntas da coleção 6 do Metabase.

Antes:  CS Cadmus | 01 Chamados abertos
Depois: CS | 01 Chamados abertos

Somente PUT /api/card/{id} com campo "name".
Não renomeia dashboard, coleção, outras perguntas nem muda SQL/filtros.
Modo simulação por padrão. Backup JSON dos nomes antes da aplicação.

Uso:
  python3 renomear_perguntas_colecao6.py
  python3 renomear_perguntas_colecao6.py --apply
  python3 renomear_perguntas_colecao6.py --restore backup_nomes_colecao6_....json --apply

Requer MB_API_KEY. MB_URL opcional.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE=os.getenv("MB_URL","http://127.0.0.1:3000").rstrip("/")
KEY=os.getenv("MB_API_KEY","")
COLLECTION_ID=6
PREFIX=re.compile(r"^CS\s+Cadmus\s*\|\s*",re.IGNORECASE)

def api(method,path,body=None):
    hdr={"X-API-Key":KEY,"Accept":"application/json"}
    payload=None
    if body is not None:
        hdr["Content-Type"]="application/json"
        payload=json.dumps(body,ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(BASE+"/api"+path,data=payload,headers=hdr,method=method)
    try:
        with urllib.request.urlopen(req,timeout=60) as res:
            raw=res.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s %s: %s"%(e.code,path,e.read().decode(errors="replace")[:1400]))
    except urllib.error.URLError as e:
        raise RuntimeError("Conexao: %s"%e)

def all_cards():
    out=[]
    offset=0
    limit=100
    while True:
        res=api("GET","/collection/%d/items?models=card&limit=%d&offset=%d"%(COLLECTION_ID,limit,offset))
        chunk=res.get("data",[])
        out.extend(chunk)
        total=res.get("total")
        if not chunk or len(chunk)<limit or (total is not None and offset+len(chunk)>=total):
            break
        offset+=len(chunk)
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    p.add_argument("--restore",metavar="BACKUP_JSON")
    a=p.parse_args()
    if not KEY:
        raise RuntimeError("MB_API_KEY não definida no terminal.")

    collection=api("GET","/collection/%d"%COLLECTION_ID)
    if collection.get("id")!=COLLECTION_ID:
        raise RuntimeError("Coleção inesperada. Cancelado.")
    print("Coleção %s: %s"%(COLLECTION_ID,collection.get("name")))
    cards=all_cards()
    remote={}
    for c in cards:
        obj=api("GET","/card/%s"%c["id"])
        if obj.get("collection_id")!=COLLECTION_ID:
            raise RuntimeError("Card %s mudou de coleção"%c["id"])
        remote[obj["id"]]=obj

    changes=[]
    if a.restore:
        with open(a.restore,encoding="utf-8") as stream:
            old=json.load(stream)
        if old.get("collection_id")!=COLLECTION_ID:
            raise RuntimeError("Backup de outra coleção")
        for record in old["cards"]:
            cid=record["id"]
            if cid not in remote:
                raise RuntimeError("Card %s não pertence mais à coleção 6"%cid)
            desired=record["name"]
            if remote[cid]["name"]!=desired:
                changes.append((cid,remote[cid]["name"],desired))
    else:
        for cid,card in remote.items():
            name=card["name"]
            if PREFIX.search(name):
                # Remove somente a marca da empresa no prefixo.
                desired=PREFIX.sub("CS | ",name,count=1)
                changes.append((cid,name,desired))

    target_names={cid:obj["name"] for cid,obj in remote.items()}
    for cid,_,new in changes:
        target_names[cid]=new
    if len(set(target_names.values()))!=len(target_names):
        raise RuntimeError("Renomeação produziria nomes duplicados na coleção; cancelado.")

    print("Perguntas encontradas:",len(cards))
    print("Perguntas a renomear:",len(changes))
    for cid,old,new in sorted(changes):
        print("%s: %s => %s"%(cid,old,new))
    if not a.apply:
        print("SIMULAÇÃO: nenhuma alteração. Use --apply.")
        return
    if not changes:
        print("Tudo já está padronizado. Nenhuma alteração.")
        return
    backup_name="backup_nomes_colecao6_"+dt.datetime.now().strftime("%Y%m%d_%H%M%S")+".json"
    backup={"collection_id":COLLECTION_ID,"collection_name":collection.get("name"),
            "cards":[{"id":cid,"name":obj["name"]} for cid,obj in sorted(remote.items())]}
    with open(backup_name,"w",encoding="utf-8") as file:
        json.dump(backup,file,ensure_ascii=False,indent=2)
    print("Backup local:",os.path.abspath(backup_name))
    for cid,old,new in sorted(changes):
        api("PUT","/card/%s"%cid,{"name":new})
        actual=api("GET","/card/%s"%cid)
        if actual.get("name")!=new:
            raise RuntimeError("Renomeado sem confirmação: %s"%cid)
        print("OK",cid,new)
    print("Renomeação concluída. Atualize a coleção no navegador.")

if __name__=="__main__":
    try:
        main()
    except (RuntimeError,OSError,ValueError,KeyError) as e:
        sys.exit("ERRO: %s"%e)
