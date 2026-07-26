# 🚀 AI Credit Intelligence Platform

An AI-powered credit risk assessment and fraud intelligence platform designed to help financial institutions, lenders, NBFCs, fintech companies, and risk teams make faster, smarter, and more explainable lending decisions.

---

## 📌 Problem Statement

Traditional credit evaluation systems are often:

* Slow and heavily manual
* Difficult to scale
* Limited in fraud detection capabilities
* Unable to provide transparent risk explanations
* Dependent on static rule-based decision making

Financial institutions need a system that can:

* Assess borrower creditworthiness instantly
* Detect suspicious transactions in real-time
* Explain decisions using AI insights
* Monitor portfolio health continuously
* Reduce operational risk

---

## 💡 Solution

AI Credit Intelligence Platform combines:

### 1. Credit Risk Assessment

Predicts borrower risk using machine learning models and financial indicators.

### 2. Fraud Detection Engine

Identifies anomalous transaction patterns using unsupervised machine learning.

### 3. Portfolio Intelligence

Provides portfolio-level risk monitoring and performance analytics.

### 4. Explainable AI

Generates understandable explanations behind every prediction.

### 5. Executive Dashboard

Offers real-time visibility into approvals, risk distribution, fraud alerts, and portfolio metrics.

---

# ✨ Core Features

## Credit Scoring

* AI-based credit score generation
* Risk categorization

  * Low Risk
  * Medium Risk
  * High Risk
* Approval recommendation
* Probability-based confidence scoring
* Explainable AI insights

---

## Fraud Detection

* Isolation Forest anomaly detection
* Suspicious transaction identification
* Fraud risk classification
* Anomaly scoring
* AI-generated fraud explanations

---

## Risk History

Track all previous credit evaluations including:

* Credit score
* Risk level
* Approval status
* AI explanations
* Prediction timestamp

---

## Fraud History

Maintain historical fraud checks with:

* Fraud status
* Risk classification
* Anomaly score
* Detection timestamp
* AI analysis

---

## Portfolio Analytics

Portfolio-wide insights including:

* Total predictions
* Approval rate
* Average credit score
* Risk segmentation
* Portfolio health monitoring

---

## Executive Dashboard

Real-time monitoring of:

* Credit performance
* Fraud metrics
* Portfolio statistics
* Recent assessments
* Recent fraud alerts

---

# 🏗️ System Architecture

Frontend (React + TanStack Router + TypeScript)

↓

FastAPI Backend

↓

Machine Learning Services

↓

SQLite Database

↓

Credit Risk Engine + Fraud Detection Engine

---

# 🤖 AI Models

## Credit Risk Model

Uses supervised machine learning to evaluate:

* Age
* Employment status
* Housing
* Savings behavior
* Checking account status
* Credit amount
* Loan duration
* Loan purpose

Outputs:

* Credit Score
* Approval Probability
* Risk Classification

---

## Fraud Detection Model

Uses:

### Isolation Forest

Analyzes:

* Transaction Amount
* Transaction Frequency
* Account Age

Outputs:

* Fraud Detection Result
* Fraud Risk Level
* Anomaly Score

---

# 🛠️ Tech Stack

## Frontend

* React
* TypeScript
* TanStack Router
* TanStack Query
* Tailwind CSS
* Recharts
* Framer Motion
* Lovable AI UI Generation

## Backend

* FastAPI
* SQLAlchemy
* Pydantic
* JWT Authentication
* SQLite

## Machine Learning

* Scikit-Learn
* Isolation Forest
* NumPy
* Pandas

## Development Tools

* Git
* GitHub
* VS Code
* GitHub Copilot

---

# 🔐 Authentication

Supports:

* User Registration
* Secure Login
* JWT Access Tokens
* Protected Routes
* Session Persistence
* Logout Functionality

---

# 📊 API Modules

### Authentication

* Signup
* Login

### Credit Intelligence

* Credit Prediction
* Prediction History
* Portfolio Summary

### Fraud Intelligence

* Fraud Detection
* Fraud History
* Fraud Summary

### Dashboard

* Unified Executive Dashboard API

---

# 🎯 Target Users

* Banks
* NBFCs
* Fintech Companies
* Credit Analysts
* Risk Teams
* Lending Platforms
* Financial Institutions

---

# 🚀 Future Roadmap

### Phase 2

* Multi-Agent AI Risk Analysis
* LLM-Based Financial Reasoning
* Model Monitoring & Drift Detection
* Real-Time Streaming Fraud Detection
* Portfolio Stress Testing
* Advanced Explainable AI

### Phase 3

* Enterprise SaaS Deployment
* Cloud Infrastructure
* Multi-Tenant Architecture
* Regulatory Compliance Dashboard
* Automated Risk Reports

---

# 🧠 Autonomous AI Banking Intelligence (Phase 9)

The platform now includes an autonomous "AI Brain" layer (all under `/api/ai/*`,
UI under the **Autonomous Intelligence** sidebar group). Fully additive and
grounded in deterministic platform data — the optional LLM only phrases facts,
never fabricates numbers. See `docs/PHASE9_ENGINEERING_REPORT.md`.

* **Enterprise Knowledge Graph** — companies, directors, subsidiaries, suppliers,
  lenders and sectors as a weighted graph with traversal, connected exposure,
  similarity and risk propagation.
* **Real-Time Risk Monitoring** & **Early Warning Signals** — continuous change
  detection across financials/connectors/GST/MCA/bureau/news with prioritized
  alerts, EWS scoring and escalation.
* **AI Credit Copilot** & **Natural Language Analytics** — ask questions and get
  grounded answers / structured queries (offline-safe local LLM by default; a
  gated Claude adapter can be enabled with `COPILOT_LLM_PROVIDER=claude`).
* **Scenario Simulation**, **Stress Testing**, **Portfolio Optimization** —
  what-if PD/rating/limit re-scoring, Base/Moderate/Severe/Custom stress with
  loss & capital projections, RAROC and concentration analysis.
* **RM Workspace**, **Executive Command Center**, **Recommendation Engine**,
  **Autonomous Workflow Intelligence**, **Model Governance** and an
  **Enterprise Data Lake** for analytics.

---

# 👨‍💻 Developer

**Shriyansh Dev**

AI & Machine Learning Enthusiast

Focused on building intelligent fintech and agentic AI systems.

GitHub:
https://github.com/Shriyansh21-ai

---

# ⭐ Project Vision

To build an intelligent financial decision-making platform that enables organizations to assess risk, prevent fraud, and make transparent AI-driven lending decisions at scale.
