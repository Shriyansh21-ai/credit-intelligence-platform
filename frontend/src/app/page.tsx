"use client";

import { useState } from "react";
import UploadCard from "./components/UploadCard";
import RiskGauge from "./components/RiskGauge";
import DecisionCard from "./components/DecisionCard";
import FraudAlert from "./components/FraudAlert";
import TrendChart from "./components/TrendChart";
import ShapChart from "./components/ShapChart";
import AIReport from "./components/AIReport";
import { motion } from "framer-motion";
import AIChat from "./components/AIChat";
import AlertPanel from "./components/AlertPanel";
import SimulationPanel from "./components/SimulationPanel";

export default function Home() {

  const [result, setResult] = useState<any>(null);

  return (
    <main className="min-h-screen bg-gray-950 text-white p-6">

      {/* 🔥 TITLE */}
      <h1 className="text-3xl font-bold mb-6">
        AI Credit Intelligence Platform
      </h1>

      {/* 🚀 UPLOAD SECTION */}
      <div className="mb-6">
        <UploadCard setResult={setResult} />
      </div>

      {/* 🚫 SHOW DASHBOARD ONLY AFTER RESULT */}
      {!result ? (
        <p className="text-gray-400 text-center mt-10">
          Upload a file to generate insights
        </p>
      ) : (

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >

          {/* 🔥 TOP ROW */}
          <div className="grid grid-cols-3 gap-6">

            <RiskGauge score={result.risk_score} />

            <DecisionCard decision={result.decision} />

            <FraudAlert risk={result.fraud_score} />

          </div>

          {/* 📊 MIDDLE ROW */}
          <div className="grid grid-cols-2 gap-6">

            <ShapChart data={result.shap_values} />
            <AlertPanel alerts={result.alerts} />
            <SimulationPanel
               baseData={{
                revenue_growth: 0.1,
                debt_ratio: result.risk_score / 100,
                current_ratio: 1.2,
                roe: 0.15
              }}
            />

            <TrendChart
              data={[
                { time: "Jan", risk: 60 },
                { time: "Feb", risk: 70 },
                { time: "Mar", risk: result.risk_score },
              ]}
            />

          </div>

          {/* 🤖 BOTTOM PANEL */}
          <AIReport data={result.analysis} />
          <AIChat context={result} />

        </motion.div>
      )}

    </main>
  );
}