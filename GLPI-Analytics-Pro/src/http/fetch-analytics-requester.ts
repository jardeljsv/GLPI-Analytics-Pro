
import { api } from "./api";

export interface RequesterAnalyticsData {
  ticketsByRequester: { requesterName: string; ticketsCount: number }[];
}

export async function fetchRequesterAnalytics(): Promise<RequesterAnalyticsData> {
  const response = await api.get("/tickets/requesters");
  return response.data as RequesterAnalyticsData;
}
