# Crescopus — Master Spec (current state)

This is the definitive, consolidated spec for what Crescopus is being built
to do, superseding prior version documents. It describes the product as it
stands now — not the history of how it got here.

---

## 1. What Crescopus is

Crescopus connects app developers ("**Builders**") with growth/marketing
people ("**Growers**") to explore and formalise collaboration. The
relationship between a Builder and Grower is a **CrescoPact**. Crescopus's
role is to facilitate discovery, negotiation, and verified growth data
between the two parties — **never to move money, hold equity, or mediate
ownership.**

---

## 2. Accounts and matching

- Accounts are **single-role**: Builder or Grower, not both.
- Either side can initiate a search and reach out to the other.

---

## 3. The CrescoPact lifecycle

1. **Ice-breaker connection.** Either party finds and connects with the
   other.
2. **Trial CrescoPact.** Formed automatically on connection acceptance.
   Unlocks email reveal and in-app messaging between the two parties.
3. **Negotiation.** Deal type and terms are discussed (Section 4).
4. **Formalise.** Either party can propose formalising the arrangement;
   the other accepts. This moves the CrescoPact from exploratory to
   committed.
5. **Disconnect.** Either party can end a Trial CrescoPact at any point
   before formalising.

CrescoPacts are **opportunities to explore, not enforceable contracts**.
Consent checkboxes appear at each key decision point (connection,
formalise) to keep this framing explicit to both parties.

Partnerships are scoped **per revenue stream**, not per app listing — a
single app can have different Growers attached to different monetisation
channels (e.g. one Grower on store IAP, another on a web subscription
funnel).

---

## 4. Deal terms

Builder and Grower agree the deal type and terms themselves. Crescopus
supports three shapes:

### 4.1 Revenue-share (fully supported)
- Crescopus never moves money. Revenue is either verified via RevenueCat
  (store IAP / web subscriptions) or self-reported by the parties.
- Crescopus computes the agreed split and produces a **settlement
  record** for reference. Actual payment happens off-platform, directly
  between Builder and Grower.
- Terms are set and negotiated via the **CrescoGap slider** (Section 5).

### 4.2 Equity-share (recorded only)
- A CrescoPact can be flagged as equity-share so both parties can
  indicate this is the deal shape in use.
- Crescopus takes **no role** in defining, valuing, drafting, or
  enforcing equity terms. No legal instrument is generated or validated
  by Crescopus.
- This happens entirely off-platform, between the two parties and their
  own advisors.

### 4.3 Combination (not yet supported)
- Not available in the current build. Will be considered once 4.1 and
  4.2 are both live and there's demonstrated demand.

---

## 5. CrescoGap — negotiating revenue-share terms

Applies to revenue-share CrescoPacts (4.1) only.

- **Builder's starting position** — % of revenue the Builder is willing
  to release, set by the Builder.
- **Grower's starting position** — % of revenue the Grower requires
  (typically after "proving," Section 6), set by the Grower.
- **The GAP** — the space between the two positions, and the object of
  negotiation.
- **Both starting positions are visible to both parties from the start.**
  No blind-bid stage.
- **Adjustment is manual**: either party can propose a revised position
  at any time; the other accepts, counters, or leaves it open. Every
  proposal is timestamped and visible to both, following the same
  pattern as the Formalise propose/accept flow.
- All CrescoGap positions remain part of the "opportunity to explore"
  framing (Section 3) — not binding until formalised, and even then not
  an enforceable contract in the traditional sense.

*(Future: an optional mode where verified proving milestones
automatically narrow the gap by a pre-agreed amount, with manual override
always available. Not in the current build.)*

---

## 6. Proving mechanics

A Grower's required position may be conditional on demonstrating growth
("proving") before it applies in full.

- The Builder selects which metric(s) are relevant to their app and sets
  the threshold(s):

  | Tier | Metric |
  |---|---|
  | 1 | Unique visitors |
  | 2 | Registrations / logins |
  | 3 | Subscriptions / activation |
  | 4 | Comments / interactions |

- The Builder specifies the target page(s) to be measured.
- **Verification is via a Crescopus-provided tracking snippet**, embedded
  by the Builder on the specified page(s). Crescopus's own recorded
  number is the source of truth — not a builder-supplied count or
  generic third-party counter — to prevent inflated or gamed figures.
- Reaching an agreed threshold is a milestone visible to both parties. It
  may trigger formalising, a CrescoGap adjustment, or simply inform
  discussion — Crescopus records that a threshold was verified reached;
  it does not adjudicate what that means for the deal.

---

## 7. Growth analytics / RUM (Crescopus's core value-add)

This is Crescopus's product offering to both sides, and the
infrastructure behind proving mechanics (Section 6).

- **Phase 1** (ships with proving mechanics): verified page views and
  unique visitors on Builder-specified pages, via the Crescopus tracking
  snippet.
- **Phase 2** (later): registrations/logins, subscriptions,
  comments/interactions — full Real User Monitoring.

---

## 8. Liability and framing caveats

These apply across the whole platform and should be reflected consistently
in UI copy, terms, and consent points:

- **Crescopus never moves money.** All payment happens off-platform,
  directly between Builder and Grower. Crescopus produces settlement
  records for reference only.
- **Crescopus never holds or mediates equity.** Equity-share CrescoPacts
  are recorded as a flag only; drafting, valuation, and enforcement are
  entirely the parties' responsibility, off-platform.
- **CrescoPacts are opportunities to explore, not enforceable
  contracts**, at every stage including after Formalise. Consent
  checkboxes reinforce this at key decision points.
- **Verified analytics are informational, not guaranteed.** Growth data
  from Crescopus's tracking snippet is provided as a reference point for
  negotiation, not a disputable source of truth Crescopus is liable for.
  This should carry an explicit disclaimer wherever verified metrics are
  shown to users.
- **Revenue-share terms are not equity, ownership, or a security**, and
  product copy should never describe them in language that could be
  read as such.

---

## 9. Open items

- Exact schema for CrescoGap positions, proving thresholds/metrics, and
  tracking snippet data.
- Where in the flow deal-type (4.1 / 4.2) is selected, and whether it can
  change after a Trial CrescoPact has started.
- UI/copy pass across the existing codebase to remove any remaining
  "CrescoShares" language and replace with CrescoGap / revenue-share
  terminology.
- Design of the automatic gap-narrowing mode (deferred, not required for
  current build).
