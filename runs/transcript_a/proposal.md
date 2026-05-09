# Client Proposal: Northwind Logistics Workflow Automation & System Integration

**Prepared for:** Sarah Chen, VP of Operations  
**Date:** 2025  
**Engagement Duration:** 6 months (Phase 1)  
**Target Completion:** Q3 2025 (September 30)

---

## Executive Summary

Northwind Logistics is experiencing operational scaling bottlenecks following 40% growth in 2024. Manual workflows across three disconnected systems—Routemaster (custom Rails dispatch tool), Salesforce, and a driver mobile app—are creating two critical problems:

1. **Cash flow drag:** Invoicing reconciliation is 3 weeks behind due to data mismatches across systems, delaying accounts receivable and creating significant working capital pressure.
2. **Operational inefficiency:** 40 dispatchers spend an average of 12 minutes per load assignment manually entering data across three systems (60–90 loads per dispatcher per day), plus 2–3 hours per day on phone calls with drivers due to limited mobile app functionality.

This proposal outlines a **6-month Phase 1 engagement** to deliver measurable operational improvements through incremental system integration and workflow automation:

- **30% reduction in dispatch time per load** (from 12 minutes to 8 minutes), paying for itself in avoided headcount growth
- **Reduction in days-sales-outstanding (DSO) to ~5 days** (industry standard), eliminating the 3-week invoicing backlog
- **Pilot in production by September 30, 2025** to meet CFO funding requirements
- **Fixed-fee milestone structure** with measurable success criteria tied to operational and financial metrics

Our approach prioritizes incremental integration over full platform rebuild, delivering measurable ROI within the 6-month timeline while positioning Northwind for Phase 2 expansion.

---

## Understanding

### Business Context

Northwind Logistics has grown rapidly—40% in 2024 through the acquisition of two smaller brokerages—but operational systems have not kept pace. The result is a scaling crisis:

- **Finance is drowning:** One person is doing full-time invoice reconciliation detective work, manually resolving data mismatches (delivery times, load numbers, rate confirmations) across three systems. Three weeks of revenue sits uninvoiced, creating a cash flow problem.
- **Dispatchers are the integration layer:** 40 dispatchers manually enter the same load assignment data into Routemaster, Salesforce, and the driver mobile app—averaging 12 minutes per load for 60–90 loads per day. This triple-entry workflow is the upstream source of the bad data that breaks invoicing.
- **Drivers fall back to phone calls:** The driver mobile app is too thin (no photo upload, issue flagging, or dispatcher messaging), forcing dispatchers to spend 2–3 hours per day on phone calls.

The current state is unsustainable. Without workflow automation, Northwind will need to hire additional dispatchers and finance staff to maintain operations—negating the efficiency gains from growth.

### Pain Points (Priority Order)

1. **Invoicing reconciliation (bleeding wound):** 3-week backlog caused by data mismatches is delaying cash flow and consuming full-time finance resources.
2. **Dispatcher workflow (upstream cause):** Manual triple-entry across systems creates the bad data that breaks invoicing. Fixing this fixes invoicing over time.
3. **Driver mobile app (quality of life):** Limited functionality forces phone-based workarounds, but this is not on fire relative to the first two issues.

### Success Criteria

Phase 1 success is defined by measurable operational and financial metrics:

1. **30% reduction in dispatch time per load** (from 12 minutes to 8 minutes), paying for itself in headcount savings
2. **DSO reduction to ~5 days** (industry standard), eliminating the 3-week invoicing backlog
3. **Pilot in production by September 30, 2025** (Q3 end) to retain CFO funding approval
4. **Measurable ROI** that justifies Phase 2 investment and earns stakeholder confidence

### Stakeholder Landscape

This engagement requires alignment across three key stakeholders with different priorities:

- **Sarah Chen (VP Operations, sponsor):** Needs incremental wins that deliver measurable ROI within 6 months. Prefers phased approach over full rebuild.
- **Rita Donovan (CFO, budget authority):** Skeptical of consulting engagements after being burned by a previous vendor in 2023. Requires fixed-fee with milestone payments and success metrics tied to dollars. Funding will be pulled if Q3 pilot deadline is missed.
- **Marcus Patel (CTO, technical sign-off):** Built half of Routemaster and has been pushing for a full platform rebuild for a year. Skeptical of incremental fixes. Required for technical approval.

