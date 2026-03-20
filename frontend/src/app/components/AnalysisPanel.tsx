"use client";

import { motion } from "framer-motion";

export default function AnalysisPanel({ analysis }: { analysis: string }) {

  return (
    <motion.div
      className="bg-gray-900 p-4 rounded-2xl col-span-3"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.8 }}
    >
      <h2 className="text-xl mb-4">AI Credit Analysis</h2>

      <motion.p
        key={analysis}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1 }}
        className="text-gray-300"
      >
        {analysis}
      </motion.p>
    </motion.div>
  );
}