#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostico complementar de inventario GLPI Cadmus (somente SELECT).
Mapeia entidade, estado, tipo, localizacao, usuario, inventario, financeiro e categorias.
Nao registra credenciais, nao altera GLPI ou Metabase.
Uso: python3 diagnostico_ativos_cadmus_etapa2.py
"""
import datetime, os, subprocess, sys
DB=os.getenv("GLPI_DB","glpidb")
MYSQL_USER=os.getenv("MYSQL_USER","root")
MYSQL_HOST=os.getenv("MYSQL_HOST","")
TYPES={
 "Computadores":"glpi_computers",
 "Monitores":"glpi_monitors",
 "Periféricos":"glpi_peripherals",
 "Telefones":"glpi_phones",
 "Impressoras":"glpi_printers"
}
def sql(query):
    cmd=["mariadb","--batch","--raw","--default-character-set=utf8mb4","-u",MYSQL_USER]
    if MYSQL_HOST: cmd+=["-h",MYSQL_HOST]
    cmd += [DB,"-e",query]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    if p.returncode: raise RuntimeError(p.stderr.strip()[:700])
    lines=p.stdout.splitlines()
    return [line.split("\t") for line in lines[1:]]
def section(name, query, limit=35):
    print("\n###",name)
    try:
        rows=sql(query)
        if not rows: print("(sem registros)")
        for r in rows[:limit]: print(" | ".join(str(v)[:120] for v in r))
        if len(rows)>limit: print("... +%d registros"% (len(rows)-limit))
    except Exception as e: print("ERRO:",e)
def main():
    print("DIAGNOSTICO DE INVENTARIO CADMUS - ETAPA 2")
    print("Database:",DB,"Em:",datetime.datetime.now().isoformat())
    section("ENTIDADES RELEVANTES",
        "SELECT id, entities_id, LEFT(completename,120) FROM glpi_entities WHERE id IN (83,137,138,140,160,161) OR entities_id IN (83,137) ORDER BY id LIMIT 50")
    for label,table in TYPES.items():
        cols={r[0] for r in sql("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='%s'"%table)}
        where=" WHERE is_deleted=0" if "is_deleted" in cols else ""
        conditions=["1=1"]
        if "is_deleted" in cols: conditions.append("a.is_deleted=0")
        if "is_template" in cols: conditions.append("a.is_template=0")
        filter_sql=" AND ".join(conditions)
        section(label+" POR ENTIDADE",
           "SELECT a.entities_id,COALESCE(LEFT(e.completename,90),'Sem entidade'),COUNT(*) "
           "FROM %s a LEFT JOIN glpi_entities e ON e.id=a.entities_id WHERE %s "
           "GROUP BY a.entities_id,e.completename ORDER BY COUNT(*) DESC LIMIT 30"%(table,filter_sql))
        if "states_id" in cols:
            section(label+" POR ESTADO",
                "SELECT a.states_id,COALESCE(s.completename,s.name,'Sem estado'),COUNT(*) "
                "FROM %s a LEFT JOIN glpi_states s ON s.id=a.states_id WHERE %s "
                "GROUP BY a.states_id,s.completename,s.name ORDER BY COUNT(*) DESC LIMIT 25"%(table,filter_sql))
        if "users_id" in cols:
            section(label+" VINCULO DE USUARIO",
                "SELECT CASE WHEN a.users_id IS NULL OR a.users_id=0 THEN 'Sem usuario' ELSE 'Com usuario' END,COUNT(*) "
                "FROM %s a WHERE %s GROUP BY 1"%(table,filter_sql))
        if "locations_id" in cols:
            section(label+" TOP LOCALIZACOES",
                "SELECT a.locations_id,COALESCE(LEFT(l.completename,90),'Nao informado'),"
                "COALESCE(l.state,''),COUNT(*) FROM %s a "
                "LEFT JOIN glpi_locations l ON l.id=a.locations_id WHERE %s "
                "GROUP BY a.locations_id,l.completename,l.state ORDER BY COUNT(*) DESC LIMIT 15"%(table,filter_sql),15)
    section("COMPUTADORES INVENTARIO / ULTIMA ATUALIZACAO",
      "SELECT CASE WHEN last_inventory_update IS NULL THEN 'Nunca inventariado' "
      "WHEN last_inventory_update < NOW()-INTERVAL 90 DAY THEN 'Mais de 90 dias' "
      "WHEN last_inventory_update < NOW()-INTERVAL 30 DAY THEN '31 a 90 dias' "
      "ELSE 'Ate 30 dias' END AS faixa,COUNT(*) "
      "FROM glpi_computers WHERE is_deleted=0 AND is_template=0 GROUP BY faixa")
    section("COMPUTADORES POR TIPO",
      "SELECT a.computertypes_id,COALESCE(ct.name,'Sem tipo'),COUNT(*) "
      "FROM glpi_computers a LEFT JOIN glpi_computertypes ct ON ct.id=a.computertypes_id "
      "WHERE a.is_deleted=0 AND a.is_template=0 GROUP BY a.computertypes_id,ct.name ORDER BY COUNT(*) DESC LIMIT 20")
    section("COMPUTADORES POR MODELO",
      "SELECT a.computermodels_id,COALESCE(cm.name,'Sem modelo'),COUNT(*) "
      "FROM glpi_computers a LEFT JOIN glpi_computermodels cm ON cm.id=a.computermodels_id "
      "WHERE a.is_deleted=0 AND a.is_template=0 GROUP BY a.computermodels_id,cm.name ORDER BY COUNT(*) DESC LIMIT 25")
    section("INFOCOM POR CLASSE DE ATIVO",
      "SELECT itemtype,entities_id,COUNT(*),SUM(buy_date IS NOT NULL),SUM(use_date IS NOT NULL),"
      "SUM(warranty_date IS NOT NULL),SUM(decommission_date IS NOT NULL) FROM glpi_infocoms "
      "GROUP BY itemtype,entities_id ORDER BY COUNT(*) DESC LIMIT 35")
    section("INFOCOM DATAS GARANTIA",
      "SELECT CASE WHEN warranty_date IS NOT NULL THEN 'Data de garantia' "
      "WHEN buy_date IS NOT NULL AND warranty_duration>0 THEN 'Compra + duracao' "
      "ELSE 'Sem vencimento calculavel' END,COUNT(*) FROM glpi_infocoms GROUP BY 1")
    section("CONTRATOS (SEM DADOS SENSIVEIS)",
      "SELECT id,entities_id,LEFT(name,80),begin_date,duration,is_deleted "
      "FROM glpi_contracts ORDER BY id")
    section("CHAMADOS DAS CATEGORIAS DE MOVIMENTACAO (ENTIDADES 138,140,160,161)",
      "SELECT t.entities_id,t.itilcategories_id,LEFT(c.completename,100),COUNT(*),"
      "SUM(t.status IN(5,6)) FROM glpi_tickets t "
      "JOIN glpi_itilcategories c ON c.id=t.itilcategories_id "
      "WHERE t.is_deleted=0 AND t.entities_id IN (138,140,160,161) "
      "AND (LOWER(c.completename) LIKE '%onboard%' OR LOWER(c.completename) LIKE '%offboard%' "
      "OR LOWER(c.completename) LIKE '%devolu%' OR LOWER(c.completename) LIKE '%troca de ativo%' "
      "OR LOWER(c.completename) LIKE '%envio de ativo%') "
      "GROUP BY t.entities_id,t.itilcategories_id,c.completename ORDER BY COUNT(*) DESC LIMIT 50")
    print("\nProximo passo: validar quais estados representam disponivel, descartado, pendente e locado.")
if __name__=="__main__":
    try: main()
    except Exception as e: sys.exit("ERRO: "+str(e))
