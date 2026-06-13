import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

export const Route = createFileRoute('/signup')({
  component: SignupPage,
});

function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem("token")) {
      window.location.href = "/";
    }
  }, []);

  async function handleSignup() {
    try {
      const response = await fetch("http://127.0.0.1:8000/signup", {
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
        // Store JWT token
        localStorage.setItem("token", data.access_token);
        
        alert("Account created successfully");
        
        // Redirect to dashboard
        window.location.href = "/";
      } else {
        alert(data.message);
      }
    } catch (error) {
      console.error(error);

      alert("Signup failed");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-[400px] rounded-xl border p-8 space-y-4">
        <h1 className="text-3xl font-bold">Create Account</h1>

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

        <button onClick={handleSignup} className="w-full bg-blue-600 text-white p-3 rounded">
          Sign Up
        </button>
        <p className="text-sm text-muted-foreground">
          Already have an account? <a href="/login" className="text-primary underline">Log in</a>
        </p>
      </div>
    </div>
  );
}
