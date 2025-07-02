
import { knex } from "@/database/knex-config";

export async function getTicketsByRequester() {
  const ticketsByRequester = await knex("glpi_tickets_users as tu")
    .select("u.name as requesterName")
    .count("tu.tickets_id as ticketsCount")
    .innerJoin("glpi_users as u", "tu.users_id", "u.id")
    .where("tu.type", 1) // type 1 = Requester
    .groupBy("u.name")
    .orderBy("ticketsCount", "desc")
    .limit(15); // Limita aos top 15 requerentes

  return {
    ticketsByRequester,
  };
}
