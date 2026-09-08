# Crescopus SPEC v4 — CrescoGap & Growth Verification

Supersedes the CrescoShares model described in SPEC v3. This spec replaces
CrescoShares with a negotiated split mechanism (**CrescoGap**) and formalises
Crescopus's role as a growth-verification and analytics provider rather than
a party to the financial or ownership terms of a CrescoPact.

---

## 1. Why this change

CrescoShares implied Crescopus had a role in controlling or administering
ownership of the app, which is not the case and was never the intent. The
name and mechanic are retired. In their place:

- Crescopus **never mediates money or equity**. It never has.
- Crescopus's value is **verified growth data** — a neutral record both
  sides can negotiate around, not a financial intermediary.
- The builder and grower **agree the deal terms between themselves**;
  Crescopus provides the negotiation surface (the slider) and, optionally,
  verified metrics to negotiate against.

---

## 2. Deal type: revenue-share, equity-share, or combination

A CrescoPact's financial terms can take one of three shapes. Only the first
is fully supported by Crescopus at launch.

### 2.1 Revenue-share (fully supported, v1)
- Matches SPEC v2's existing model: Crescopus never moves money.
- RevenueCat verifies store IAP / web subscription revenue where
  applicable; other revenue streams are self-reported.
- Crescopus computes the agreed split and produces a settlement record.
  Payment happens off-platform between the two parties.
- This is the only deal type the CrescoGap slider and proving mechanics
  (Sections 3–4) are built for in v1.

### 2.2 Equity-share (recorded, not mediated)
- Crescopus takes **no role** in defining, valuing, drafting, or enforcing
  equity terms. This is a deliberate boundary, not a gap to be filled
  later — equity commitments carry legal/securities complexity that sits
  outside what a CrescoPact ("an opportunity to explore, not an
  enforceable contract") is designed to carry.
- A CrescoPact can be flagged as **equity-share** so both sides can
  indicate this is the deal shape they're pursuing, but:
  - No slider, percentages, or proving mechanics apply.
  - No legal instrument is generated, stored, or validated by Crescopus.
  - Copy should make clear this is between the two parties and their own
    legal advice, entirely off-platform.

### 2.3 Combination
- Deferred. Not supported in v1. Revisit once revenue-share (2.1) and
  equity-share (2.2) both work independently and there's real demand.
  The open problem — how "closing the gap" is even defined when one side
  of the negotiation is a % and the other is equity — needs its own
  design pass rather than being retrofitted onto the slider.

---

## 3. CrescoGap: the negotiation slider

Applies to **revenue-share CrescoPacts only** (Section 2.1).

### 3.1 Core concept
Three numbers, shown as a single visual scale:

- **Builder's starting position** — % of revenue the builder is willing
  to release, set by the builder.
- **Grower's starting position** — % of revenue the grower requires
  after "proving" (Section 4), set by the grower.
- **The GAP** — the negotiating range between the two positions.

### 3.2 Visibility
Both starting positions are **visible to both parties from the outset**.
No blind-bid stage. This fits the platform's existing "opportunities to
explore, discussed openly" framing, and avoids the trust cost of hidden
numbers, at the cost of some anchoring risk — an accepted trade-off.

### 3.3 Adjusting the gap
- **v1: manual only.** Either party can propose a revised position at any
  point; the other accepts, counters, or leaves it open. Every proposal
  is time-stamped and visible to both — same pattern as the existing
  Formalise propose/accept flow.
- **Later phase: automatic narrowing (optional).** Once proving
  milestones (Section 4) are verified, the gap can optionally narrow by a
  pre-agreed amount per milestone, calculated automatically. Manual
  adjustment remains available as a permanent override — automation
  narrows the range, it never finalises a number without one side
  confirming.
- Framing note: all terms, including CrescoGap positions, remain part of
  the "opportunity to explore" — not an enforceable contract — consistent
  with existing CrescoPact liability framing.

---

## 4. Proving mechanics

Applies to revenue-share CrescoPacts where the grower's position depends
on demonstrated growth ("proving").

### 4.1 Metric selection, not a fixed threshold
Rather than a single platform-wide bar (e.g. "10,000 views"), the builder
selects which metric(s) are relevant to their app from a tiered list, and
sets the threshold:

| Tier | Metric | Notes |
|---|---|---|
| 1 | Unique visitors | Harder to game than raw page views; good baseline for pre-revenue apps |
| 2 | Registrations / logins | Signals real intent, not just traffic |
| 3 | Subscriptions / activation | Signals real value created |
| 4 | Comments / interactions | Optional, app-dependent |

A SaaS app might require signups; a content app might require unique
visitors. The builder specifies the target page(s) and the threshold(s)
for whichever metric(s) apply.

### 4.2 Verification: Crescopus as the source of truth
Raw page-view counters (e.g. a builder-supplied number, or a generic
third-party counter) are not trusted as proof — too easy to inflate,
deliberately or accidentally (bots, refresh loops, paid traffic that
never converts).

Instead:
- The builder embeds a **Crescopus-provided tracking snippet** on the
  specified page(s).
- Crescopus becomes the neutral record of the metric, not either party's
  self-reported number.
- This is the same infrastructure as the RUM product (Section 5) — proving
  mechanics and the analytics product are one build, not two.

### 4.3 What "proving" unlocks
Reaching an agreed threshold is a trigger point in the CrescoPact — e.g.
it may be the condition for formalising, for an automatic CrescoGap
narrowing step (3.3), or simply a milestone both parties see and can
discuss. Crescopus records that a threshold was verified reached; it does
not adjudicate disputes about what that means for the deal.

---

## 5. Crescopus's added value: growth analytics / RUM

This is Crescopus's core value-add going forward, replacing "administering
the financial mechanic" as the platform's central offering.

### 5.1 Scope (phased)
- **Phase 1 (ships with proving mechanics, 4.2):** a single tracking
  snippet providing verified page views and unique visitors on
  builder-specified pages. This is the minimum needed to make Section 4
  trustworthy, and the natural starting point.
- **Phase 2:** registrations/logins, subscriptions, comments/interactions
  — full Real User Monitoring, scoped as its own build once Phase 1 is
  proven out.

### 5.2 Liability framing
Because CrescoGap negotiations may lean on Crescopus's verified numbers,
those numbers carry real weight in a financial negotiation even though no
money passes through Crescopus. Extend the existing "opportunity to
explore, not an enforceable contract" framing explicitly to analytics: the
data is information to negotiate around, not a guaranteed, disputable
source of truth Crescopus is on the hook for. Suggest an explicit
disclaimer at the point verified metrics are shown (e.g. "for reference,
not a guarantee").

---

## 6. Open items for next discussion

- Confirm terminology: **CrescoGap** for the negotiation range — anything
  else to rename now that CrescoShares is retired?
- UI/copy pass to make sure "revenue-share" is never described in
  language that reads as equity/ownership, anywhere in the product.
- Where in the CrescoPact flow does deal-type selection (2.1 vs 2.2)
  happen, and can it be changed after a Trial CrescoPact has started?
- Exact mechanics of automatic gap-narrowing (3.3) — deferred design,
  not needed for v1.
- Schema implications: new tables/fields for CrescoGap positions, proving
  thresholds, and tracking snippet data — to be scoped once this spec is
  agreed.
