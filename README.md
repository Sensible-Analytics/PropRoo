<div align="center">

[![PropRoo](https://www.sensibleanalytics.co/logos/proproo-logo.png)](https://proproo.sensibleanalytics.co)

# PropRoo

### Smart Property Analytics Engine

**Australian real estate insights with AI-powered analysis**

[![Live Demo](https://img.shields.io/badge/Live_Demo-00C7B7?style=for-the-badge&logo=vercel&logoColor=white)](https://proproo.sensibleanalytics.co)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Sensible-Analytics/PropRoo)

</div>

---

## 🛡️ Security First

> ⚠️ **CRITICAL SECURITY WARNING**
> 
> This repository uses **automated secret scanning**. NEVER commit:
> - API keys (OpenAI, Anthropic, database credentials)
> - AI agent tokens
> - Database connection strings
> - Private keys
> 
> **Before committing:** Review our [Security Policy](SECURITY.md) and [AI Agent Keys Policy](AI_AGENT_KEYS_POLICY.md)

---

## 🎯 What is PropRoo?

PropRoo is a **smart, Aussie-flavoured property analytics engine** that helps investors hop through market data, rental insights, and investment metrics with ease. Built for Australian property investors who want clarity without the clutter.

### Key Capabilities

- 📊 **Market Analysis** — Real-time property market data and trends
- 🏠 **Rental Insights** — Rental yield calculations and comparisons
- 📈 **Investment Metrics** — ROI, cash flow, and growth projections
- 🗺️ **Location Intelligence** — Suburb-level analytics and demographics
- 🔍 **Property Search** — Smart filters for finding opportunities

---

## ✨ Features

### For Property Investors

- **Portfolio Dashboard** — Track all your properties in one place
- **Market Trends** — Visualize price movements and rental yields
- **Investment Calculator** — Model different scenarios
- **Suburb Reports** — Deep-dive into local market conditions
- **Alert System** — Get notified of new opportunities

### For Real Estate Professionals

- **Client Reporting** — Generate professional investment reports
- **Market Comparisons** — Side-by-side property analysis
- **Data Exports** — CSV and PDF report generation
- **API Access** — Programmatic access to property data

---

## 🚀 Quick Start

### Live Demo

Try PropRoo now at **[proproo.sensibleanalytics.co](https://proproo.sensibleanalytics.co)**

### Local Development

```bash
# Clone the repository
git clone https://github.com/Sensible-Analytics/PropRoo.git
cd PropRoo

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Install frontend dependencies
cd ../frontend
npm install

# Start development servers
npm run dev
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Frontend** | React, TypeScript, Tailwind CSS |
| **Backend** | Python, FastAPI |
| **Database** | PostgreSQL |
| **AI/ML** | Python, scikit-learn |
| **Deployment** | Vercel |

---

## 📊 Use Cases

### Property Investment Analysis

```
Input: Property address + purchase price
Output: Rental yield, capital growth projections, comparable sales
```

### Suburb Scoring

```
Input: Suburb name
Output: Growth potential, rental demand, infrastructure projects
```

### Portfolio Tracking

```
Input: List of properties
Output: Total equity, rental income, performance metrics
```

---

## 🏆 Case Studies

### Healthcare Analytics Platform Modernization

*Client: Healthcare Consultancy*

Transformed a consultancy-based analytics platform into a global SaaS provider:

- **83%** Subscription Revenue (up from 56%)
- **3x** Client Capacity
- **76%** Cost Reduction

[Read full case study](https://www.sensibleanalytics.co)

---

## 🤝 Contributing

We welcome contributions from the community!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please read our [Contributing Guide](CONTRIBUTING.md) for details.

---

## 🛡️ Security

### 🔒 Automated Protection

This repository includes:
- ✅ **Pre-commit hooks** - Scan for secrets before every commit
- ✅ **GitHub Secret Scanning** - Automatic detection of exposed credentials
- ✅ **Push Protection** - Block commits containing secrets
- ✅ **Dependency scanning** - Detect vulnerable packages

### 🚨 Security Requirements

**Before contributing:**

1. **Install pre-commit hooks:**
   ```bash
   pip install pre-commit
   pre-commit install
   ```

2. **Use environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your keys (NEVER commit this file!)
   ```

3. **Verify .env is ignored:**
   ```bash
   git check-ignore .env  # Should output: .env
   ```

### 🆘 Security Incidents

**If you accidentally commit a secret:**

1. **DO NOT PANIC**
2. **REVOKE the key immediately** via provider dashboard
3. **Contact:** security@sensibleanalytics.co
4. **Follow our [Incident Response Guide](SECURITY.md)**

### 📋 Security Checklist

- [ ] Pre-commit hooks installed
- [ ] .env file created from .env.example
- [ ] .env added to .gitignore
- [ ] No hardcoded API keys in code
- [ ] No console.log of sensitive data

For full details, see our [Security Policy](SECURITY.md) and [AI Agent Keys Policy](AI_AGENT_KEYS_POLICY.md).

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built by [Sensible Analytics](https://www.sensibleanalytics.co)**  
*AI architecture for regulated industries*

[Website](https://www.sensibleanalytics.co) · [LinkedIn](https://www.linkedin.com/in/prabhatr/) · [Support](mailto:hello@sensibleanalytics.co)

</div>
