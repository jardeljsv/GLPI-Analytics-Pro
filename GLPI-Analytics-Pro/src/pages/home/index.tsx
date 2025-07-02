// import { dataTicketsHomeResponse } from "@/data/ticketsData";

import {
  CardFlash,
  CardIcon,
  CardInformations,
  CardRoot,
  CardWrapper,
} from "@/components/Card/Card";

import { ArrowsLeftRight, Timer, UsersThree } from "phosphor-react";

import { Header } from "./header";

import {
  levelPriorityIcons,
  levelPriorityStyle,
  levelTypeIcons,
  levelTypeStyle,
  priorityTranslations,
  typeTranslations,
} from "./definitions";
import { useTicketsPending, useTicketsSummary } from "./api/tickets.queries";
import { useEffect, useState } from "react";
import { SpinnerBall } from "@phosphor-icons/react";
import { BarChartsTickets } from "./components/BarCharts";
import { fetchTicketsByGroup } from "@/http/fetch-tickets-by-group";
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

export const Home = () => {
  const { data: statusData, isLoading: isLoadingStatus } = useTicketsPending();
  const { data: summaryData } = useTicketsSummary();
  const [ticketsByGroup, setTicketsByGroup] = useState<{ groupName: string; ticketsCount: number }[]>([]);

  const COLORS = [
    'hsl(var(--chart-1))',
    'hsl(var(--chart-2))',
    'hsl(var(--chart-3))',
    'hsl(var(--chart-4))',
    'hsl(var(--chart-5))',
  ];

  useEffect(() => {
    const loadGroupData = async () => {
      try {
        const data = await fetchTicketsByGroup();
        setTicketsByGroup(data.ticketsByGroup);
      } catch (error) {
        console.error("Failed to fetch group data", error);
      }
    };
    loadGroupData();
  }, []);

  const [statusTickets, setStatusTickets] = useState(statusData);

  useEffect(() => {
    setStatusTickets(statusData);
  }, [statusData]);

  if (isLoadingStatus || !statusTickets) {
    return (
      <div className="w-full flex flex-col gap-2 items-center justify-center">
        <SpinnerBall className="text-zinc-700 animate-spin size-10" />
        <span className="text-xs font-light">Loading...</span>
      </div>
    );
  }

  const totalGroups = ticketsByGroup.length;

  return (
    <main className="flex flex-col w-full h-[max-content] h-full">
      {statusTickets && (
        <>
          <Header name="Dashboard" />

          <CardRoot>
            {/* style default: but add style custom */}
            <CardWrapper>
              {statusTickets.meta.type.map((row) => (
                <CardFlash key={row.name}>
                  <CardIcon className={levelTypeStyle[row.name]}>
                    {levelTypeIcons[row.name]}
                  </CardIcon>

                  <CardInformations
                    count={row.count}
                    name={typeTranslations[row.name]}
                  />
                </CardFlash>
              ))}
            </CardWrapper>

            <CardWrapper>
              <CardFlash key={statusTickets.meta.total}>
                <CardIcon className="bg-yellow-400 border border-yellow-600 text-4xl">
                  <Timer />
                </CardIcon>
                <CardInformations
                  className="text-5xl"
                  count={statusTickets.meta.total}
                  name={statusTickets.meta.total > 0 ? "Pendente" : "-"}
                />
              </CardFlash>
            </CardWrapper>

            <CardIcon className="bg-white p-2 teanimate-pulse">
              <ArrowsLeftRight className="text-orange-600 animate-pulse" />
            </CardIcon>

            <CardWrapper className="flex flex-row">
              {statusTickets.meta.priority.map((row) => (
                <CardFlash key={row.name}>
                  <CardIcon className={levelPriorityStyle[row.name]}>
                    {levelPriorityIcons[row.name]}
                  </CardIcon>

                  <CardInformations
                    count={row.count}
                    name={priorityTranslations[row.name]}
                  />
                </CardFlash>
              ))}
            </CardWrapper>

            {totalGroups > 0 && (
              <CardWrapper>
                <CardFlash key="total-groups">
                  <CardIcon className="bg-blue-500 border border-blue-700 text-4xl">
                    <UsersThree />
                  </CardIcon>
                  <CardInformations
                    className="text-5xl"
                    count={totalGroups}
                    name="Total de Grupos"
                  />
                </CardFlash>
              </CardWrapper>
            )}
          </CardRoot>

          <div className="flex flex-col max-h-screen w-full mt-2 flex-1">
            {summaryData && (
              <BarChartsTickets
                categorie={summaryData.meta.categories}
                concludes={summaryData.list}
                delayed={summaryData.meta.delayed}
              />
            )}

            {ticketsByGroup.length > 0 && (
              <div className="mt-4">
                <h2 className="text-xl font-bold mb-2">Chamados por Grupo</h2>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={ticketsByGroup}
                      dataKey="ticketsCount"
                      nameKey="groupName"
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      fill="#8884d8"
                      label
                    >
                      {ticketsByGroup.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </>
      )}
    </main>
  );
}