Our proposal must address the rebuild question head-on and make the case for incremental integration that satisfies all three stakeholders.

### Technical Landscape

- **Routemaster (custom Rails 5 dispatch tool):** ~7 years old, maintained by only 2 engineers, no integration with Salesforce or driver app
- **Salesforce:** CRM and opportunity management, manually updated by dispatchers
- **Driver mobile app (React Native):** Last updated 2023, supports load assignment and status updates only—no photos, issue flagging, or messaging
- **~600 contracted drivers** must adopt any enhanced mobile app functionality
- **TMS vendor evaluation in progress:** No selection made yet; unclear how this impacts integration architecture
- **ELD compliance deadline (November):** Federal mandate update owned by Rajiv Mehta (Head of Compliance); not officially in scope but solution must avoid creating new compliance work

---

## Approach

### Philosophy: Incremental Integration Over Full Rebuild

We understand the tension between incremental improvement and full platform rebuild. Marcus has been advocating for a Routemaster rebuild for a year, and from a technical purity standpoint, that instinct is sound—legacy Rails 5 systems maintained by two engineers are inherently fragile.

However, **a full rebuild is a 12+ month project** that does not align with the Q3 pilot deadline, CFO funding constraints, or the urgency of the invoicing crisis. Our approach is to:

1. **Deliver measurable ROI in 6 months** through targeted integration and workflow automation
2. **Preserve optionality for future rebuild or TMS migration** by designing integrations that are modular and decoupled from Routemaster's internal architecture
3. **Earn Phase 2 funding** by demonstrating operational and financial impact in Phase 1

This is not a band-aid. It is a deliberate strategy to de-risk the business case for modernization by proving value incrementally.

### Technical Strategy

Our integration architecture is designed to **avoid deep coupling with Routemaster** while enabling automated data flow across systems:

1. **Event-driven integration layer:** Build a lightweight middleware service (Node.js or Python) that listens for events from Routemaster (load assignment, status change) and propagates updates to Salesforce and the driver app via APIs. This avoids modifying Routemaster's core codebase and preserves optionality for future TMS migration.
2. **Salesforce API integration:** Automate load assignment updates to Salesforce opportunity records, eliminating manual dispatcher entry.
3. **Driver mobile app enhancements:** Add photo upload, issue flagging, and dispatcher messaging to reduce phone call volume. These features will be built as new React Native components that integrate with the existing app architecture.
4. **Invoicing reconciliation automation:** Build a reconciliation engine that cross-references data from Routemaster, Salesforce, and the driver app, flags mismatches, and auto-resolves common discrepancies (e.g., timestamp normalization, load number fuzzy matching). This addresses the bleeding wound while the upstream dispatcher workflow improvements take effect.

This approach is **modular and reversible**. If Northwind selects a TMS vendor or proceeds with a Routemaster rebuild in Phase 2, the integration layer can be adapted or retired without stranding investment.

### Operational Strategy

Workflow automation only delivers ROI if dispatchers and drivers adopt it. Our operational strategy includes:

1. **Dispatcher workflow redesign:** Map current 12-minute dispatch process, identify automation opportunities, and design new workflow that reduces time to 8 minutes. This includes training materials and change management.
2. **Pilot cohort approach:** Launch with a small cohort of dispatchers (5–10) to validate workflow improvements, gather feedback, and refine before full rollout.
3. **Driver mobile app adoption plan:** Communicate enhancements to ~600 contracted drivers, provide in-app onboarding, and monitor adoption metrics (photo upload rate, messaging usage).
4. **Finance reconciliation handoff:** Train finance team on new reconciliation engine, establish escalation workflows for edge cases, and measure backlog reduction weekly.

Dispatcher adoption is the critical success factor. We will include a detailed training and change management plan in the engagement.

### Risk Mitigation

