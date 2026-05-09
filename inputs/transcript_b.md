# Discovery Call — Transcript B

**Date:** April 21, 2026
**Duration:** 64 minutes
**Attendees:** Sarah Chen (VP Operations), Marcus Patel (CTO), Rita Donovan (CFO), Alex Rivera (Consultant)
**Format:** Zoom, video on
**Source:** Auto-transcribed via Otter, manually cleaned by Alex

---

**Alex:** Hey everyone, thanks for making the time. Sarah, I had a great call with you last week. I thought today the goal was to get Marcus and Rita's perspective so I can put together a proposal that actually works for all three of you. Does that sound right?

**Sarah:** That's right. Marcus, Rita — Alex came highly recommended from the Cascade Freight engagement. I wanted you both to hear his approach directly before we move forward.

**Rita:** Before we start, I want to set expectations. We are not signing anything today. We are not committing to a number today. I have been burned by this exact conversation before. I'm here to listen.

**Alex:** Completely understood. I'm not here to close anything. I'm here to listen and ask questions. Marcus, Rita, anything either of you want me to know upfront before we dig in?

**Marcus:** Yeah, actually. Sarah and I have been having a parallel conversation about this for months and we don't agree on what the problem is. So I want to make sure my view is on the table. Sarah thinks this is a workflow problem. I think this is a platform problem. Routemaster is seven years old, it was built by two engineers including me back when we were a 50-person company, and it's at the end of its useful life. We can put a band-aid on the dispatcher workflow but in two years we'll be back here having the same conversation about the next workflow.

**Sarah:** Marcus —

**Marcus:** Let me finish. I had a demo last week from a vendor — I won't name them — that does dispatch-as-a-service, full SaaS platform, integrates with Salesforce out of the box, mobile app included, the works. We could be live on it in nine months and we'd never have to maintain Routemaster again.

**Rita:** What's the cost on that?

**Marcus:** Their list price is $400k a year ongoing plus $200k implementation. So in year one, about $600k. But after that it's $400k a year forever and we cut the two engineers who maintain Routemaster.

**Rita:** $600k in year one?

**Marcus:** Yes.

**Rita:** Marcus, the budget I approved is $300,000. That's the cap.

**Sarah:** Rita, that's not what we discussed. We discussed a six-month Phase 1 in the $250 to $400 range, with a Phase 2 to be scoped later.

**Rita:** I approved a six-month engagement up to $300k. If you have notes from a different conversation I'd like to see them.

**Sarah:** [pause] Okay, we can resolve that offline. The point is, Marcus, $600k is not in scope for what we're talking about today.

**Marcus:** That's exactly my problem. We're scoping the wrong thing. We're scoping a band-aid because we set a budget that only buys a band-aid.

**Alex:** Can I jump in for a second? I want to make sure I understand both views before this becomes a debate. Marcus, your position is that the right move is to replace Routemaster with a SaaS platform, and the budget conversation should start from "what does the right answer cost" rather than "what fits in $300k." Is that fair?

**Marcus:** That's fair.

**Alex:** And Sarah, your position is that you want to fix three specific operational pain points — dispatcher double-entry, the driver app, and invoicing — incrementally, within the budget Rita has signaled, and the Routemaster question is a separate conversation that doesn't need to be answered now.

**Sarah:** Yes. And I'll add — even if Marcus is right that we eventually need to replace Routemaster, we can't do it in the timeline we have. We have a Q3 pilot commitment.

**Marcus:** Q3 was your commitment, not mine. I never agreed to Q3. I think Q4 is more realistic if we're doing it right.

**Sarah:** Marcus, the Q3 date came from Rita. It wasn't mine.

**Rita:** That's correct. Q3 is a budget cycle thing. If we don't have something in production by end of September, the funding gets reallocated. That part isn't negotiable.

**Marcus:** Then we shouldn't be doing this at all. We should not be making a multi-year platform decision under an artificial six-month deadline.

**Rita:** Then what are we doing here, Marcus?

**Marcus:** [pause] I don't know. I'm raising a concern. I'm saying if we sign a $300k consulting engagement to fix workflows on a platform we're going to throw away in two years, we're wasting $300k.

**Sarah:** And I'm saying we're not throwing it away in two years, and even if we are, the workflow fixes are needed regardless because the dispatchers can't keep working this way.

**Alex:** Let me ask a different question. Forget the platform decision for a second. Marcus, do you agree that the three problems Sarah described — dispatcher double-entry, the driver app, and invoicing reconciliation — are real problems?

**Marcus:** They're real. I just don't agree they're the most important problems.

**Alex:** What is the most important problem, in your view?

**Marcus:** Technical debt in Routemaster. We can't ship features anymore because the codebase is too fragile. Every change takes three times as long as it should.

**Sarah:** Marcus, that's a problem for your team. That's not a problem the business feels.

**Marcus:** The business feels it every time you ask me for a feature and I tell you it'll take six weeks.

**Rita:** I want to bring this back to something concrete. Alex, what would you actually deliver in six months for $300k?

**Alex:** Honestly Rita, I don't know yet. I want to scope it properly before I quote it. Based on what Sarah described last week, I'd want to focus on the invoicing reconciliation first because that's directly affecting cash flow, and then the dispatcher workflow because it's the upstream cause of the bad invoicing data. The driver app I'd defer.

**Rita:** Defer means you're not doing it?

**Alex:** Defer means I'd put it in a Phase 2 conversation, not Phase 1.

**Rita:** Okay. And what's the ROI?

