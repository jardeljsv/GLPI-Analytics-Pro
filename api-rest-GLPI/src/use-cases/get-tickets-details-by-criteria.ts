
import { knex } from "@/database/knex-config";

interface GetTicketsDetailsByCriteriaParams {
  criteriaType: 'status' | 'priority';
  criteriaValue: string;
  period?: 'today' | 'week' | 'month';
}

export async function getTicketsDetailsByCriteria({ criteriaType, criteriaValue, period = 'month' }: GetTicketsDetailsByCriteriaParams) {

  const applyDateFilter = (query: any) => {
    if (period === 'today') {
      return query.whereRaw('DATE(date) = CURDATE()');
    }
    if (period === 'week') {
      return query.whereRaw('date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)');
    }
    return query.whereRaw('date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)');
  };

  const query = knex("glpi_tickets as t")
    .select(
      "t.id",
      "t.name as title",
      knex.raw(`
        CASE 
          WHEN t.status = 1 THEN 'Novo'
          WHEN t.status = 2 THEN 'Em Atendimento (atribuído)'
          WHEN t.status = 3 THEN 'Em Atendimento (planejado)'
          WHEN t.status = 4 THEN 'Pendente'
          WHEN t.status = 5 THEN 'Solucionado'
          WHEN t.status = 6 THEN 'Fechado'
        END AS status
      `),
      knex.raw(`
        CASE 
          WHEN t.priority = 6 THEN 'Crítica'
          WHEN t.priority = 1 THEN 'Muito baixa'
          WHEN t.priority = 2 THEN 'Baixa'
          WHEN t.priority = 3 THEN 'Média'
          WHEN t.priority = 4 THEN 'Alta'
          WHEN t.priority = 5 THEN 'Muito alta'
        END AS priority
      `),
      "t.date_creation"
    )
    .orderBy("t.date_creation", "desc");

  applyDateFilter(query);

  if (criteriaType === 'status') {
    query.where(knex.raw(`
      CASE 
        WHEN t.status = 1 THEN 'Novo'
        WHEN t.status = 2 THEN 'Em Atendimento (atribuído)'
        WHEN t.status = 3 THEN 'Em Atendimento (planejado)'
        WHEN t.status = 4 THEN 'Pendente'
        WHEN t.status = 5 THEN 'Solucionado'
        WHEN t.status = 6 THEN 'Fechado'
      END
    `), criteriaValue);
  } else if (criteriaType === 'priority') {
    query.where(knex.raw(`
      CASE 
        WHEN t.priority = 6 THEN 'Crítica'
        WHEN t.priority = 1 THEN 'Muito baixa'
        WHEN t.priority = 2 THEN 'Baixa'
        WHEN t.priority = 3 THEN 'Média'
        WHEN t.priority = 4 THEN 'Alta'
        WHEN t.priority = 5 THEN 'Muito alta'
      END
    `), criteriaValue);
  }

  const tickets = await query;
  return { tickets };
}
