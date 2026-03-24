"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { apiFetch } from "../../../utils/api";

export default function RiskHistoryChart() {

  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    const fetchHistory = async () => {
      const res = await apiFetch("http://127.0.0.1:8000/risk-history");
      const result = await res.json();
      setData(result.history);
    };

    fetchHistory();
  }, []);

  return (
    <div className="bg-gray-900 p-5 rounded-2xl">
      <h2 className="text-xl mb-4">Risk Trend</h2>

      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data}>
          <XAxis dataKey="date" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="risk" stroke="#3b82f6" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}