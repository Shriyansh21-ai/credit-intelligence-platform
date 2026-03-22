"use client";

import { useState } from "react";

export default function AuthPage() {

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {

    if (!email || !password) {
      alert("Enter email and password");
      return;
    }

    setLoading(true);

    try {
      const endpoint = isLogin ? "login" : "signup";

      const res = await fetch(`http://127.0.0.1:8000/${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          email,
          password
        })
      });

      const data = await res.json();

      if (res.ok) {
        // 🔐 Store credentials (simple auth for now)
        localStorage.setItem("email", email);
        localStorage.setItem("password", password);

        alert(isLogin ? "Login successful" : "Signup successful");

        // 👉 redirect to dashboard
        window.location.href = "/";
      } else {
        alert(data.detail || data.message || "Something went wrong");
      }

    } catch (err) {
      console.error(err);
      alert("Server error");
    }

    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-black text-white">

      <div className="bg-gray-900 p-8 rounded-2xl w-96">

        <h2 className="text-2xl mb-4">
          {isLogin ? "Login" : "Signup"}
        </h2>

        <input
          placeholder="Email"
          className="w-full p-2 mb-3 bg-gray-800 outline-none"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <input
          placeholder="Password"
          type="password"
          className="w-full p-2 mb-3 bg-gray-800 outline-none"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <button
          onClick={handleSubmit}
          disabled={loading}
          className="bg-blue-600 w-full py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Please wait..." : (isLogin ? "Login" : "Signup")}
        </button>

        <p
          className="mt-3 text-sm cursor-pointer text-gray-400"
          onClick={() => setIsLogin(!isLogin)}
        >
          Switch to {isLogin ? "Signup" : "Login"}
        </p>

      </div>

    </div>
  );
}