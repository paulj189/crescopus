# Crescopus — Spec v3: Ice-Breaker First

## Why this revision

SPEC v2 required a builder and grower to agree revenue terms (CrescoShares) before
they'd really had a chance to talk. That's backwards for a first-time platform:
it puts the highest-friction, highest-stakes decision at the *front* of the
funnel, before either party knows if they even want to work together.

v3 moves revenue entirely out of the default path. The platform's job, for now,
is to be a low-risk way for a builder and a grower to **meet and explore** —
nothing more. Revenue-sharing, verification, and reporting remain fully built
and available, but only as something two people deliberately opt into *after*
they've already decided they like each other. This also gives Crescopus a
natural, honest place to put a future paywall: exploring stays free forever;
formalising is where a premium tier could eventually live.

---

## Entities

### Listing
An app posted by a builder. Lightweight — no revenue detail required to
publish. A description of the app and what kind of grower they're hoping to
meet is enough.

### Grower Profile *(not actually new — an extension of the existing account)*
Growers already create an account the same way builders do. The only real
addition needed is a **self-description field**, made public so builders can
browse it — with the same friendly, example-driven guidance as connection
requests (what you're good at, the kind of apps you're drawn to, anything
worth knowing about your track record). No new signup flow, no separate
object — just one more field on the profile that happens to be public for
growers. Worth adding the same field for **builders too** — useful context
for a grower deciding whether to reach out, and keeps the two sides
symmetric.

### CrescoPact
The relationship itself, not a revenue agreement. Every CrescoPact starts in
**Trial** state and *may* later move to **Formalised**. A listing can have
**many concurrent Trial CrescoPacts**, but only ever **one Formalised
CrescoPact** at a time.

- **Trial** — created the moment a builder accepts a grower's connection
  request. Reveals both parties' email addresses and opens an in-app message
  thread. No revenue terms attached. Purely exploratory.
- **Formalised** — a Trial that both sides have deliberately agreed to commit
  to (see "Formalising" below). Signals exclusivity/seriousness for this
  listing. Still carries no revenue terms by default.

A Trial can be ended directly by either side via **Disconnect** — this
**completely ends the relationship**, same severity as ending a Formalised
CrescoPact: a reason is given, visible to both, and factors into track
record. This is deliberately more final than a declined formalise proposal
(below), which just means the two of you haven't reached a formalise-worthy
agreement *yet* — the Trial itself continues.

A Formalised CrescoPact can later end (as today — reason recorded, visible to
both, factors into track record). When it does, the listing's other Trial
CrescoPacts are **not** auto-closed — they remain live, so the builder isn't
forced back to square one.

### Connection request (replaces "Pitch" as a structured object)
Search is **reciprocal**: a grower can browse Listings and reach out to a
builder, and a builder can browse Grower Profiles and reach out to a grower.
Whichever side initiates, the mechanics are the same — only the direction
differs.

The initiator sends a **free-form message**, not a structured form (offer %,
growth plan, track record as separate fields). Rather than required fields,
the compose box offers friendly, example-driven guidance — not rules, just a
nudge toward a useful first message:

> *A good intro usually covers: what drew you to this app, anything relevant
> you've done before, and roughly how you'd approach growing it. You don't
> need all three — just enough for the other side to picture working with
> you.*

Tone throughout (guidelines, empty states, prompts) should be friendly and
helpful, not formal or legalistic — this is the "ice-breaker" surface of the
product and should read like one.

The recipient responds with:
- **Accept** → creates the Trial CrescoPact, reveals emails, opens messaging
- **Reject** → no CrescoPact created; an optional reason can be given

**Every connection request is stored regardless of outcome** — accepted,
rejected, or later abandoned. This preserves the "recorded, not hidden" trust
principle from the existing end-of-relationship flow, and gives both sides a
track record even from Trials that didn't go anywhere.

### Formalising
A deliberate, mutual upgrade from Trial → Formalised, layered on an existing
CrescoPact:
1. Either party **proposes** to formalise
2. The other party **accepts**, or **declines with a reason** — a decline
   does **not** end the Trial. The proposer can see the reason and respond;
   conversation continues as normal, and formalising can be proposed again
   later, **with no limit** on how many times.
