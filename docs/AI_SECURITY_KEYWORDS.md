# AI Security Keywords and Topic Taxonomy

This is a starting point for keyword/topic sets used in:
1) selecting content from sources, and
2) classifying ingested items into security-relevant themes.

The focus is **LLM security, AI agent safety, privacy, robustness, and mitigations**.
Avoid collecting content primarily for offensive experimentation.

## Core keyword groups

### Prompt injection / jailbreak-adjacent risks
- "prompt injection"
- "indirect prompt injection"
- "jailbreak"
- "jailbreaking"
- "prompt leaking"
- "system prompt"
- "instruction hierarchy"
- "role override"
- "content injection"
- "prompt security"

### Data privacy and leakage
- "data leakage"
- "sensitive information"
- "information exfiltration"
- "model inversion"
- "membership inference"
- "prompt disclosure"
- "PII leakage"
- "training data extraction"
- "privacy attacks" (context: mitigation/evaluation)

### AI agent safety (tools, permissions, control)
- "AI agent security"
- "agent safety"
- "tool misuse"
- "function calling"
- "tool abuse"
- "untrusted tool"
- "access control"
- "authorization"
- "policy enforcement"
- "sandbox"
- "capability-based security"
- "agent orchestration risks"

### Secure RAG and retrieval risks
- "RAG security"
- "retrieval poisoning"
- "document injection"
- "context injection"
- "secure retrieval"
- "quote integrity"
- "grounding"
- "citation safety"

### Model and data supply chain integrity
- "model supply chain"
- "supply chain risk"
- "data poisoning"
- "training data poisoning"
- "prompt dataset poisoning"
- "weights integrity"
- "provenance"
- "integrity verification"

### Evaluation, benchmarks, and defenses (in a safety context)
- "threat model"
- "risk assessment"
- "evaluation framework"
- "security benchmark"
- "red teaming" (as safety evaluation)
- "mitigation"
- "guardrails"
- "robustness"
- "safe generation"
- "monitoring"
- "security controls"
- "incident response"

### Governance and compliance
- "AI governance"
- "AI safety policy"
- "risk management"
- "model risk management"
- "auditability"
- "transparency"

## Suggested query templates

Use search queries as AND/OR combinations, for example:

### Prompt injection template
- ("prompt injection" OR "indirect prompt injection" OR jailbreak) AND (mitigation OR evaluation OR defense)

### Agent tool misuse template
- ("agent" OR "AI agent") AND ("tool misuse" OR "function calling" OR "tool abuse") AND (policy OR access OR sandbox)

### Privacy template
- ("data leakage" OR "information exfiltration" OR "model inversion" OR "membership inference") AND (mitigation OR privacy OR evaluation)

## Mapping to an internal taxonomy

For each ingested item, store:
- `primary_topic` (choose from: PROMPT_INJECTION, DATA_LEAKAGE, AGENT_TOOL_MISUSE, RAG_SECURITY, SUPPLY_CHAIN, EVALUATION, GOVERNANCE)
- `evidence_type` (STANDARD, PAPER, ADVISORY, INCIDENT, GUIDE)
- `artifact_type` (text, feed item, repo issue/discussion thread)
- `suggested_controls` (free text extracted from the item)

