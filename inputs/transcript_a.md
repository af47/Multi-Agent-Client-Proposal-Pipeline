# Discovery Call — Transcript A

**Date:** April 14, 2026
**Duration:** 32 minutes
**Attendees:** Sarah Chen (VP Operations, Northwind Logistics), Alex Rivera (Consultant)
**Format:** Zoom, audio only
**Source:** Auto-transcribed via Otter, manually cleaned by Alex

---

**Alex:** Hey Sarah, thanks for making the time. Before we dig in, do you have a hard stop?

**Sarah:** I've got 35 minutes. I'd rather use them well than rush, so let's just get into it.

**Alex:** Perfect. So I read the intake form you sent, and I want to make sure I understand the problem from your side before I start pitching anything. Can you walk me through what a typical day looks like for one of your dispatchers right now?

**Sarah:** Sure. So a dispatcher comes in, opens our custom dispatch tool — we call it Routemaster internally — and they start the day looking at loads that need coverage. They see a list of available drivers, available trucks, and the loads. The dispatcher matches them up. That part actually works fine. The system is ugly but the matching logic is solid because we built it ourselves over seven years.

**Alex:** Okay.

**Sarah:** The problem starts the moment they make a match. The dispatcher then has to manually go into Salesforce and update the opportunity record with the truck assignment, the driver, the pickup time, and the rate. Then they have to send the load tender to the customer, which is a separate workflow. Then they have to ping the driver through our mobile app — which the driver may or may not see. So it's three systems for one assignment, and the dispatcher is the integration layer.

**Alex:** How many of those assignments does a single dispatcher do per day?

**Sarah:** Sixty to ninety. Per dispatcher. And we have forty dispatchers.

**Alex:** That's a lot of double-entry.

**Sarah:** That's the first problem. The second problem is the driver app. We built it in 2023 and it hasn't really been touched since. Drivers can see their assigned load, accept it, and update status — at-pickup, loaded, at-delivery, delivered. That's it. They can't take photos, they can't flag issues, they can't message the dispatcher. So what happens is drivers fall back to phone calls. Every dispatcher tells me they spend two to three hours a day on the phone with drivers because the app doesn't do what they need.

**Alex:** Got it. And the third one is invoicing?

**Sarah:** Yeah, and this one is what's actually putting us at risk. So when a load is delivered, the driver marks it delivered in the app, the dispatcher confirms it in Routemaster, and then someone in finance has to reconcile the rate confirmation, the bill of lading, the actual delivery time, and any accessorials before they can invoice. Right now they're three weeks behind. Three weeks of revenue we should have invoiced is just sitting there.

**Alex:** Why three weeks?

**Sarah:** Because the data doesn't line up. The driver might mark a load delivered at 2pm in the app, but the actual proof of delivery shows 4pm, and the dispatcher entered 3:30 in Routemaster, and the rate confirmation has a different load number than what's in Salesforce because the dispatcher mistyped it. So finance is doing detective work on every single invoice. They have one person doing it full-time and she's drowning.

**Alex:** Okay. Let me play that back to make sure I have it right. You've got three problems. One: dispatcher double-entry between Routemaster, Salesforce, and the driver app. Two: the driver app is too thin, so drivers fall back to phones. Three: invoicing is broken because reconciliation is manual and error-prone, and finance is three weeks behind.

**Sarah:** That's exactly right.

**Alex:** If you had to rank those by what would unblock the most value, what's the order?

**Sarah:** Honestly, invoicing is the bleeding wound. We need to fix that first. Three weeks of A/R behind is real money and it's getting worse. Second is the dispatcher workflow — that's the source of the bad data that breaks invoicing, so fixing it would also fix invoicing over time, but it'll take longer to ship. Third is the driver app. It's a quality-of-life issue but it's not on fire.

**Alex:** That's helpful. So the order is: invoicing reconciliation first because it's a cash flow problem, then dispatcher workflow because it's the upstream cause, then driver app because it's the lowest urgency even though dispatchers complain about it loudest.

**Sarah:** Yes. And to be clear — I want all three eventually. I just don't think we should boil the ocean.

**Alex:** Agreed. Let me ask about constraints. You mentioned in the intake form a Q3 pilot and a six-month Phase 1. Tell me more about how those numbers got set.

**Sarah:** Q3 is because Rita — our CFO — agreed to the budget on the condition that we have something measurable in production by end of September. Otherwise the funding gets pulled into other projects. The six months is roughly what I told her I thought we'd need to make a real dent. It's not a hard number, it's a budgeting horizon.

**Alex:** And on the budget itself?

**Sarah:** I've earmarked $250,000 to $400,000 for Phase 1, depending on scope. Rita knows the range. I'd rather come in at the lower end and earn the next phase than overpromise. We've been burned by vendors who quoted big and delivered late.

**Alex:** Understood. And what would success look like — not for the whole engagement, but for Phase 1 specifically? If we shipped something in Q3 that you'd consider a win, what does that look like?

**Sarah:** I've been thinking about this. I think the cleanest metric is dispatch time per load. Right now our average dispatcher takes about twelve minutes to fully process a load through all three systems. If we can get that to eight minutes — call it a thirty percent reduction — that's a real productivity win and it pays for itself in headcount we don't have to hire next year. And if we fix invoicing reconciliation, the secondary metric is days-sales-outstanding, which should drop from where we are now back to industry standard, which is about five days.

**Alex:** Those are concrete and they're measurable. I appreciate that. A lot of clients give us "improve efficiency" and we have to invent the metric.

**Sarah:** I learned that the hard way.

**Alex:** Decision process. You're the champion, Marcus is the CTO, Rita is the CFO. Walk me through how a yes happens.

**Sarah:** I run discovery with you, you put together a proposal, I share it with Marcus and Rita. Marcus will want to dig into the technical approach — he has strong opinions about Routemaster because he built half of it. Rita will want to see the milestone payments and the success metrics tied to dollars. If they're both okay with it, we move. I have authority to sign once they've blessed it.

**Alex:** How likely is Marcus to want to rebuild Routemaster from scratch?

**Sarah:** [pause] Pretty likely. He's been pushing for that for a year. I want to be honest with you — that's a fight I've been having internally, and I need a partner who can help me make the case for incremental change instead of a full rebuild. The rebuild is a 12-month project minimum and we don't have 12 months.

**Alex:** Got it. That's useful to know. I'll make sure the proposal addresses the rebuild question head-on rather than ducking it.

**Sarah:** Please do.

**Alex:** Last question. Are you talking to other firms?

**Sarah:** Two others. I'm being upfront about that. You're at the top of my list because of the Cascade Freight work, but I owe Rita due diligence.

**Alex:** That's fair. Thank you for being straight about it. I'll have a draft proposal to you by end of next week. Anything else I should know before I start writing?

**Sarah:** One thing. There's an ELD compliance deadline in November — federal mandate update. Rajiv, our head of compliance, owns it. It's not officially in scope for this engagement, but if your approach can avoid creating new compliance work for him, that's a quiet point in your favor.

**Alex:** Noted. I won't bake it into Phase 1 but I'll flag it as something to consider.

**Sarah:** Perfect. Thanks Alex.

**Alex:** Thanks Sarah. Talk soon.

[Call ends — 32:14]
