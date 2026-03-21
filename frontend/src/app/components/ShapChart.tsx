"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

import { motion } from "framer-motion";
import AnimatedCard from "./AnimatedCard";

export default function ShapChart({ data }: any) {

  // 🔥 Convert object → array if needed
  const chartData = data
    ? Object.keys(data).map((key) => ({
        feature: key,
        value: data[key],
      }))
    : [];

  // 🔥 Sort by absolute impact
  const sortedData = [...chartData].sort(
    (a, b) => Math.abs(b.value) - Math.abs(a.value)
  );

  return (
    <AnimatedCard>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="bg-gray-900 p-5 rounded-2xl"
      >
        <h2 className="text-xl mb-4">
          Explainability (SHAP Values)
        </h2>

        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={sortedData} layout="vertical">

            <XAxis
              type="number"
              stroke="#ccc"
              tickFormatter={(v) => v.toFixed(2)}
            />

            <YAxis
              dataKey="feature"
              type="category"
              stroke="#ccc"
              width={120}
            />

            <Tooltip
              formatter={(value: any) =>
              `${value > 0 ? "+" : ""}${Number(value).toFixed(3)}`
            }
            />

            <Bar dataKey="value">

              {sortedData.map((entry, index) => (
                <Cell
                  key={index}
                  fill={entry.value > 0 ? "#22c55e" : "#ef4444"}
                />
              ))}

            </Bar>

          </BarChart>
        </ResponsiveContainer>

        {/* 🔥 LEGEND */}
        <div className="flex gap-4 mt-3 text-sm">
          <span className="text-green-400">▲ Increases Risk</span>
          <span className="text-red-400">▼ Decreases Risk</span>
        </div>

      </motion.div>
    </AnimatedCard>
  );
}