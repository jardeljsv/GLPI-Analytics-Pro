import { Card, CardHeader, CardContent, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectTrigger,
  SelectValue,
  SelectItem,
} from '@/components/ui/select';
import { useState, useEffect, useCallback } from 'react';
import { BarChart, PieChart, LineChart } from 'recharts';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import { fetchAnalyticsOverview, AnalyticsData } from '@/http/fetch-analytics-overview';
import { fetchTechnicianAnalytics, TechnicianAnalyticsData } from '@/http/fetch-analytics-technician';
import { fetchRequesterAnalytics, RequesterAnalyticsData } from '@/http/fetch-analytics-requester';
import { fetchTicketsAnalytics, TicketsAnalyticsData } from '@/http/fetch-analytics-tickets';
import { Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, Pie, Cell, Line } from 'recharts';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Modal } from '@/components/Modal';
import { api } from '@/http/api';
import { exportToCsv } from '@/utils/exportToCsv';

export const Analytics = () => {
  const [selectedTab, setSelectedTab] = useState('overview');
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [technicianData, setTechnicianData] = useState<TechnicianAnalyticsData | null>(null);
  const [requesterData, setRequesterData] = useState<RequesterAnalyticsData | null>(null);
  const [ticketsData, setTicketsData] = useState<TicketsAnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState('month');

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalTitle, setModalTitle] = useState('');
  const [modalContent, setModalContent] = useState<any[]>([]);
  const [isModalLoading, setIsModalLoading] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      if (selectedTab === 'overview') {
        const data = await fetchAnalyticsOverview(period);
        setAnalyticsData(data);
      } else if (selectedTab === 'technicians') {
        const data = await fetchTechnicianAnalytics();
        setTechnicianData(data);
      } else if (selectedTab === 'requesters') {
        const data = await fetchRequesterAnalytics();
        setRequesterData(data);
      } else if (selectedTab === 'tickets') {
        const data = await fetchTicketsAnalytics();
        setTicketsData(data);
      }
    } catch (err) {
      setError('Falha ao carregar os dados.');
    } finally {
      setLoading(false);
    }
  }, [selectedTab, period]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleExport = () => {
    let dataToExport: any[] = [];
    let fileName = 'relatorio';

    switch (selectedTab) {
      case 'overview':
        if (!analyticsData) return;
        dataToExport = [
          ...analyticsData.ticketsByStatus.map(d => ({ ...d, tipo: 'Status' })),
          ...analyticsData.ticketsByPriority.map(d => ({ ...d, tipo: 'Prioridade' })),
        ];
        fileName = 'visao_geral';
        break;
      case 'technicians':
        if (!technicianData) return;
        dataToExport = [
          ...technicianData.ticketsAmountTechnician.map(d => ({ ...d, tipo: 'Atribuídos' })),
          ...technicianData.ticketsAmountTechnicianSolution.map(d => ({ ...d, tipo: 'Solucionados' })),
        ];
        fileName = 'tecnicos';
        break;
      case 'requesters':
        if (!requesterData) return;
        dataToExport = requesterData.ticketsByRequester;
        fileName = 'requerentes';
        break;
      case 'tickets':
        if (!ticketsData) return;
        dataToExport = ticketsData.categories_last_tickets;
        fileName = 'ultimos_chamados';
        break;
    }

    if (dataToExport.length > 0) {
      exportToCsv(dataToExport, fileName);
    }
  };

  const handleChartClick = async (criteriaType: 'status' | 'priority', criteriaValue: string) => {
    setModalTitle(`Detalhes para: ${criteriaValue}`);
    setIsModalOpen(true);
    setIsModalLoading(true);

    try {
      const response = await api.get("/tickets/details", { params: { criteriaType, criteriaValue, period } });
      setModalContent(response.data.tickets);
    } catch (error) {
      console.error("Failed to fetch details", error);
      setModalContent([]);
    } finally {
      setIsModalLoading(false);
    }
  };

  const COLORS = [
    'hsl(var(--chart-1))',
    'hsl(var(--chart-2))',
    'hsl(var(--chart-3))',
    'hsl(var(--chart-4))',
    'hsl(var(--chart-5))',
  ];

  const getStatusName = (status: number) => {
    const statusMap: { [key: number]: string } = {
      1: 'Novo',
      2: 'Em Atendimento (atribuído)',
      3: 'Em Atendimento (planejado)',
      4: 'Pendente',
      5: 'Solucionado',
      6: 'Fechado',
    };
    return statusMap[status] || 'Desconhecido';
  };

  return (
    <section className="w-full space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-4xl font-bold">Análises e Gráficos</h1>
        <Button variant="outline" onClick={handleExport}>Exportar Relatórios</Button>
      </div>

      {/* Filtros */}
      <Card className="p-4 card-shadow">
        <div className="flex justify-center gap-4">
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-56">
              <SelectValue placeholder="Selecione o Período" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="today">Hoje</SelectItem>
              <SelectItem value="week">Última Semana</SelectItem>
              <SelectItem value="month">Último Mês</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={loadData}>Filtrar</Button>
        </div>
      </Card>

      {/* Tabs e Conteúdo */}
      <Tabs value={selectedTab} onValueChange={setSelectedTab}>
        <TabsList className="flex justify-center space-x-4">
          <TabsTrigger value="overview" className="tabs-trigger-transition">Visão Geral</TabsTrigger>
          <TabsTrigger value="technicians" className="tabs-trigger-transition">Técnicos</TabsTrigger>
          <TabsTrigger value="requesters" className="tabs-trigger-transition">Requerentes</TabsTrigger>
          <TabsTrigger value="tickets" className="tabs-trigger-transition">Chamados</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          {loading && <p>Carregando...</p>}
          {error && <p className="text-red-500">{error}</p>}
          {analyticsData && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <Card className="card-shadow">
                <CardHeader>
                  <h2 className="font-semibold text-lg">Chamados por Status</h2>
                </CardHeader>
                <CardContent>
                  <ChartContainer className="w-full h-64">
                    <BarChart data={analyticsData.ticketsByStatus} onClick={(data) => handleChartClick('status', data.activePayload[0].payload.name)}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Legend />
                      <Bar dataKey="value" fill="hsl(var(--chart-1))" />
                    </BarChart>
                  </ChartContainer>
                </CardContent>
              </Card>
              <Card className="card-shadow">
                <CardHeader>
                  <h2 className="font-semibold text-lg">Chamados por Urgência</h2>
                </CardHeader>
                <CardContent>
                  <ChartContainer className="w-full h-64">
                    <PieChart>
                      <Pie data={analyticsData.ticketsByPriority} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} fill="hsl(var(--chart-2))" label onClick={(data) => handleChartClick('priority', data.name)}>
                        {analyticsData.ticketsByPriority.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Legend />
                    </PieChart>
                  </ChartContainer>
                </CardContent>
              </Card>
              <Card className="card-shadow">
                <CardHeader>
                  <h2 className="font-semibold text-lg">Tendências Mensais</h2>
                </CardHeader>
                <CardContent>
                  <ChartContainer className="w-full h-64">
                    <LineChart data={analyticsData.ticketsTrend}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Legend />
                      <Line type="monotone" dataKey="value" stroke="hsl(var(--chart-3))" />
                    </LineChart>
                  </ChartContainer>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        <TabsContent value="technicians">
          {loading && <p>Carregando...</p>}
          {error && <p className="text-red-500">{error}</p>}
          {technicianData && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card className="card-shadow">
                <CardHeader>
                  <h2 className="font-semibold text-lg">Chamados Atribuídos por Técnico</h2>
                </CardHeader>
                <CardContent>
                  <ChartContainer className="w-full h-96">
                    <BarChart data={technicianData.ticketsAmountTechnician} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis dataKey="technician" type="category" width={150} />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Legend />
                      <Bar dataKey="quantity" fill="hsl(var(--chart-4))" />
                    </BarChart>
                  </ChartContainer>
                </CardContent>
              </Card>
              <Card className="card-shadow">
                <CardHeader>
                  <h2 className="font-semibold text-lg">Chamados Solucionados por Técnico</h2>
                </CardHeader>
                <CardContent>
                  <ChartContainer className="w-full h-96">
                    <BarChart data={technicianData.ticketsAmountTechnicianSolution} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis dataKey="technician" type="category" width={150} />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Legend />
                      <Bar dataKey="count" fill="hsl(var(--chart-5))" />
                    </BarChart>
                  </ChartContainer>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        <TabsContent value="requesters">
          {loading && <p>Carregando...</p>}
          {error && <p className="text-red-500">{error}</p>}
          {requesterData && (
            <Card className="card-shadow">
              <CardHeader>
                <h2 className="font-bold text-xl">Top 15 Requerentes por Chamados Abertos</h2>
              </CardHeader>
              <CardContent>
                <ChartContainer className="w-full h-[500px]">
                  <BarChart data={requesterData.ticketsByRequester} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis dataKey="requesterName" type="category" width={150} />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Legend />
                    <Bar dataKey="ticketsCount" fill="hsl(var(--chart-1))" />
                  </BarChart>
                </ChartContainer>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="tickets">
          {loading && <p>Carregando...</p>}
          {error && <p className="text-red-500">{error}</p>}
          {ticketsData && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card className="card-shadow">
                <CardHeader>
                  <CardTitle>Chamados por Categoria</CardTitle>
                </CardHeader>
                <CardContent>
                  <ChartContainer className="w-full h-80">
                    <PieChart>
                      <Pie data={ticketsData.categories_amount} dataKey="tickets_amount" nameKey="category" cx="50%" cy="50%" outerRadius={100} fill="hsl(var(--chart-2))" label>
                        {ticketsData.categories_amount.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Legend />
                    </PieChart>
                  </ChartContainer>
                </CardContent>
              </Card>
              <Card className="card-shadow">
                <CardHeader>
                  <CardTitle>Últimos 10 Chamados Registrados</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>ID</TableHead>
                        <TableHead>Nome</TableHead>
                        <TableHead>Categoria</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {ticketsData.categories_last_tickets.map((ticket) => (
                        <TableRow key={ticket.id}>
                          <TableCell>{ticket.id}</TableCell>
                          <TableCell>{ticket.name}</TableCell>
                          <TableCell>{ticket.category}</TableCell>
                          <TableCell>{getStatusName(ticket.status)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>
      </Tabs>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={modalTitle}>
        {isModalLoading ? <p>Carregando detalhes...</p> : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Título</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Prioridade</TableHead>
                <TableHead>Criação</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {modalContent.map((ticket) => (
                <TableRow key={ticket.id}>
                  <TableCell>{ticket.id}</TableCell>
                  <TableCell>{ticket.title}</TableCell>
                  <TableCell>{ticket.status}</TableCell>
                  <TableCell>{ticket.priority}</TableCell>
                  <TableCell>{new Date(ticket.date_creation).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Modal>
    </section>
  );
};