**Alex:** Sarah and I talked about a 30% reduction in dispatch time per load and a return to industry-standard DSO on the invoicing side.

**Rita:** What's that worth in dollars?

**Sarah:** I can pull the numbers. Roughly, a 30% reduction in dispatch time means we don't need to hire four additional dispatchers next year, which is about $320k in fully-loaded comp. And a return to five-day DSO from where we are now frees up about $1.4M in working capital that's currently stuck in unbilled receivables.

**Rita:** Okay, those are real numbers. Why didn't you lead with those?

**Sarah:** I wanted Alex to walk you through it.

**Marcus:** Those numbers assume the workflow fixes actually work. We've tried internal projects to fix this exact thing twice and they both failed. What's different this time?

**Alex:** Fair question. The two things that are different — and I want to be honest, I might be wrong — are: one, an outside team isn't subject to the political pressure of being told to fix something while also maintaining the rest of the system. And two, we'd be building this with an explicit eye toward whatever Routemaster's eventual replacement looks like, so the work isn't wasted if the platform decision changes later.

**Marcus:** That's actually a reasonable answer.

**Sarah:** I want to add one more thing. The ELD compliance deadline in November is real. The federal mandate update changes how we have to log driver hours and report them. Rajiv has flagged it but we haven't built anything for it yet.

**Marcus:** Wait, when did this become in scope?

**Sarah:** It's not in scope. I'm flagging it because whatever we build needs to not get in the way of the compliance work.

**Marcus:** That's a totally different system. The ELD work is in the driver app, which Alex just said he's deferring.

**Sarah:** Right, but if we touch the driver app at all in Phase 2, we need to do it in a way that supports ELD.

**Rita:** When is the November deadline?

**Sarah:** November 15th.

**Rita:** And what happens if we miss it?

**Sarah:** Fines, possibly losing our operating authority in some states. Rajiv has the details.

**Rita:** This is the first I'm hearing about a November deadline that could affect our operating authority. Why is this not the top priority?

**Sarah:** It is a top priority. Rajiv is on it. It's just a separate workstream from what we're talking about with Alex.

**Marcus:** Is it though? If we're going to touch the driver app, the ELD work has to be coordinated.

**Alex:** I'm going to be honest, I need to learn more about the ELD work before I can speak to that. Can I get fifteen minutes with Rajiv before I write the proposal?

**Sarah:** Yes, I'll set it up.

**Rita:** Alex, I want to ask you something directly. Sarah told me you're talking to two other firms. Why should we pick you?

**Alex:** Honestly Rita, you should pick whoever can give you the most credible plan to hit the Q3 pilot inside the budget you've authorized. I think that's me because we did almost this exact engagement at Cascade Freight last year and I can show you the results. But I'm not going to pretend I'm the only option.

**Rita:** That was a non-answer.

**Alex:** [pause] Fair. The honest answer is: I'll give you a fixed-fee proposal with milestone payments tied to specific outcomes, and if we miss the milestones you don't pay for them. I don't think the other firms will do that.

**Rita:** Now we're talking.

**Marcus:** I want to come back to the platform question. If we go down this path with Alex and in twelve months we decide to replace Routemaster anyway, how much of the work is wasted?

**Alex:** If we build it the way I have in mind — workflow logic in a layer on top of Routemaster, talking to Salesforce and the driver app through clean integration points — then most of the workflow logic is portable. The pieces that touch Routemaster directly would have to be rewritten, but those are a minority of the work. I'd estimate 60-70% of the Phase 1 work survives a platform change.

**Marcus:** That's better than I expected. I'd want to see the architecture before I sign off on that number.

**Alex:** Of course.

**Sarah:** Alex, what do you need from us to put together the proposal?

**Alex:** Fifteen minutes with Rajiv on the ELD work. Read access to Routemaster — at least the schema and a representative slice of the data. And I'd like a follow-up call with the three of you next week to walk through the draft before I send a final.

**Rita:** I can give you thirty minutes next Friday.

**Sarah:** I'll get you the Rajiv intro and the Routemaster access this week.

**Marcus:** I want to be in the room when you walk through the architecture.

**Alex:** Absolutely.

**Rita:** Alex, one more thing. I want a number in the proposal. Not a range. A number.

**Alex:** Understood. I'll commit to a number.

**Sarah:** I think we've got what we need. Anything else from anyone?

**Marcus:** Just to be clear, I'm not opposed to this. I'm skeptical, but I'm not opposed.

**Rita:** Same.

**Sarah:** Good. Alex, thanks. Talk Friday.

**Alex:** Thanks everyone.

[Call ends — 1:04:23]

---

**Alex's notes (added after the call):**
- Q3 vs Q4 deadline: unresolved between Sarah and Marcus. Rita confirmed Q3 is hard.
- Budget: Rita says $300k cap, Sarah remembers $250-400k range. Resolve before proposal.
- Platform replacement: Marcus wants it, Sarah doesn't, Rita unaware of cost implications. Proposal must address.
- ELD compliance Nov 15: surfaced for first time. Critical. Need Rajiv intro.
- Driver app: Sarah says defer, but Marcus correctly notes it overlaps with ELD work.
- Success metrics: Sarah's numbers (4 dispatchers @ $320k, $1.4M working capital) landed well with Rita. Lead with those.
- Marcus's "twice failed before" comment is the real risk. Proposal needs to address why this time is different.
- Rita wants: fixed fee, milestone payments, single number, accountability for missed milestones.
