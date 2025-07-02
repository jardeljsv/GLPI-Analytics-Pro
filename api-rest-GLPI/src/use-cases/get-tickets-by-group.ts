
import { knex } from "@/database/knex-config";

export async function getTicketsByGroup() {
  const ticketsByGroup = await knex("glpi_tickets_users as tu")
    .select("g.name as groupName")
    .count("tu.tickets_id as ticketsCount")
    .innerJoin("glpi_groups_tickets as gt", "tu.tickets_id", "gt.tickets_id")
    .innerJoin("glpi_groups as g", "gt.groups_id", "g.id")
    .where("tu.type", 2) // type 2 = Assigned to (technician or group)
    .groupBy("g.name")
    .orderBy("ticketsCount", "desc");

  return {
    ticketsByGroup,
  };
}
