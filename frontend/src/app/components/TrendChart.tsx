"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import { motion } from "framer-motion";
import AnimatedCard from "./AnimatedCard";

export default function TrendChart({ data }: any) {

  return (
    <AnimatedCard>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.7 }}
        className="bg-gray-900 p-4 rounded-2xl col-span-2"
      >
        <h2 className="text-xl mb-4">Risk Trend</h2>

        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={data}>
            <XAxis dataKey="time" stroke="#ccc" />
            <YAxis stroke="#ccc" />
            <Tooltip />
            <Line type="monotone" dataKey="risk" stroke="#3b82f6" />
          </LineChart>
        </ResponsiveContainer>

      </motion.div>
    </AnimatedCard>
  );
}