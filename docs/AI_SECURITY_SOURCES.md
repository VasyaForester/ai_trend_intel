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

### Research repositories (paper discovery)
- arXiv (home): https://arxiv.org/
- arXiv search (use keyword queries): https://arxiv.org/search/
- arXiv archive (category index): https://arxiv.org/archive/
- arXiv cs.CR (recent): https://arxiv.org/list/cs.CR/recent
- arXiv cs.AI (recent): https://arxiv.org/list/cs.AI/recent
- IACR ePrint (cryptography/security papers): https://eprint.iacr.org/

### Frontier labs and research blogs (LLM/agent context)
- OpenAI Research: https://openai.com/research
- Anthropic Research: https://www.anthropic.com/research
- Google DeepMind Blog: https://deepmind.google/discover/blog/
- Meta AI Blog: https://ai.meta.com/blog/

### Security and engineering blogs (practical trends & mitigations)
- Microsoft Security Blog: https://www.microsoft.com/en-us/security/blog/
- Trail of Bits: https://blog.trailofbits.com/
- HiddenLayer Research: https://hiddenlayer.com/research/
- Protect AI Blog: https://protectai.com/blog
- Lakera Blog: https://www.lakera.ai/blog
- Robust Intelligence Blog (archive): https://www.robustintelligence.com/blog
- Cloudflare Security tag: https://blog.cloudflare.com/tag/security/
- GitHub Security: https://github.blog/security/
- Google Project Zero: https://googleprojectzero.blogspot.com/
- GitHub Security Lab: https://securitylab.github.com/

### LLM and AI security risk guidance (standards / playbooks / threat catalogs)
- OWASP - Top 10 for Large Language Model Applications: https://owasp.org/www-project-top-ten-for-large-language-model-applications/
- OWASP - AI Security and Privacy Guide: https://owasp.org/www-project-ai-security-and-privacy-guide/
- MITRE ATLAS: https://atlas.mitre.org/
- NIST - AI Risk Management Framework (AI RMF): https://www.nist.gov/itl/ai-risk-management-framework
- AI Now Institute: https://ainowinstitute.org/
- UK AISI: https://www.aisi.gov.uk/

### Conferences and professional publications
- USENIX Security Symposium: https://www.usenix.org/conference/usenixsecurity
- IEEE Security & Privacy Magazine: https://www.computer.org/csdl/magazine/sp

### Media & community signals (use carefully; prefer referenced posts)
- WIRED: https://www.wired.com
- Reddit /r/LocalLLaMA: https://www.reddit.com/r/LocalLLaMA/
- Reddit /r/MachineLearning: https://www.reddit.com/r/MachineLearning/
- Reddit /r/AI_Safety: https://www.reddit.com/r/AI_Safety/
- Reddit /r/llmsecurity: https://www.reddit.com/r/llmsecurity/
- Simon Willison: https://simonwillison.net/
- Import AI (newsletter): https://importai.substack.com/
- The Gradient: https://thegradient.pub/


