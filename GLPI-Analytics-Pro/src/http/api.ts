export const api = {
  get: async (url: string, params?: any) => {
    console.log(`GET request to: ${url} with params:`, params);
    if (url === "/tickets/analytics") {
      return Promise.resolve({
        data: {
          ticketsByStatus: [
            { name: "New", value: 100 },
            { name: "Pending", value: 50 },
            { name: "Solved", value: 150 },
          ],
          ticketsByPriority: [
            { name: "High", value: 70 },
            { name: "Medium", value: 80 },
            { name: "Low", value: 150 },
          ],
          ticketsTrend: [
            { date: "2024-01-01", value: 10 },
            { date: "2024-01-02", value: 20 },
            { date: "2024-01-03", value: 15 },
          ],
        },
      });
    } else if (url === "/tickets/requesters") {
      return Promise.resolve({
        data: {
          ticketsByRequester: [
            { requesterName: "User A", ticketsCount: 50 },
            { requesterName: "User B", ticketsCount: 30 },
            { requesterName: "User C", ticketsCount: 20 },
          ],
        },
      });
    } else if (url === "/tickets/tickets-technician") {
      return Promise.resolve({
        data: {
          ticketsAmountTechnician: [
            { technician: "Tech 1", quantity: 100 },
            { technician: "Tech 2", quantity: 80 },
          ],
          ticketsAmountTechnicianSolution: [
            { technician: "Tech 1", group: "Group A", count: 90 },
            { technician: "Tech 2", group: "Group B", count: 70 },
          ],
        },
      });
    } else if (url === "/tickets/categories") {
      return Promise.resolve({
        data: {
          categories_amount: [
            { category: "Software", tickets_amount: 120 },
            { category: "Hardware", tickets_amount: 80 },
          ],
          categories_last_tickets: [
            { id: 1, name: "Ticket 1", status: 1, date: "2024-01-01", category: "Software" },
            { id: 2, name: "Ticket 2", status: 2, date: "2024-01-02", category: "Hardware" },
          ],
        },
      });
    } else if (url === "/tickets/details") {
      return Promise.resolve({
        data: {
          tickets: [
            { id: 1, title: "Detail Ticket 1", status: "New", priority: "High", date_creation: "2024-01-01" },
            { id: 2, title: "Detail Ticket 2", status: "Solved", priority: "Low", date_creation: "2024-01-02" },
          ],
        },
      });
    } else if (url === "/tickets/groups") {
      return Promise.resolve({
        data: {
          ticketsByGroup: [
            { groupName: "Group A", ticketsCount: 100 },
            { groupName: "Group B", ticketsCount: 50 },
          ],
        },
      });
    } else if (url === "/settings") {
      return Promise.resolve({
        data: {
          primary_color: "#4EA8DE",
          secondary_color: "#8284FA",
          logo_url: null,
        },
      });
    }
    return Promise.resolve({ data: {} });
  },
  post: async (url: string, data: any) => {
    console.log(`POST request to: ${url} with data:`, data);
    if (url === "/settings/logo") {
      return Promise.resolve({ data: { logo_url: "mock_logo_url" } });
    }
    return Promise.resolve({ data: {} });
  },
};