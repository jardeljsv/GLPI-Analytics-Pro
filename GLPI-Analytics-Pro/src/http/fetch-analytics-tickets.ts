
import { api } from "./api";

export interface TicketsAnalyticsData {
  categories_amount: { category: string; tickets_amount: number }[];
  categories_last_tickets: {
    id: number;
    name: string;
    status: number;
    date: string;
    category: string;
  }[];
}

export async function fetchTicketsAnalytics(): Promise<TicketsAnalyticsData> {
  const response = await api.get("/tickets/categories");
  return response.data;
}
