
import { api } from "./api";

export interface TechnicianAnalyticsData {
  ticketsAmountTechnician: { technician: string; quantity: number }[];
  ticketsAmountTechnicianSolution: { technician: string; group: string; count: number }[];
}

export async function fetchTechnicianAnalytics(): Promise<TechnicianAnalyticsData> {
  const response = await api.get("/tickets/tickets-technician");
  return response.data;
}
