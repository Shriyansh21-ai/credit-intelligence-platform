"use client";

import { useState } from "react";
import { apiFetch } from "../../../utils/api";

export default function DownloadReport({ data }: any) {

  const [loading, setLoading] = useState(false);

  const downloadPDF = async () => {

    if (!data) {
      alert("No data available to generate report");
      return;
    }

    setLoading(true);

    try {
      const res = await apiFetch(
        "http://127.0.0.1:8000/download-report",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(data)
        }
      );

      if (!res.ok) {
        throw new Error("Failed to generate PDF");
      }

      // 📄 Convert response to blob
      const blob = await res.blob();

      // 🔗 Create download link
      const url = window.URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = "credit_report.pdf";
      document.body.appendChild(a);
      a.click();

      // 🧹 Cleanup
      a.remove();
      window.URL.revokeObjectURL(url);

    } catch (err) {
      console.error(err);
      alert("Download failed");
    }

    setLoading(false);
  };

  return (
    <div className="bg-gray-900 p-5 rounded-2xl">

      <h2 className="text-xl mb-3">Download Report</h2>

      <button
        onClick={downloadPDF}
        disabled={loading}
        className={`px-4 py-2 rounded ${
          loading ? "bg-gray-500" : "bg-green-600 hover:bg-green-700"
        }`}
      >
        {loading ? "Generating..." : "Download PDF"}
      </button>

    </div>
  );
}