
import { knex } from "@/database/knex-config";

interface GetTicketsAnalyticsParams {
  period?: 'today' | 'week' | 'month';
}

export async function getTicketsAnalytics({ period = 'month' }: GetTicketsAnalyticsParams) {

  const applyDateFilter = (query: any) => {
    if (period === 'today') {
      return query.whereRaw('DATE(date) = CURDATE()');
    }
    if (period === 'week') {
      return query.whereRaw('date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)');
    }
    // Default to 'month'
    return query.whereRaw('date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)');
  };

  const ticketsByStatusQuery = knex("glpi_tickets")
    .select(
      knex.raw(`
        CASE 
          WHEN status = 1 THEN 'Novo'
          WHEN status = 2 THEN 'Em Atendimento (atribuído)'
          WHEN status = 3 THEN 'Em Atendimento (planejado)'
          WHEN status = 4 THEN 'Pendente'
          WHEN status = 5 THEN 'Solucionado'
          WHEN status = 6 THEN 'Fechado'
          ELSE 'Desconhecido'
        END AS name
      `),
      knex.raw("COUNT(*) as value")
    )
    .groupBy("name")
    .orderBy("value", "desc");

  const ticketsByPriorityQuery = knex("glpi_tickets")
    .select(
      knex.raw(`
        CASE 
          WHEN priority = 6 THEN 'Crítica'
          WHEN priority = 1 THEN 'Muito baixa'
          WHEN priority = 2 THEN 'Baixa'
          WHEN priority = 3 THEN 'Média'
          WHEN priority = 4 THEN 'Alta'
          WHEN priority = 5 THEN 'Muito alta'
          ELSE 'Desconhecida'
        END AS name
      `),
      knex.raw("COUNT(*) as value")
    )
    .groupBy("name")
    .orderBy("value", "desc");

  const ticketsTrendQuery = knex("glpi_tickets")
    .select(knex.raw("DATE(date) as date"), knex.raw("COUNT(*) as value"))
    .groupBy("date")
    .orderBy("date", "asc");

  const [ticketsByStatus, ticketsByPriority, ticketsTrend] = await Promise.all([
    applyDateFilter(ticketsByStatusQuery),
    applyDateFilter(ticketsByPriorityQuery),
    applyDateFilter(ticketsTrendQuery),
  ]);

  return {
    ticketsByStatus,
    ticketsByPriority,
    ticketsTrend,
  };
}
