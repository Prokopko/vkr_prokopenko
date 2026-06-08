---
register: product
---

# Smart Contract Audit Studio

## Product Purpose
Automated security audit platform for Ethereum-ecosystem smart contracts. Analysts submit a contract address or Solidity source code and receive a consolidated report from three engines: Slither (static analysis), Mythril (symbolic execution), and LLM semantic review. Results are persisted in NocoDB for historical tracking, comparison, and PDF export.

## Users
**Primary:** Security auditors and blockchain researchers who review contract code before deployment or investment decisions. They need fast triage (trusted / warning / suspicious) followed by deep investigation (findings by severity, raw tool output, source code).  
**Secondary:** Junior analysts who rely on the tool's verdict and recommendations without reading raw output.

## Brand Tone
Professional, precise, composed. The tool handles high-stakes findings (potential exploits, financial risk) so the UI must project calm authority — not panic, not hype. Severity is communicated factually, not dramatically.

## Anti-references
- Neon-on-black "crypto" aesthetic
- Dark navy "enterprise security" SaaS (current design falls here)
- Glassmorphism / frosted card effects
- The hero-metric template (big number, gradient card)
- Dashboard widget clutter
- Flashy gradients on UI chrome (buttons, cards, sidebar)

## Strategic Principles
1. Risk signals must be immediately readable — verdict and severity dominate, chrome recedes.
2. The tool is used in daylight, analytical, professional contexts — optimize for sustained reading, not demo-screen impressiveness.
3. Support two usage modes: quick triage (verdict + score at a glance) and deep investigation (findings table, source viewer, raw JSON).
4. The interface is a professional instrument, not a marketing surface.
