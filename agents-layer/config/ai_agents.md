# AI Agents Portfolio

## Purpose

This file defines the editable first-wave portfolio for the `compliance-agents-layer` and `expert-agents-layer`.

The runtime supports one to ten active compliance agents and one to ten active expert agents without changing service architecture.

## Shared Operating Rules

- Agents are advisory only.
- Humans validate, approve, decide, and sign off.
- Agents do not own product master data, DPP records, raw evidence, source documents, or formal certification decisions.
- Agents read governed context from product-layer, data-layer, configuration, and Mempalace.
- Every finding must include traceability.
- Restricted evidence requires approved access.
- LAN Ollama is the default local LLM pattern.
- Enterprise cloud providers are optional and must be explicitly approved.

## Compliance Agents

1. Sustainability & Environment Compliance Agent
2. EMC & Electrical Conformity Compliance Agent
3. Cybersecurity Certification Compliance Agent
4. Wireless Standards Compliance Agent
5. Data Protection & Privacy Compliance Agent

## Expert Agents

1. DPP Readiness Expert
2. Sustainability & Circularity Expert
3. EMC & Electrical Design Expert
4. Cybersecurity & Software Quality Expert
5. Product Data Governance Expert
6. CAD and Mechanical Design Expert
7. Pricing, Sales, and Market Expert
8. Aftermarket Service Expert

## LLM Access

Default provider:

```text
provider: ollama_lan
base_url: http://192.168.178.60:11434
model: gpt-oss:20b
```

Alternative localhost provider for host-local runs:

```text
provider: ollama_localhost
base_url: http://localhost:11434
model: gpt-oss:20b
```

LLM output may help with explanation and synthesis, but deterministic checks and traceability remain visible in the returned assessment.

## Escalation Policy

- Critical compliance gaps escalate to compliance owner and product owner.
- Security and vulnerability findings require restricted handling.
- Certification-impacting findings require human review.
- Missing evidence is routed as workflow feedback, not silently corrected.

## Sign-Off Policy

No agent can provide final certification, engineering, legal, privacy, or market sign-off.
