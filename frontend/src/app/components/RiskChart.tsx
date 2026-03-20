"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import { motion } from "framer-motion";
import AnimatedCard from "./AnimatedCard";

export default function RiskChart({ data }: any) {

  // 🔥 CONVERT OBJECT → ARRAY
  const chartData = data
    ? Object.keys(data).map((key) => ({
        feature: key,
        value: data[key],
      }))
    : [];

  return (
    <AnimatedCard>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.7 }}
        className="bg-gray-900 p-4 rounded-2xl col-span-2"
      >
        <h2 className="text-xl mb-4">Risk Factor Analysis</h2>

        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={chartData}>
            <XAxis dataKey="feature" stroke="#ccc" />
            <YAxis stroke="#ccc" />
            <Tooltip />
            <Bar dataKey="value" fill="#ef4444" />
          </BarChart>
        </ResponsiveContainer>

      </motion.div>
    </AnimatedCard>
  );
}