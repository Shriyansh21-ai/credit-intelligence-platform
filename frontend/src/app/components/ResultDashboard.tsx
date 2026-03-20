"use client";

import { motion } from "framer-motion";
import RiskGauge from "./RiskGauge";
import RiskChart from "./RiskChart";

export default function ResultDashboard({ data }: any) {

  if (!data) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-6 grid gap-6"
    >

      {/* 🔥 TOP SECTION */}
      <div className="grid md:grid-cols-2 gap-6">

        {/* Risk Score */}
        <div className="bg-gray-900 p-6 rounded-2xl shadow-lg">
          <h3 className="text-lg mb-4">Risk Score</h3>
          <RiskGauge score={data.risk_score} />
          <p className="mt-2 text-gray-400 text-sm">
            AI-calculated credit risk
          </p>
        </div>

        {/* Key Metrics */}
        <div className="bg-gray-900 p-6 rounded-2xl shadow-lg">
          <h3 className="text-lg mb-4">Key Metrics</h3>

          <div className="space-y-3 text-sm">
            <p>💰 Income: ₹{data.income}</p>
            <p>📉 Debt: ₹{data.debt}</p>
            <p>⚠ Fraud Risk: {(data.fraud_risk * 100).toFixed(1)}%</p>
          </div>
        </div>

      </div>

      {/* 📊 CHART */}
      <div className="bg-gray-900 p-6 rounded-2xl shadow-lg">
        <h3 className="text-lg mb-4">Risk Factor Analysis</h3>
        <RiskChart factors={data.factors} />
      </div>

      {/* 🤖 AI INSIGHTS */}
      <div className="bg-gray-900 p-6 rounded-2xl shadow-lg">
        <h3 className="text-lg mb-4">AI Insights</h3>

        <ul className="text-sm text-gray-300 space-y-2">
          <li>• High debt ratio increases risk</li>
          <li>• Stable income reduces risk</li>
          <li>• Monitor transaction anomalies</li>
        </ul>
      </div>

    </motion.div>
  );
}