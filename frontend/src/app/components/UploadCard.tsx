"use client";

import axios from "axios";
import { useState } from "react";

export default function UploadCard({ setResult }: any) {

  const [file, setFile] = useState<File | null>(null);

  const handleUpload = async () => {

    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await axios.post(
        "http://127.0.0.1:8000/upload",
        formData
      );

      setResult(res.data);

    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="bg-gray-900 p-4 rounded-2xl shadow-lg">

      <h2 className="text-xl mb-4">Upload Financial Document</h2>

      <input
        type="file"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
      />

      <button
        onClick={handleUpload}
        className="mt-4 bg-blue-600 px-4 py-2 rounded-xl"
      >
        Analyze
      </button>

    </div>
  );
}