We have identified the following risks and mitigation strategies:

| Risk | Mitigation |
|------|------------|
| **Legacy data quality issues in Routemaster** | Conduct data quality audit in discovery phase; build reconciliation engine with fuzzy matching and manual override workflows |
| **CTO skepticism of incremental approach** | Involve Marcus in technical design reviews; demonstrate how integration layer preserves optionality for future rebuild/TMS migration |
| **Dispatcher adoption failure** | Pilot cohort approach with feedback loops; include dispatchers in workflow redesign; measure adoption metrics weekly |
| **TMS vendor selection disrupts architecture** | Design integration layer to be TMS-agnostic; avoid deep coupling with Routemaster internals |
| **Incomplete tech integration from 2024 acquisitions** | Discovery phase includes data consistency audit across legacy systems from acquired brokerages |
| **ELD compliance deadline (November) creates scope creep** | Confirm with Rajiv Mehta that integration approach does not create new compliance work; keep ELD mandate explicitly out of scope |
| **Q3 pilot deadline missed, CFO pulls funding** | Aggressive milestone tracking; weekly status updates; escalation protocol for blockers |

---

## Phases & Timeline

### Phase 1: 6-Month Engagement (Target Completion: September 30, 2025)

**Month 1: Discovery & Design**
- Stakeholder interviews (Sarah, Marcus, Rita, Rajiv, finance team, dispatcher cohort)
- Technical architecture assessment (Routemaster, Salesforce, driver app APIs)
- Data quality audit (Routemaster, acquisition system integration, common mismatch patterns)
- Workflow mapping (current 12-minute dispatch process, invoicing reconciliation detective work)
- Integration architecture design (event-driven middleware, API contracts)
- Dispatcher workflow redesign (target 8-minute process)
- Driver mobile app feature specification (photo upload, issue flagging, messaging)
- Reconciliation engine logic design (auto-resolve rules, manual override workflows)
- **Deliverable:** Technical design document, workflow redesign, project plan with success metrics

**Months 2–3: Build & Integration**
- Build integration middleware (event listeners, Salesforce API integration, driver app API integration)
- Develop invoicing reconciliation engine (mismatch detection, auto-resolve logic, manual override UI)
- Enhance driver mobile app (photo upload, issue flagging, dispatcher messaging)
- Build dispatcher workflow automation (single-entry load assignment, auto-propagation to Salesforce and driver app)
- Unit testing and integration testing
- **Deliverable:** Working integration layer, reconciliation engine, enhanced driver app (staging environment)

**Month 4: Pilot Launch**
- Deploy to pilot cohort (5–10 dispatchers, subset of drivers)
- Dispatcher training and onboarding
- Driver mobile app rollout communication and in-app onboarding
- Finance team training on reconciliation engine
- Monitor adoption metrics (dispatch time per load, reconciliation backlog, driver app usage)
- Gather feedback and iterate
- **Deliverable:** Pilot in production, adoption metrics dashboard, feedback report

**Month 5: Refinement & Rollout**
- Address pilot feedback (workflow adjustments, bug fixes, UX improvements)
- Full rollout to all 40 dispatchers and ~600 drivers
- Finance reconciliation engine in full production
- Monitor success metrics (dispatch time, DSO, invoicing backlog)
- **Deliverable:** Full production rollout, success metrics report

**Month 6: Measurement & Phase 2 Planning**
- Measure Phase 1 success criteria (30% dispatch time reduction, DSO reduction to ~5 days)
- Document ROI (headcount savings, cash flow improvement)
- Conduct retrospective with stakeholders
- Develop Phase 2 roadmap (additional automation opportunities, TMS migration planning, full driver app rebuild, etc.)
- **Deliverable:** Phase 1 success report, ROI analysis, Phase 2 proposal

### Key Milestones

1. **End of Month 1:** Technical design and workflow redesign approved by Marcus and Sarah
2. **End of Month 3:** Integration layer and reconciliation engine built and tested in staging
3. **End of Month 4:** Pilot in production with measurable adoption metrics
4. **September 30, 2025 (Q3 end):** Full production rollout complete, success metrics measured

