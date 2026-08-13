# Crescopus — Product Spec (v2)

*Supersedes the original Stripe Connect-based design. This version reflects
the shift to a revenue-reporting model: Crescopus records and verifies
revenue and computes splits; it does not move money.*

## 1. Premise (unchanged)

Crescopus pairs app **developers** — who build but don't want to run growth
or monetisation — with **growers** — who have marketing/commercial skill but
no product of their own. They form a 1:1 partnership: the developer keeps
ownership, the grower earns a share of the revenue they help generate.

## 2. Core entities

```
profiles
  └─ is_developer, is_grower (a person can be both), country, stripe fields
     removed — no longer relevant

listings                        (an app, owned by one developer)
  └─ revenue_streams             (one listing → many streams)
        └─ proposals             (a grower's pitch on a stream)
        └─ partnerships          (formed when a proposal is accepted)
              └─ revenue_reports (periodic, per partnership)
```

The key change from v1: **the partnership is per revenue stream, not per
listing.** One app can have a different grower handling store subscriptions
and another handling advertising, each under separate terms, running
independently.

### listings
The app itself — title, description, category, platform, what it does.
No longer carries `min_revenue_share` or `looking_for` — those move to the
stream level, since a developer may want a different partner and different
terms for different revenue channels on the same app.

### revenue_streams
One monetisation channel on a listing.

