"use client";

import { motion } from "framer-motion";

export default function AnimatedCard({ children }: any) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      whileHover={{ scale: 1.03 }}
      className="w-full"
    >
      {children}
    </motion.div>
  );
}