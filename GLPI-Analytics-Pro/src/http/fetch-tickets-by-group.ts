
import { api } from "./api";

export interface TicketsByGroupData {
  ticketsByGroup: { groupName: string; ticketsCount: number }[];
}

export async function fetchTicketsByGroup(): Promise<TicketsByGroupData> {
  const response = await api.get("/tickets/groups");
  return response.data as TicketsByGroupData;
}
