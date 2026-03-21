"use client";

export default function AlertPanel({ alerts }: any) {

  if (!alerts || alerts.length === 0) return null;

  return (
    <div className="bg-gray-900 p-5 rounded-2xl col-span-3">

      <h2 className="text-xl mb-3">Risk Alerts</h2>

      <div className="space-y-2">
        {alerts.map((alert: any, i: number) => (
          <div
            key={i}
            className={`p-3 rounded-lg text-sm ${
              alert.level === "high"
                ? "bg-red-600"
                : alert.level === "medium"
                ? "bg-yellow-600"
                : "bg-blue-600"
            }`}
          >
            {alert.message}
          </div>
        ))}
      </div>

    </div>
  );
}