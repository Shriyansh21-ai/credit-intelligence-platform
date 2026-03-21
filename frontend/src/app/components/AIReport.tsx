"use client";

import AnimatedCard from "./AnimatedCard";

export default function AIReport({ data }: any) {

  if (!data) return null;

  return (
    <AnimatedCard>
      <div className="bg-gray-900 p-5 rounded-2xl col-span-3">

        <h2 className="text-xl mb-4">AI Credit Report</h2>

        <p className="mb-3 text-gray-300">
          {data.risk_summary}
        </p>

        <div className="grid grid-cols-2 gap-4 text-sm">

          <div>
            <h3 className="text-green-400 mb-1">Strengths</h3>
            <ul>
              {data.strengths?.map((s: string, i: number) => (
                <li key={i}>• {s}</li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-red-400 mb-1">Weaknesses</h3>
            <ul>
              {data.weaknesses?.map((w: string, i: number) => (
                <li key={i}>• {w}</li>
              ))}
            </ul>
          </div>

        </div>

        <div className="mt-4 flex justify-between items-center">
          <span>Decision: <b>{data.decision}</b></span>
          <span>Confidence: <b>{data.confidence}%</b></span>
        </div>

      </div>
    </AnimatedCard>
  );
}