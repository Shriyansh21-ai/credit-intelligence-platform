"use client";

import AnimatedCard from "./AnimatedCard";

export default function DecisionCard({ decision }: { decision: string }) {

  const color =
    decision === "Approved"
      ? "text-green-400"
      : decision === "Rejected"
      ? "text-red-400"
      : "text-yellow-400";

  return (
    <AnimatedCard>
      <div className="bg-gray-900 p-4 rounded-2xl">

        <h2 className="text-xl mb-4">Decision</h2>

        <div className={`text-2xl font-bold ${color}`}>
          {decision}
        </div>

      </div>
    </AnimatedCard>
  );
}