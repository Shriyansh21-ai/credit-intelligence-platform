export default function RiskGauge({ score }: { score: number }) {
  return (
    <div className="bg-gray-900 p-4 rounded-2xl">
      <h2 className="text-xl mb-4">Risk Score</h2>

      <div className="text-4xl font-bold text-center">{score}</div>

      <div className="mt-4 w-full bg-gray-700 h-3 rounded-full">
        <div
          className="bg-red-500 h-3 rounded-full"
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}