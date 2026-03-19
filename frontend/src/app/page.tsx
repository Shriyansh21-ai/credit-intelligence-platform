"use client";

import { useState } from "react";
import UploadCard from "./components/UploadCard";
import RiskGauge from "./components/RiskGauge";
import DecisionCard from "./components/DecisionCard";
import FraudAlert from "./components/FraudAlert";
import AnalysisPanel from "./components/AnalysisPanel";

export default function Home() {

  const [result, setResult] = useState<any>(null);

  return (
    <main className="min-h-screen bg-gray-950 text-white p-6">

      <h1 className="text-3xl font-bold mb-6">
        AI Credit Intelligence Platform
      </h1>

      <div className="grid grid-cols-3 gap-6">

        <UploadCard setResult={setResult} />

        <RiskGauge score={result?.risk_score || 0} />

        <DecisionCard decision={result?.decision || "Pending"} />

        <FraudAlert risk={result?.fraud_score || "No Data"} />

        <AnalysisPanel analysis={result?.analysis || "Upload file to see analysis"} />

      </div>

    </main>
  );
}