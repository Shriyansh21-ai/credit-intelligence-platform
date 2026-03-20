"use client";

import AnimatedCard from "./AnimatedCard";

export default function FraudAlert({ risk }: any) {

  return (
    <AnimatedCard>
      <div className="bg-red-900 p-4 rounded-2xl">

        <h2 className="text-xl mb-4">Fraud Alert</h2>

        <div className="text-red-300 font-bold">
          {JSON.stringify(risk)}
        </div>

      </div>
    </AnimatedCard>
  );
}