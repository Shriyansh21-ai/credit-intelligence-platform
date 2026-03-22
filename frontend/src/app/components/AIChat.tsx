"use client";

import { useState } from "react";
import { apiFetch } from "../../../utils/api";

export default function AIChat({ context }: any) {

  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {

    if (!input.trim()) return;

    const userMessage = input;

    const newMessages = [
      ...messages,
      { role: "user", content: userMessage }
    ];

    setMessages(newMessages);
    setInput("");
    setLoading(true);

    try {
      const res = await apiFetch("http://127.0.0.1:8000/ai-chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: userMessage,   // ✅ FIXED
          context: context        // ✅ PASSING FULL RESULT
        })
      });

      const data = await res.json();

      setMessages([
        ...newMessages,
        { role: "assistant", content: data.reply }
      ]);

    } catch (err) {
      console.error(err);
      setMessages([
        ...newMessages,
        { role: "assistant", content: "Error getting response" }
      ]);
    }

    setLoading(false);
  };

  return (
    <div className="bg-gray-900 p-5 rounded-2xl col-span-3 flex flex-col h-[400px]">

      <h2 className="text-xl mb-3">AI Credit Chat</h2>

      <div className="flex-1 overflow-y-auto space-y-2 mb-3">

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`p-2 rounded-lg text-sm max-w-[80%] ${
              msg.role === "user"
                ? "bg-blue-600 self-end ml-auto"
                : "bg-gray-700"
            }`}
          >
            {msg.content}
          </div>
        ))}

        {loading && (
          <div className="text-gray-400 text-sm">
            AI is thinking...
          </div>
        )}

      </div>

      <div className="flex gap-2">
        <input
          className="flex-1 p-2 rounded bg-gray-800 outline-none"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about risk, fraud, decision..."
          onKeyDown={(e) => {
            if (e.key === "Enter") sendMessage();
          }}
        />

        <button
          onClick={sendMessage}
          className="bg-blue-600 px-4 rounded hover:bg-blue-700"
        >
          Send
        </button>
      </div>

    </div>
  );
}