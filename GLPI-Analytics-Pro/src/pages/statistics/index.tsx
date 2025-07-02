import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ChartContainer, ChartTooltipContent } from '@/components/ui/chart';
import { fetchTicketsByGroup, TicketsByGroupData } from '@/http/fetch-tickets-by-group';

export const Statistics = () => {
  const [ticketsByGroup, setTicketsByGroup] = useState<TicketsByGroupData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const data = await fetchTicketsByGroup();
        setTicketsByGroup(data);
      } catch (err) {
        setError('Falha ao carregar os dados de grupos.');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  return (
    <div className="w-full space-y-6">
      {/* Título e Resumo Geral */}
      <header className="text-center space-y-2">
        <h1 className="text-3xl font-bold text-slate-800">
          Estatísticas Gerais
        </h1>
        <p className="text-sm text-gray-500">
          Visualize dados detalhados sobre técnicos, requerentes, chamados e grupos de atendimento.
        </p>
      </header>

      {/* Cards Resumidos */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="card-shadow">
          <CardHeader>
            <CardTitle>Total de Chamados</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-4xl font-bold text-blue-500">1,234</p>
          </CardContent>
        </Card>

        <Card className="card-shadow">
          <CardHeader>
            <CardTitle>Técnicos Ativos</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-4xl font-bold text-green-500">45</p>
          </CardContent>
        </Card>

        <Card className="card-shadow">
          <CardHeader>
            <CardTitle>Média de Resolução</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-4xl font-bold text-yellow-500">3h 15m</p>
          </CardContent>
        </Card>

        <Card className="card-shadow">
          <CardHeader>
            <CardTitle>Chamados Pendentes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-4xl font-bold text-red-500">67</p>
          </CardContent>
        </Card>
      </section>

      {/* Gráficos */}
      <section className="space-y-6">
        {loading && <p>Carregando dados de estatísticas...</p>}
        {error && <p className="text-red-500">{error}</p>}
        {ticketsByGroup && (
          <Card className="card-shadow">
            <CardHeader>
              <CardTitle>Chamados por Grupo de Atendimento</CardTitle>
            </CardHeader>
            <CardContent>
              <ChartContainer className="w-full h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ticketsByGroup.ticketsByGroup} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="groupName" width={150} />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Legend />
                    <Bar dataKey="ticketsCount" fill="hsl(var(--chart-1))" />
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  );
}

