import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/http";

export const Route = createFileRoute('/login')({
  component: LoginPage,
});

function LoginPage() {
  const [email, setEmail] = useState("");

  const [password, setPassword] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem("token")) {
      window.location.href = "/";
    }
  }, []);

  async function handleLogin() {
    try {
      const response = await fetch(`${API_BASE}/login`, {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          email,
          password,
        }),
      });

      const data = await response.json();

      if (data.success) {
        localStorage.setItem("token", data.access_token);

        window.location.href = "/";
      } else {
        alert(data.message);
      }
    } catch (error) {
      console.error(error);

      alert("Login failed");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-[400px] rounded-xl border p-8 space-y-4">
        <h1 className="text-3xl font-bold">Login</h1>

        <input
          type="email"
          placeholder="Email"
          className="w-full border p-3 rounded"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <input
          type="password"
          placeholder="Password"
          className="w-full border p-3 rounded"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <button onClick={handleLogin} className="w-full bg-blue-600 text-white p-3 rounded">
          Login
        </button>
        <p className="text-sm text-muted-foreground">
          Don’t have an account? <a href="/signup" className="text-primary underline">Sign up</a>
        </p>
      </div>
    </div>
  );
}
