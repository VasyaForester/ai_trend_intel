# AI Security Sources (LLM + AI Agents)

This document lists **recommended categories of public information sources** for collecting messages about
AI security and LLM/AI agent security.

The goal is to **understand risks, safety gaps, mitigations, governance practices, and emerging patterns**.
The project should avoid framing or collecting content primarily for offensive use.

## Source categories

### 1) Security standards and risk frameworks
- NIST (AI Risk Management Framework / related AI guidance)
- ISO/IEC AI-related security and risk standards (where applicable)
- OWASP (LLM-focused risk lists and guidance)

How to parse:
- Prefer RSS/news feeds, official changelogs, and structured “advisory” pages.

### 2) Advisories and vulnerability disclosures (LLM/AI-related)
- CVE / NVD entries that mention LLMs, model services, inference stacks, or agent frameworks
- Vendor advisories for model-serving stacks (inference gateways, tool connectors, RAG pipelines)
- CERT-style guidance when it exists for AI systems

How to parse:
- Treat items as “risk events”: extract affected component(s), risk type, and recommended mitigations.

### 3) Research and technical papers (evidence-backed)
- arXiv (queries for LLM security, prompt injection, agent vulnerabilities, privacy attacks, etc.)
- Academic venues (where you can access abstracts or open summaries)
- Industry research blogs (when they publish findings with methodology)

How to parse:
- Prefer papers that include threat model, evaluation setup, and mitigation discussion.

### 4) Engineering blogs, incident writeups, and postmortems
- Company security research blogs that discuss LLM/agent security in a safety context
- Public incident reports about data leakage, tool misuse, or unsafe agent behavior

How to parse:
- Extract: what happened, root cause, detection/mitigation, and lessons learned.

### 5) Framework and platform documentation (mitigations and best practices)
- Docs from LLM/agent frameworks about safety features, tool permissions, and sandboxing
- RAG/security guidance (retrieval filtering, access control, prompt construction safety)

How to parse:
- Extract security controls and configuration guidelines (not just feature announcements).

### 6) Public community signals
- GitHub security advisories (ecosystem-level dependencies used by AI apps)
- Public discussions where mitigations and patterns are shared (avoid purely offensive posts)
- Conference talks that publish slides or transcripts publicly

How to parse:
- Use community sources carefully: deduplicate and prefer items with references or actionable mitigations.

## Connector types (implementation-oriented)

When you build connectors, start with these ingestion patterns:

- **RSS/Atom**: standardized parsing for news and blog feeds
- **Web scraping (structured)**: extract title, author, date, main text, and tags from known layouts
- **API ingestion**:
  - GitHub search (issues/discussions) for AI security topics
  - arXiv API/RSS for paper abstracts
  - Optional: vendor-specific APIs if they exist and are allowed by terms of service

## Default tagging (high-level)

When ingesting, map each item to:
- Domain: `LLM`, `AI_AGENT`, `RAG`, `MODEL_SERVING`, `DATA_PRIVACY`, `GOVERNANCE`
- Risk theme: `PROMPT_INJECTION`, `DATA_LEAKAGE`, `AGENT_TOOL_MISUSE`, `SUPPLY_CHAIN`, `EVALUATION`, etc.
- Stage: `DISCOVERY`, `MITIGATION`, `EVALUATION`, `GOVERNANCE_POLICY`

## Concrete starting sources (starter list)

These are good starting points to wire into ingestion connectors. You should verify
availability (RSS endpoints, pagination, robots.txt, and terms of service) before automating collection.

### LLM and agent security risk guidance
- OWASP - Top 10 for Large Language Model Applications: https://owasp.org/www-project-top-ten-for-large-language-model-applications/
- OWASP - Main site (search within for LLM-related items): https://owasp.org/

### Risk management frameworks and governance
- NIST - AI Risk Management Framework (AI RMF): https://www.nist.gov/itl/ai-risk-management-framework
- NIST AI-related security publications (start from NIST AI index pages): https://www.nist.gov/itl/ai

### Research repositories (paper discovery)
- arXiv search (use topic keyword queries, e.g. for security and LLM-related terms): https://arxiv.org/search/
- arXiv (category landing pages, useful if you later build category-specific queries): https://arxiv.org/archive/

### Public news and engineering writeups
- GitHub Security Lab (AI/ML-adjacent security posts often appear here): https://securitylab.github.com/
- CERT-style guidance (start from CERT/CSIRT directories and search by AI/LLM terms): https://www.cert.org/

### Tooling and frameworks (safety controls)
- OWASP guidance and example libraries: https://owasp.org/
- Vendor safety and security pages (use your chosen providers and track their change logs): https://openai.com/safety/


