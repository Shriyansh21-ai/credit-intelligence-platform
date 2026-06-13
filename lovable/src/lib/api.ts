const API_BASE = "http://127.0.0.1:8000";

// =====================================
// Auth Helpers
// =====================================

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem("token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

function checkAuth() {
  if (typeof window !== "undefined" && !localStorage.getItem("token")) {
    window.location.href = "/login";
    throw new Error("No token found");
  }
}

// =====================================
// Authentication
// =====================================

export async function signup(email: string, password: string) {
  const response = await fetch(`${API_BASE}/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return response.json();
}

export async function login(email: string, password: string) {
  const response = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return response.json();
}

// =====================================
// Dashboard
// =====================================

export interface DashboardData {
  success: boolean;
  user: string;
  portfolio_summary: {
    total_predictions: number;
    approved: number;
    approval_rate: number;
    average_credit_score: number;
  };
  fraud_summary: {
    total_checks: number;
    fraud_detected: number;
    fraud_rate: number;
  };
  recent_predictions: any[];
  recent_fraud_checks: any[];
}

export async function getDashboard(): Promise<DashboardData> {
  checkAuth();
  const response = await fetch(`${API_BASE}/dashboard/overview`, {
    headers: getAuthHeaders(),
  });
  
  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    throw new Error("Failed to fetch dashboard data");
  }
  
  return response.json();
}

// =====================================
// Risk History
// =====================================

export interface RiskHistoryItem {
  id: number;
  credit_score: number;
  risk_level: string;
  approval: boolean;
  probability: number;
  ai_analysis: string;
  created_at: string;
}

export interface RiskHistoryResponse {
  success: boolean;
  data: RiskHistoryItem[];
}

export async function getRiskHistory(): Promise<RiskHistoryResponse> {
  checkAuth();
  const response = await fetch(`${API_BASE}/risk-history`, {
    headers: getAuthHeaders(),
  });
  
  if (!response.ok) {
    throw new Error("Failed to fetch risk history");
  }
  
  return response.json();
}

// =====================================
// Fraud History
// =====================================

export interface FraudHistoryItem {
  id: number;
  amount: number;
  frequency: number;
  account_age: number;
  fraud_detected: boolean;
  fraud_score: number;
  anomaly_score: number;
  ai_analysis: string;
  created_at: string;
}

export interface FraudHistoryResponse {
  success: boolean;
  data: FraudHistoryItem[];
}

export async function getFraudHistory(): Promise<FraudHistoryResponse> {
  checkAuth();
  const response = await fetch(`${API_BASE}/fraud-history`, {
    headers: getAuthHeaders(),
  });
  
  if (!response.ok) {
    throw new Error("Failed to fetch fraud history");
  }
  
  return response.json();
}

// =====================================
// Fraud Summary
// =====================================

export async function getFraudSummary() {
  checkAuth();
  const response = await fetch(`${API_BASE}/fraud-summary`, {
    headers: getAuthHeaders(),
  });
  
  if (!response.ok) {
    throw new Error("Failed to fetch fraud summary");
  }
  
  return response.json();
}

// =====================================
// Portfolio Summary
// =====================================

export async function getPortfolioSummary() {
  checkAuth();
  const response = await fetch(`${API_BASE}/portfolio-summary`, {
    headers: getAuthHeaders(),
  });
  
  if (!response.ok) {
    throw new Error("Failed to fetch portfolio summary");
  }
  
  return response.json();
}

// =====================================
// Predictions
// =====================================

export interface PredictionRequest {
  age: number;
  sex: string;
  job: number;
  housing: string;
  saving_account: string;
  checking_account: string;
  credit_amount: number;
  duration: number;
  purpose: string;
}

export interface PredictionResponse {
  success: boolean;
  credit_score: number;
  risk_level: string;
  approval: boolean;
  probability: number;
  ai_analysis: string;
}

export async function runPrediction(data: PredictionRequest): Promise<PredictionResponse> {
  checkAuth();
  // Backend prediction route expects specific field names (capitalized)
  const payload = {
    Age: data.age,
    Sex: data.sex,
    Job: data.job,
    Housing: data.housing,
    Saving_accounts: data.saving_account,
    Checking_account: data.checking_account,
    Credit_amount: data.credit_amount,
    Duration: data.duration,
    Purpose: data.purpose,
  };

  const response = await fetch(`${API_BASE}/predict/predict`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  
  if (!response.ok) {
    throw new Error("Failed to run prediction");
  }
  const res = await response.json();
  // Backend returns { success: true, data: { ... } }
  return res.data ?? res;
}

// =====================================
// Fraud Detection
// =====================================

export interface FraudCheckRequest {
  amount: number;
  frequency: number;
  account_age: number;
}

export interface FraudCheckResponse {
  success: boolean;
  fraud_detected: boolean;
  fraud_score: number;
  anomaly_score: number;
  ai_analysis: string;
}

export async function runFraudCheck(data: FraudCheckRequest): Promise<FraudCheckResponse> {
  checkAuth();
  const response = await fetch(`${API_BASE}/detect-fraud`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error("Failed to run fraud check");
  }
  
  return response.json();
}