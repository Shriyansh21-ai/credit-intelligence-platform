export default function AnalysisPanel({ analysis }: { analysis: string }) {

  return (
    <div className="bg-gray-900 p-4 rounded-2xl col-span-3">
      <h2 className="text-xl mb-4">AI Credit Analysis</h2>

      <p className="text-gray-300">
        {analysis}
      </p>
    </div>
  );
}