3. On acceptance, this CrescoPact becomes the listing's one Formalised
   CrescoPact

Formalising is a statement of commitment/exclusivity. It does **not**
automatically pull in revenue terms.

A connection request that's rejected, or a Trial that ends in Disconnect,
doesn't block trying again later — either side is free to send a new
connection request.

### Revenue terms (unchanged from what's already built, just relocated)
CrescoShares, RevenueCat sync, manual/engagement reporting, the consent
mechanism — all of this remains exactly as already built. It simply becomes
an **optional, separate action available only on a Formalised CrescoPact**,
initiated whenever both sides are ready. Nothing here needs to be
re-architected, only re-triggered from a later point in the journey.

### Revenue Stream
No longer relevant to listing or matching at all. Deferred until (and unless)
a Formalised CrescoPact's revenue terms are being set up — at that point it
becomes a detail of *that* setup, not something defined at listing time.

---

## User journey

1. Builder lists an app — no revenue stream required. Grower fills in a
   Grower Profile — no strict requirements either.
2. Either direction: a grower browses Listings and sends a connection
   request, **or** a builder browses Grower Profiles and sends one. Same
   mechanics either way — a free-form intro message.
3. The recipient reviews it and either:
   - **Accepts** → Trial CrescoPact created, emails revealed, messaging opens
   - **Rejects** → optionally with a reason; message stays on record, and
     the sender can try again later
4. Builder can be in **several Trial CrescoPacts at once** on the same
   listing, talking to multiple growers in parallel — regardless of which
   side initiated each one.
5. Either side in a Trial can end it directly via **Disconnect** (reason
   given, recorded, visible to both) if it's clearly not a fit.
6. Anywhere along the way, either side in a Trial can **propose to
   formalise**. The other side accepts, or **declines with a reason** — a
   decline doesn't end the Trial; the proposer can respond and try again
   later.
7. On acceptance, that CrescoPact becomes **Formalised** — the listing's one
   committed relationship. The listing's other growers in Trial are
   **notified** that it's now formalised with someone else. Their Trials
   stay open and they can keep refining their conversation/positioning, but
   won't be considered for Formalising unless the current one ends.
8. *(Fully separate, optional, whenever both are ready)* — either side can
   propose attaching **revenue terms** to the Formalised CrescoPact. This is
   where the existing CrescoShares/consent/RevenueCat/reporting flow already
   built comes back into play, unchanged.
9. If the Formalised CrescoPact later ends, the listing's other Trials remain
   available — the builder isn't starting over, and any of them can now be
   proposed for Formalising again.

---

## Terminology summary

| Term | Meaning |
|---|---|
| Listing | The app posted by a builder |
| Grower Profile | A grower's account, with a public self-description field — the counterpart to a Listing |
| Connection request | A free-form message expressing interest, sent by either side |
| Trial CrescoPact | Low-stakes, exploratory relationship — emails + messaging, no revenue |
| Disconnect | Either side fully ending a Trial, with a recorded reason |
| Formalising | Mutual propose/accept step that commits one CrescoPact as exclusive |
| Formalised CrescoPact | The listing's one committed relationship |
| Revenue terms | Optional, later, attached only to a Formalised CrescoPact |
| CrescoShares | Unit representing an agreed revenue stake — only relevant once revenue terms are attached |

---

## Resolved during discussion (kept for reference)

- **Grower/Builder self-description**: not a new entity — just a public
  self-description field on the existing profile, for both roles, with
  example-driven guidance.
- **Symmetric "formalised elsewhere" notification for builders**: not
  needed. Exclusivity is scoped to a *listing* (one app shouldn't have two
  committed grower relationships at once), not to a *grower* — a grower is
  free to have several simultaneous Formalised relationships across
  different listings, so there's no equivalent conflict to notify a builder
  about.

---

## What stays exactly as-is

- Listing creation, editing
- The account model (single role per user, builder or grower)
- CrescoShares, consent mechanism, RevenueCat integration, manual/engagement
  reporting — all fully built, just triggered later in the journey
- Terms & Conditions / Privacy / info modal framing (the "opportunity to
  explore" language already fits this direction well, if anything it should
  be leaned into further now)
- Branding, visual design, footer/nav/badge work
