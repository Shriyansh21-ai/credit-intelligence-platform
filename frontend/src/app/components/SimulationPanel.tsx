"use client";

import { useState } from "react";
import { apiFetch } from "../../../utils/api";

export default function SimulationPanel({ baseData }: any) {

  const [scenario, setScenario] = useState({
    revenue_growth: 0,
    debt_ratio: 0,
    current_ratio: 0,
    roe: 0
  });

  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleChange = (key: string, value: number) => {
    setScenario({ ...scenario, [key]: value });
  };

  const simulate = async () => {
    setLoading(true);

    try {
      const res = await apiFetch("http://127.0.0.1:8000/simulate-risk", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          base_data: baseData,
          scenario: scenario
        })
      });

      const data = await res.json();
      setResult(data);

    } catch (err) {
      console.error(err);
    }

    setLoading(false);
  };

  return (
    <div className="bg-gray-900 p-5 rounded-2xl col-span-3">

      <h2 className="text-xl mb-4">Scenario Simulation</h2>

      {/* 🔧 SLIDERS */}
      <div className="grid grid-cols-2 gap-4 text-sm">

        {Object.keys(scenario).map((key) => (
          <div key={key}>
            <label className="block mb-1">{key}</label>

            <input
              type="range"
              min={-1}
              max={1}
              step={0.05}
              value={scenario[key as keyof typeof scenario]}
              onChange={(e) =>
                handleChange(key, Number(e.target.value))
              }
              className="w-full"
            />

            <p className="text-gray-400 text-xs">
              {scenario[key as keyof typeof scenario]}
            </p>
          </div>
        ))}

      </div>

      {/* 🚀 BUTTON */}
      <button
        onClick={simulate}
        className="mt-4 bg-blue-600 px-4 py-2 rounded"
      >
        {loading ? "Simulating..." : "Run Simulation"}
      </button>

      {/* 📊 RESULT */}
      {result && (
        <div className="mt-4 p-3 bg-gray-800 rounded">

          <p>New Risk Score: <b>{result.risk_score}</b></p>

          <p className="text-sm text-gray-400 mt-2">
            Updated Features:
          </p>

          <pre className="text-xs mt-2">
            {JSON.stringify(result.new_data, null, 2)}
          </pre>

        </div>
      )}

    </div>
  );
}