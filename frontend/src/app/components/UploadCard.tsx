"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import AnimatedCard from "./AnimatedCard";
import axios from "axios";

export default function UploadCard({ setResult }: any) {

  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [progress, setProgress] = useState(0);

  const handleFile = (selectedFile: File) => {
    setFile(selectedFile);
    setError(null);
    setSuccess(false);
    setProgress(0);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(true);
  };

  const handleDragLeave = () => {
    setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  // 🚀 JWT SECURED UPLOAD
  const handleUpload = async () => {

    if (!file) {
      setError("Please upload a file first");
      return;
    }

    const token = localStorage.getItem("token");

    if (!token) {
      setError("Please login first");
      window.location.href = "/auth";
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(false);
    setProgress(0);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await axios.post(
        "http://127.0.0.1:8000/ai-credit-analysis",
        formData,
        {
          headers: {
            "Authorization": `Bearer ${token}`,
          },
          onUploadProgress: (progressEvent) => {
            const percent = Math.round(
              (progressEvent.loaded * 100) /
              (progressEvent.total || 1)
            );
            setProgress(percent);
          }
        }
      );

      setResult(res.data);
      setSuccess(true);

    } catch (err: any) {
      console.error(err);

      if (err.response?.status === 401) {
        setError("Session expired. Please login again.");
        localStorage.removeItem("token");
        window.location.href = "/auth";
      } else {
        setError("Upload failed. Try again.");
      }
    }

    setLoading(false);
  };

  return (
    <AnimatedCard>
      <div className="bg-gray-900 p-6 rounded-2xl shadow-lg w-full">

        <h2 className="text-xl mb-4">Upload Financial Document</h2>

        {/* DRAG ZONE */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-6 text-center transition ${
            dragActive ? "border-blue-500 bg-blue-500/10" : "border-gray-600"
          }`}
        >
          <p className="text-sm text-gray-400">
            Drag & drop file here or click below
          </p>

          <input
            type="file"
            disabled={loading}
            onChange={(e) =>
              e.target.files && handleFile(e.target.files[0])
            }
            className="mt-4"
          />

          {file && (
            <p className="mt-2 text-green-400 text-sm">
              Selected: {file.name}
            </p>
          )}
        </div>

        {/* PROGRESS */}
        {loading && (
          <div className="mt-4">
            <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
              <div
                className="bg-blue-500 h-3 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-sm mt-1 text-gray-400">
              Uploading... {progress}%
            </p>
          </div>
        )}

        {/* ERROR */}
        {error && (
          <p className="text-red-400 mt-2 text-sm">{error}</p>
        )}

        {/* SUCCESS */}
        {success && (
          <p className="text-green-400 mt-2 text-sm">
            Analysis completed successfully!
          </p>
        )}

        {/* BUTTON */}
        <motion.button
          whileTap={{ scale: 0.9 }}
          whileHover={{ scale: loading ? 1 : 1.05 }}
          onClick={handleUpload}
          disabled={loading}
          className={`mt-4 px-4 py-2 rounded-xl flex justify-center ${
            loading ? "bg-gray-500" : "bg-blue-600"
          }`}
        >
          {loading ? (
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Processing...
            </div>
          ) : (
            "Analyze"
          )}
        </motion.button>

      </div>
    </AnimatedCard>
  );
}