import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/http";

export const Route = createFileRoute('/signup')({
  component: SignupPage,
});

function SignupPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [organization, setOrganization] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem("token")) {
      window.location.href = "/";
    }
  }, []);

  async function handleSignup() {
    try {
      const response = await fetch(`${API_BASE}/signup`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
          job_title: jobTitle,
          organization,
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
          type="text"
          placeholder="Full name"
          className="w-full border p-3 rounded"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
        />

        <input
          type="email"
          placeholder="Work email"
          className="w-full border p-3 rounded"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <input
          type="text"
          placeholder="Job title (e.g. Senior Credit Analyst)"
          className="w-full border p-3 rounded"
          value={jobTitle}
          onChange={(e) => setJobTitle(e.target.value)}
        />

        <input
          type="text"
          placeholder="Organization / Bank"
          className="w-full border p-3 rounded"
          value={organization}
          onChange={(e) => setOrganization(e.target.value)}
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