---

## Pricing Approach

### Fixed-Fee Structure: $295,000

We propose a **fixed-fee engagement of $295,000** for the 6-month Phase 1 scope outlined above. This fee is structured around three milestone payments to align with delivery and reduce client risk:

| Milestone | Deliverable | Payment | Timeline |
|-----------|-------------|---------|----------|
| **Milestone 1: Discovery & Design Complete** | Technical design document, workflow redesign, project plan approved by Marcus and Sarah | $118,000 (40%) | End of Month 1 |
| **Milestone 2: Pilot in Production** | Integration layer, reconciliation engine, and enhanced driver app deployed to pilot cohort; adoption metrics dashboard live | $118,000 (40%) | End of Month 4 |
| **Milestone 3: Full Rollout & Success Metrics** | Full production rollout to all dispatchers and drivers; Phase 1 success criteria measured and documented | $59,000 (20%) | End of Month 6 (Sept 30) |

### Pricing Methodology

Our fee is based on transparent cost-build methodology:

- **Discovery & Design (Month 1):** ~240 hours (senior consultant + technical architect) at blended rate of ~$3,200/day = $96,000
- **Build & Integration (Months 2–3):** ~480 hours (technical architect + 2 engineers) at blended rate of ~$2,900/day = $116,000
- **Pilot Launch & Rollout (Months 4–5):** ~320 hours (project lead + engineer + change management) at blended rate of ~$3,000/day = $64,000
- **Measurement & Phase 2 Planning (Month 6):** ~80 hours (senior consultant + project lead) at blended rate of ~$3,400/day = $19,000
- **Total:** $295,000

This pricing reflects:
- Senior consultant day rates in the $2,800–$3,800 range (industry standard for freight brokerage workflow automation)
- Fixed-fee structure with milestone payments (strongly preferred by mid-market freight brokers per industry benchmarks)
- Risk buffer for legacy data quality issues and dispatcher adoption challenges

### Benchmark Context

Industry benchmarks for 6-month workflow automation and system integration engagements in the freight brokerage sector show:

- **p25:** $180,000 (smaller scope, fewer systems)
- **p50:** $300,000 (median for mid-market brokers)
- **p75:** $480,000 (larger scope, full TMS implementation)
- **p90:** $750,000 (enterprise-scale transformation)

Our proposed fee of **$295,000 sits just below the median**, reflecting the focused scope (invoicing reconciliation + dispatcher workflow + driver app enhancements) and 6-month timeline. This pricing is consistent with mid-market freight broker budgets of $250k–$400k for similar engagements.

Typical ROI for invoicing/reconciliation automation in this segment is realized within 90 days through improved cash flow and reduced finance labor.

### What's Included

- Technical architecture design and integration development
- Invoicing reconciliation engine (auto-resolve logic, manual override workflows)
- Driver mobile app enhancements (photo upload, issue flagging, dispatcher messaging)
- Dispatcher workflow redesign and automation
- Pilot launch and full rollout (all 40 dispatchers, ~600 drivers)
- Training and change management (dispatchers, drivers, finance team)
- Weekly status updates and stakeholder communication
- Phase 1 success measurement and ROI documentation
- Phase 2 roadmap and proposal

### What's Not Included (Out of Scope)

- Full Routemaster rebuild or replacement
- TMS vendor selection or implementation
- ELD compliance mandate work (November deadline)
- Tech integration of 2024 acquisition systems (unless directly impacting Phase 1 scope)
- Ongoing maintenance or support beyond Phase 1 (can be addressed in Phase 2)

---

## Open Questions

The following items require clarification before finalizing the engagement:

### 1. Budget Alignment and Approval Authority

There appears to be a discrepancy in budget expectations:

- **Sarah's stated range:** $250,000–$400,000 for Phase 1 (per discovery transcript)
- **CRM risk flag:** Rita has a $300,000 hard cap, and a budget disagreement exists between Sarah and Rita

Our proposed fee of **$295,000** is below the $300,000 cap indicated in the CRM, but we need clarity on:

