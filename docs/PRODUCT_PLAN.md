# Product and rollout plan

This is a proposed plan. Pricing, conversion, reliability, and market position are hypotheses until measured with real customers and production telemetry.

## One product, three entry points

1. **Developer:** `agent-trust run` evaluates a local action-intent fixture and exports a reproducible Agent Passport. The next increment is an instrumented LangGraph tool wrapper and CrewAI/Paperclip event bridges, each validated against pinned upstream versions.
2. **Platform team:** enroll real agents, define scoped delegation, intercept sensitive tool calls at an authenticated gateway, route human approvals, retain receipts, and monitor outcomes. This requires a durable replay store, signatures, workload identity, multi-tenant isolation, and tested recovery before production claims.
3. **Buyer:** inspect a signed passport and assurance case for a named agent, environment, version, and time period. Export evidence to GRC_Claw and the AI Governance Evidence Graph; permit independent verification without exposing raw prompts or secrets.

The customer-facing wedge is a **verified support agent**. It retrieves tenant-scoped policy, drafts a refund, requests approval, executes through a governed tool, and produces an outcome-linked receipt. Web chat first; voice, telephony, social channels, and outbound campaigns follow demonstrated demand. Chatbase already sells those channels, so the differentiation must be verified actions and evidence, not basic document chat.

## Open-source boundary

Keep the event and receipt schemas, local verifier, reference policy, synthetic cases, sample adapters, benchmark scenarios, and single-tenant development UI public. Do not require an account to reproduce the first demo. Publish versions and migration rules for event contracts. Benchmark only observed results and label simulated data.

## Commercial boundary

Sell managed operations: authenticated ingestion, hosted retention, enterprise connectors, cross-tenant administration, SSO, key management, policy rollout, continuous evaluations, incident workflow, service-level commitments, private deployment, and buyer evidence rooms. Publish the export/verification format so paying customers are not trapped. Charge implementation separately when integration work is genuinely bespoke.

## Adoption loop and leading indicators

| Stage | Measured signal | Decision gate |
| --- | --- | --- |
| Discovery | Qualified visits to reproducible demos; docs-to-install conversion | Publish another case only if it brings relevant users |
| Activation | First verified local passport within 15 minutes | Fix onboarding before adding more catalog items |
| Integration | At least one real agent and tool connected; sampled event completeness | Reject unverified connector claims |
| Retention | Weekly active organizations; recurring policy review and evidence exports | Identify which report causes repeat use |
| Revenue | Paid pilot conversion, expansion, gross and contribution margin | Reduce deployment/support cost before scaling sales |
| Trust | Unauthorized-action escape rate, false denials, missing receipts, replay failures | No safety claim from demo-only evidence |

## 90-day sequence

**Days 1–30:** freeze event/receipt contract, ship this demo and verifier, build one real LangGraph integration behind an authenticated test gateway, and recruit three design partners around the refund workflow.

**Days 31–60:** add CrewAI and Paperclip adapters, GRC_Claw export, offline benchmark runner, simple UI, and one-click reproducible demo. Add continuous tests for tenant isolation, approval replay, revocation, missing receipts, and recovery.

**Days 61–90:** run paid pilots. Capture procurement objections, support hours, inference/storage cost, time-to-first-passport, and observed unauthorized-action escape rate. Publish only consented, reproducible benchmark results. Decide whether to deepen support-agent sales or pivot to internal agent governance based on activation and paid conversion.

## Unit-economics ledger

For each organization and month, record `subscription_revenue`, `usage_revenue`, `inference_cost`, `storage_cost`, `compute_cost`, `support_cost`, `payment_fees`, `implementation_cost`, and `acquisition_cost`. Do not infer customer count from downloads or GitHub stars.

```text
gross_margin = (revenue - inference_cost - storage_cost - compute_cost) / revenue
contribution_margin = (revenue - all variable delivery and support costs) / revenue
CAC_payback_months = acquisition_cost / monthly contribution dollars
cost_per_accepted_outcome = all variable execution costs / verified accepted outcomes
```

Suggested pilot pricing is a test, not a published offer: fixed-fee integration and evidence review, then a subscription with included retained events and transparent overage pricing. Set actual prices after measuring pilot delivery cost, willingness to pay, and support load. A useful gate is positive contribution margin for three consecutive months in the same customer cohort before expanding the catalog.

## Licensing and dependency discipline

Use LangChain/LangGraph capabilities where valuable and keep an OpenTelemetry-compatible export so LangSmith remains optional. Keep CrewAI/Paperclip integrations at their public APIs. MiroFish is AGPL-3.0; run any simulation as a separately reviewed service or obtain appropriate rights before redistribution. Simulation outputs are sensitivity explorations, not calibrated predictions or permission to act.
