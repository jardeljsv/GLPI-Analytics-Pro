
import { api } from "./api";

export interface AnalyticsData {
  ticketsByStatus: { name: string; value: number }[];
  ticketsByPriority: { name: string; value: number }[];
  ticketsTrend: { date: string; value: number }[];
}

export async function fetchAnalyticsOverview(period?: string): Promise<AnalyticsData> {
  const response = await api.get("/tickets/analytics", { params: { period } });
  return response.data;
}