| field | notes |
|---|---|
| `stream_type` | `store_iap`, `web_revenuecat`, `advertising`, `existing_processor`, `other` |
| `status` | `draft` (developer hasn't opened it to proposals yet), `open`, `matched`, `archived` |
| `created_by` | developer (set up at listing time) or grower (proposed during a pitch) |
| `min_revenue_share` | developer's floor for this specific stream |
| `looking_for` / `control_boundaries` | per-stream, not per-app |
| `revenuecat_project_key` | set only when `stream_type` is RevenueCat-backed |

A listing can be published with **zero streams** — a developer can list the
app bare and let growers propose the first stream, or add streams themselves
later.

### proposals
A grower's pitch on one specific stream — existing or newly proposed
alongside the pitch itself ("you're not monetising with ads yet, I'd add
that channel and offer you 70%").

### partnerships
Formed when a proposal is accepted. One partnership = one (listing, stream,
grower) combination, each with its own `revenue_share`, term, and agreement.

## 3. Revenue reporting — no money moves through Crescopus

Every partnership settles on a period (default monthly). What happens at
period-end depends on the stream's `stream_type`:

**RevenueCat-backed (`store_iap`, `web_revenuecat`)**
"Sync now" pulls verified totals from RevenueCat's REST API for the period.
`revenue_reports.verified = true`, `source = 'revenuecat'`.

**Everything else (`advertising`, `existing_processor`, `other`)**
No API exists that can see this money. Either party enters the period
total themselves. `verified = false`, `source = 'manual'`, `reported_by`
records who. Clearly labelled as self-reported in the UI — this is a
materially different trust level than a RevenueCat-verified figure, and the
product should never blur that distinction.

**In both cases**, Crescopus computes the split from `partnerships.
revenue_share` and produces a **settlement record**: "developer owes grower
£X for March" (or vice versa, depending on who collects the revenue).
Nothing is transferred automatically. Payment happens directly between the
two parties — bank transfer, invoice, whatever they agree — and Crescopus
never touches it.

### revenue_reports
| field | notes |
|---|---|
| `partnership_id` | |
| `period_start` / `period_end` | |
| `gross_amount` | |
| `developer_share` / `grower_share` | computed at report time |
| `source` | `revenuecat` \| `manual` |
| `verified` | true only for RevenueCat-pulled data |
| `reported_by` | profile id, for manual reports |
| `settled` | boolean — either party can mark a period as paid, off-platform |

## 4. Lifecycle & anti-circumvention

### 4.1 Partnership lifecycle states

A partnership isn't just "on" or "off" — how it ended matters, both for
reputation and for the non-circumvention clause.

| `status` | meaning | who can trigger it |
|---|---|---|
| `active` | normal, ongoing | — |
| `ended` | either party walked away — no fault implied, no sale | either party, unilaterally |
| `bought_out` | developer sold the product to the grower outright | mutual — both parties confirm the sale |

`inactive` is **not** a status — it's a derived flag (`reporting_overdue`)
on an otherwise-`active` partnership, raised when periods pass with no
revenue report and no formal `ended`/`bought_out` closure. Keeping this
separate from the real lifecycle states matters: "ended cleanly" and "went
quiet" need to look different at a glance, not share a bucket.

### 4.2 Clean break — either party can exit, no permission required

If a partnership isn't working, either the developer or the grower can end
it unilaterally, at any time:

- `status → 'ended'`, `ended_at`, `ended_by` (which profile), and a
  required `end_reason` — a short explanation, not a legal classification.
  Making it required (rather than optional) matters here: this record is
  visible to the other party and factors into both people's track record,
  so it should carry real information rather than being a formality either
  side can skip.
- The **revenue stream reopens** (`status → 'open'`) so the developer can
  find a different grower for that channel.
- Any unresolved `revenue_reports` stay on record as owed — ending the
  partnership doesn't erase a pending settlement, it just stops requiring
  new periodic reports.
- **The non-circumvention tail clause still starts ticking from
  `ended_at`.** This is deliberate: if ending cleanly discharged the tail
  obligation, "end it, then keep working together off-record" would become
  the obvious way around the platform. The tail exists precisely to cover
  this case, not just the "went quiet" case.

This is distinct from `bought_out`: a buy-out extinguishes the underlying
revenue-share relationship by sale, so there's no ongoing arrangement left
for the tail clause to protect — it doesn't apply there. A clean break, by
contrast, is exactly the scenario the tail clause is for.

### 4.3 Anti-circumvention mechanisms
keep working together and no built-in incentive to keep reporting through
Crescopus — especially once the platform eventually charges a fee. Four
things address this, by design rather than as an afterthought:

1. **The reporting layer is the value, not a tax.** RevenueCat sync,
   auto-computed splits, and clean period statements should be *easier*
   than either party tracking and calculating this themselves. If it's
   genuinely useful, staying is the path of least resistance.
2. **Reputation only accrues on-platform.** Reviews, ratings, and a
   grower's visible track record are gated to partnerships with recorded
   history in Crescopus. Going dark costs both parties their future
   discoverability and credibility, not just Crescopus's cut.
3. **A non-circumvention clause in the standard partnership agreement.**
   Reporting obligations continue for a defined tail period (e.g. 12
   months) after a match is made through Crescopus, independent of whether
   the parties consider themselves "still working together" through the
   platform. This doesn't physically stop bypass, but it means quietly
   going around the platform doesn't actually discharge the obligation —
   and gives real grounds if it's ever contested.
4. **Silence is visible, not invisible.** If a partnership stops filing
   revenue reports without being formally closed out (`ended` or
   `bought_out`), it's flagged (`reporting_overdue` after N periods with no
   report) rather than just fading unnoticed. This is a soft signal for
   now — no enforcement mechanism — but it means "went quiet" and "ended
   cleanly" are visibly different states.
5. **The buy-out and the clean break stay the two sanctioned exits.**
   Formally closing a partnership — whether by sale (§4.1, `bought_out`) or
   by either party simply choosing to end it (§4.2, `ended`) — is the
   encouraged way to stop, contrasted against just going inactive.

Practical implication for launch sequencing: build the reporting/reputation
stickiness *before* introducing any platform fee. There's no incentive to
bypass a free platform — the goal is for genuine value to already be
embedded by the time there's a reason to leave.

## 5. Explicitly out of scope (for now)

- Any movement of money through Crescopus (dropped entirely — this was the
  Stripe Connect design, now scrapped).
- Ad-network API integrations (AdMob, Meta Audience Network, etc.) — manual
  reporting covers this until/unless it's worth building per-network pulls.
- Automated enforcement of the non-circumvention clause — this starts as a
  contract term and a status flag, not an enforcement system.

## 6. What carries over from the existing build

Unaffected by this redesign — no rework needed:
- Auth (signup/login, Supabase integration, the profile-creation trigger,
  the country field)
- Settings, app factory, blueprint structure
- Branding, templates, deployment config

Needs rebuilding, because the relationship model changed shape underneath
it:
- `listings`, `proposals`, `partnerships` schema and routes
- `revenue_events` → replaced by `revenue_reports`
- The `payments` blueprint → deleted (Stripe Connect is gone)
- A new reporting blueprint: RevenueCat client, manual entry forms,
  settlement view
- Dashboard → group partnerships by stream, per listing
