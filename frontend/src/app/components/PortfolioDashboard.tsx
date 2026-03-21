"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer
} from "recharts";

export default function PortfolioDashboard({ data }: any) {

  if (!data) return null;

  const pieData = [
    { name: "High Risk", value: data.high_risk_companies },
    { name: "Others", value: data.total_companies - data.high_risk_companies }
  ];

  return (
    <div className="bg-gray-900 p-5 rounded-2xl">

      <h2 className="text-xl mb-4">Portfolio Risk Overview</h2>

      <p>Average Risk: <b>{data.average_risk.toFixed(2)}</b></p>

      <ResponsiveContainer width="100%" height={250}>
        <PieChart>
          <Pie data={pieData} dataKey="value" outerRadius={80}>
            {pieData.map((_, index) => (
              <Cell key={index} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>

    </div>
  );
}