- **Which budget authority is correct?** Does Rita's $300k cap override Sarah's stated $250k–$400k range?
- **Does $295,000 require approval from both Sarah and Rita?** If so, what is the approval process and timeline?
- **Is there flexibility in the $300k cap if scope adjustments are needed?**

We recommend a three-way conversation (Sarah, Rita, and our team) to align on budget before proceeding to contract.

### 2. TMS Vendor Selection Timeline and Impact

A TMS vendor evaluation is currently in progress, but no selection has been made. We need to understand:

- **What is the expected timeline for TMS vendor selection?**
- **If a TMS is selected during Phase 1, how does that impact the integration architecture?** Our approach is designed to be TMS-agnostic, but we need to confirm this does not create rework.
- **Should we plan for TMS migration in Phase 2, or is the TMS evaluation separate from this engagement?**

### 3. ELD Compliance Deadline (November) and Scope Boundaries

The ELD compliance mandate (federal update, November deadline) is owned by Rajiv Mehta and is not officially in scope for this engagement. However, we need to confirm:

- **What are the details of the ELD compliance deadline?** (Sarah indicated details would be discussed on a follow-up call)
- **Does our integration approach create any new compliance work for Rajiv?** We want to avoid this, but need technical details to confirm.
- **Is there any overlap between ELD compliance and the driver mobile app enhancements?** (e.g., if ELD data needs to flow through the app)

### 4. Data Quality Audit Scope for 2024 Acquisitions

Northwind acquired two smaller brokerages in 2024, and tech integration from those acquisitions is incomplete. We need to understand:

- **What systems did the acquired brokerages use for dispatch, CRM, and driver management?**
- **Is data from those systems now in Routemaster and Salesforce, or are there parallel systems still running?**
- **Are there known data inconsistencies (e.g., duplicate load numbers, mismatched customer records) that could impact invoicing reconciliation?**

We will conduct a data quality audit in Month 1, but advance visibility into acquisition system integration will help us scope the effort accurately.

### 5. Dispatcher Training and Change Management Ownership

Dispatcher adoption is the critical success factor for this engagement. We need to clarify:

- **Who owns dispatcher training and change management on the Northwind side?** (Sarah, operations manager, dispatcher lead?)
- **What is the current dispatcher onboarding and training process?** (We will build on existing processes rather than creating net-new training infrastructure)
- **Are there any known dispatcher resistance or change fatigue issues we should plan for?**

### 6. Marcus Sign-Off Process and Technical Review Cadence

Marcus (CTO) is required for technical sign-off and has been advocating for a full Routemaster rebuild. To ensure alignment:

- **What is Marcus's preferred technical review cadence?** (Weekly architecture reviews, milestone-based reviews, ad hoc?)
- **Are there specific technical concerns or non-negotiables Marcus has flagged about incremental integration?**
- **Who else on Marcus's team should be involved in technical design reviews?** (e.g., the two engineers maintaining Routemaster)

### 7. Success Metrics Baseline and Measurement

To measure Phase 1 success, we need baseline data:

- **Current average dispatch time per load:** Confirmed as 12 minutes, but is this measured/tracked, or anecdotal?
- **Current DSO (days-sales-outstanding):** Target is ~5 days (industry standard), but what is the current DSO? (We know invoicing is 3 weeks behind, but DSO may be a different metric)
- **Current invoicing backlog:** Confirmed as 3 weeks, but how is this measured? (Number of uninvoiced loads? Dollar value of uninvoiced revenue?)

We will establish measurement protocols in Month 1, but advance clarity on current metrics will help us set realistic targets.

---

**Next Steps:**

We propose a follow-up call with Sarah, Marcus, and Rita to:

1. Align on budget and approval process
2. Review technical approach and address Marcus's rebuild concerns
3. Clarify open questions above
4. Finalize engagement scope and timeline

We are ready to move quickly to meet the Q3 pilot deadline. Please let us know your availability for a stakeholder alignment call.

---

**Prepared by:** [Your Firm Name]  
**Contact:** [Your Name, Title, Email, Phone]