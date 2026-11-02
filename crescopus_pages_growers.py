"""Crescopus content library: grower topics, version 1 drafts.

Written from a neutral point of view ("the grower", "the builder"), to sit alongside the
builder pages. Load them as drafts with:

    python load_pages.py <your-user-id> --growers

Anything still to check is marked <strong>[CONFIRM: ...]</strong>. A page cannot be submitted
for review until its markers are removed.
"""

PAGES = [
    {
        "key": "grower-role",
        "title": "What does a grower do on Crescopus?",
        "tags": ["start", "growers", "roles", "overview"],
        "summary": "A grower helps an app find users and earn more, in return for a share of what that growth brings in. The builder keeps ownership of the app.",
        "disclaimer": None,
        "body": '''
<p>A grower is a person or small team with the skills to grow an app: marketing, promotion, pricing, partnerships, distribution or monetisation. Many good apps stall because the builder doesn't have the time or experience for this side of things. That is where a grower comes in.</p>
<h3>What a grower brings</h3>
<ul>
<li>Skills and effort to grow the app's audience and income</li>
<li>A plan, agreed with the builder in a CrescoPlan</li>
<li>A record of the time and costs they put in, kept in the CrescoLedger</li>
</ul>
<h3>What the grower gets</h3>
<p>The grower and the builder agree between themselves how the grower is rewarded, usually as a share of the revenue the app earns. Crescopus helps them plan and keep a shared record, but the arrangement itself is directly between the two of them.</p>
<h3>What the grower does not get</h3>
<p>The grower does not take ownership of the app. The builder stays in charge of it.</p>
''',
    },
    {
        "key": "grower-getting-started",
        "title": "How does a grower get started?",
        "tags": ["start", "growers", "getting-started", "steps", "signup"],
        "summary": "Sign up as a grower, make a free grower card, then use Find to look for apps that fit.",
        "disclaimer": None,
        "body": '''
<ol>
<li><strong>Sign up as a grower.</strong> Each account is either a builder or a grower. Signing in with Google, LinkedIn or GitHub works too; the grower then chooses the grower role once.</li>
<li><strong>Make a grower card.</strong> The card tells builders who the grower is, what they offer and what they are looking for. See "What should a grower put on their card?"</li>
<li><strong>Look for apps.</strong> Find shows the apps that builders have listed. Each card opens to show more detail.</li>
<li><strong>Reach out.</strong> When an app looks like a good fit, the grower sends the builder a short introduction.</li>
<li><strong>Plan together.</strong> If the builder accepts, the two of them get a shared space in My Crescos with messages, a CrescoPlan and a CrescoLedger.</li>
</ol>
<p>Builders can also find growers and reach out to them first, so a good card matters.</p>
''',
    },
    {
        "key": "grower-card",
        "title": "What should a grower put on their card?",
        "tags": ["growers", "card", "profile", "pitch"],
        "summary": "A short tagline, a clear description of the skills on offer, what kind of apps the grower wants to work with, and any track record that shows results.",
        "disclaimer": None,
        "body": '''
<p>The grower card is what builders see first, so it is worth making clear and specific.</p>
<h3>What to include</h3>
<ul>
<li><strong>Tagline:</strong> one line that sums up what the grower does, for example "App Store optimisation and paid acquisition for games".</li>
<li><strong>About:</strong> who the grower is and how they work.</li>
<li><strong>Offers:</strong> the skills and help they can bring, such as marketing, pricing, partnerships, content or analytics.</li>
<li><strong>Needs:</strong> what they are looking for in an app or a builder, such as a category, a platform or a stage of growth.</li>
<li><strong>Results:</strong> examples of apps or products they have grown, with figures where they can share them.</li>
</ul>
<h3>Tips</h3>
<ul>
<li>Be specific. "Grew a fitness app from 2,000 to 20,000 monthly users" says more than "experienced marketer".</li>
<li>Only claim what can be backed up. Builders may ask for evidence.</li>
<li>Keep it up to date. The card can be edited at any time.</li>
</ul>
''',
    },
    {
        "key": "grower-finding-apps",
        "title": "How does a grower find apps to work with?",
        "tags": ["growers", "find", "browse", "apps", "search"],
        "summary": "Find lists the apps builders have put on Crescopus. Each app card opens to show the builder's pitch, what they need and what they offer.",
        "disclaimer": None,
        "body": '''
<p>Find shows a card for each app that builders have listed. Opening a card shows the app's pitch, its category and platform, and what the builder is looking for in a grower.</p>
<h3>Things worth checking</h3>
<ul>
<li>Does the app fit the grower's skills and experience?</li>
<li>Does the builder's list of needs match what the grower offers?</li>
<li>Is the app already earning, or does it need monetising from scratch? Both can work, but the plan will look very different.</li>
<li>Is the builder still actively working on it?</li>
</ul>
<p><strong>[CONFIRM: describe any filters or search on Find, e.g. by category or platform.]</strong></p>
''',
    },
    {
        "key": "grower-connecting",
        "title": "How does a grower contact a builder?",
        "tags": ["growers", "connect", "connection-request", "introduction", "contact"],
        "summary": "From an app's card, the grower sends a short introduction. The builder can accept or decline. Nothing is agreed at this stage.",
        "disclaimer": None,
        "body": '''
<p>From an app's card, the grower can send the builder a connection request with a short introduction.</p>
<h3>A good introduction</h3>
<ul>
<li>Says why this app caught the grower's interest</li>
<li>Gives one or two ideas for how it could grow</li>
<li>Points to relevant experience</li>
<li>Stays short. The detail comes later, in the CrescoPlan.</li>
</ul>
<h3>What happens next</h3>
<p>The builder can accept or decline. If they accept, the two of them get a shared space in My Crescos. Sending or accepting a request does not commit either side to anything.</p>
<p>Before sending, the grower confirms they understand that Crescopus doesn't broker, manage or guarantee any relationship formed on the platform and is not a party to it.</p>
''',
    },
    {
        "key": "grower-my-crescos",
        "title": "What happens after a builder accepts?",
        "tags": ["growers", "my-crescos", "partnership", "messages", "process"],
        "summary": "The partnership appears in My Crescos, where the grower and builder can message each other, build a CrescoPlan and keep a CrescoLedger.",
        "disclaimer": None,
        "body": '''
<p>Once a builder accepts, the partnership (a "Cresco") appears in My Crescos for both of them. Each Cresco has:</p>
<ul>
<li><strong>Messages:</strong> a private conversation between the grower and the builder.</li>
<li><strong>CrescoPlan:</strong> what they are trying to achieve together, who does what and how they will measure success.</li>
<li><strong>CrescoLedger:</strong> a shared record of costs, time and revenue.</li>
</ul>
<p>Anything that needs the grower's attention, such as a new message, a plan change or a ledger entry to confirm, shows under "Needs your attention" on their Home page.</p>
''',
    },
    {
        "key": "grower-crescoplan",
        "title": "What is a CrescoPlan, and how does a grower contribute to it?",
        "tags": ["growers", "crescoplan", "plan", "actions", "measures"],
        "summary": "The CrescoPlan is a shared plan the grower and builder write together. It sets out needs and offers, actions with owners and dates, and how success will be measured. Each version is agreed by both.",
        "disclaimer": None,
        "body": '''
<p>The CrescoPlan is where the grower and the builder agree what they are setting out to do.</p>
<h3>What it contains</h3>
<ul>
<li><strong>Needs and offers:</strong> what each side needs and brings. Ticked items from each person's card can be added with a tap.</li>
<li><strong>Actions:</strong> what will be done, who owns it, by when, and its status.</li>
<li><strong>Measures:</strong> how success is judged, with a target, the evidence that will show it, and when it will be reviewed.</li>
</ul>
<h3>How it is agreed</h3>
<p>Either side can edit the plan. Each saved change creates a new version, and both the grower and the builder agree to it. The history shows every version and who changed what.</p>
<h3>Why it matters for the grower</h3>
<p>A clear, agreed plan sets out what the grower is expected to do and how results will be judged, which helps avoid misunderstandings later. Agreeing a plan is not a contract. Anything the two of them want to be binding should be agreed separately, ideally with independent advice.</p>
''',
    },
    {
        "key": "grower-ledger",
        "title": "How does a grower record their time and costs?",
        "tags": ["growers", "crescoledger", "ledger", "time", "costs", "rates"],
        "summary": "In the CrescoLedger. The grower adds entries for costs or time, and the builder confirms them. Time is valued at an hourly rate both sides agree.",
        "disclaimer": None,
        "body": '''
<p>The CrescoLedger is a shared record of what each side puts in and what the app earns. The builder chooses the ledger's currency.</p>
<h3>Adding entries</h3>
<p>Either side can add an entry, for example ad spend, a tool subscription or hours worked. The other side then confirms it, or queries it if something looks wrong. Confirming only means agreeing the entry is an accurate record.</p>
<h3>Time and hourly rates</h3>
<p>Time entries are valued at an hourly rate that both sides agree. Until a rate is agreed, time is recorded at zero cost. When a new rate is agreed, the two of them choose whether it applies to time entries that are still pending.</p>
<h3>Goodwill and recoverable costs</h3>
<ul>
<li><strong>Recoverable:</strong> a cost the two sides may later agree to recover, for example out of revenue.</li>
<li><strong>Goodwill:</strong> effort that isn't expected to be paid back but is still acknowledged, for example work done before the partnership began. It can still be useful when discussing something like equity.</li>
</ul>
''',
    },
    {
        "key": "grower-getting-paid",
        "title": "How does a grower get paid?",
        "tags": ["growers", "payment", "revenue-share", "money", "recovery"],
        "summary": "Directly by the builder, on terms the two of them agree. Crescopus never holds or moves money. The CrescoLedger keeps a shared record to support those discussions.",
        "disclaimer": "This page explains how Crescopus works. It is not legal, tax or financial advice.",
        "body": '''
<p>Crescopus never holds, moves or guarantees any money. Any payment is made directly between the builder and the grower, on terms they agree between themselves.</p>
<h3>Agreeing the terms</h3>
<p>Most partnerships are based on a share of the revenue the app earns. The two sides agree the percentage, what counts as revenue and when payments are made. Writing these terms into a separate agreement is strongly recommended.</p>
<h3>How the ledger helps</h3>
<ul>
<li>Revenue, costs and time are recorded in one place that both can see.</li>
<li>Either side can propose a recovery settlement. The other side accepts or declines it. Nothing is ever recovered automatically.</li>
<li>The ledger can be exported as a CSV file.</li>
</ul>
<p>Figures in the ledger help the two sides negotiate. Confirming an entry or a settlement does not create any obligation to pay.</p>
''',
    },
    {
        "key": "grower-protecting-effort",
        "title": "How can a grower protect their time and effort?",
        "tags": ["growers", "trust", "protection", "risk", "agreement"],
        "summary": "By agreeing a clear plan, recording time and costs as they go, getting entries confirmed, and putting the important terms in a separate written agreement.",
        "disclaimer": "This page explains how Crescopus works. It is not legal, tax or financial advice.",
        "body": '''
<p>Working for a share of future revenue carries risk for a grower. Some good habits help:</p>
<ul>
<li><strong>Agree the plan first.</strong> A CrescoPlan both sides have agreed sets out what was expected.</li>
<li><strong>Agree an hourly rate early.</strong> Time is recorded at zero cost until a rate is agreed.</li>
<li><strong>Record as you go.</strong> Add time and costs to the CrescoLedger promptly, and ask for them to be confirmed.</li>
<li><strong>Mark goodwill clearly.</strong> Effort that isn't expected to be repaid can still be acknowledged.</li>
<li><strong>Get it in writing.</strong> Put the revenue share and any payment terms in a separate agreement, ideally with independent advice.</li>
</ul>
<p>Crescopus does not check or guarantee any figures, and it is not a party to any arrangement between a builder and a grower.</p>
''',
    },
    {
        "key": "grower-disagreements",
        "title": "What if the grower and builder disagree about a ledger entry?",
        "tags": ["growers", "crescoledger", "disagreement", "query", "crescoguide"],
        "summary": "Either side can query an entry. The two of them talk it through, and either can ask the CrescoGuide for a neutral summary. The entry keeps counting in the totals while it is open.",
        "disclaimer": "This page explains how Crescopus works. It is not legal, tax or financial advice.",
        "body": '''
<p>If an entry doesn't look right, either side can query it from the ledger. Each person then gives their side.</p>
<ul>
<li>A queried entry keeps counting in the ledger totals while it is open.</li>
<li>Either side can ask the CrescoGuide, an AI tool, for a neutral summary of both sides. It is advisory only, may contain mistakes and is not professional advice. Each account has three free summaries.</li>
<li>If the other side doesn't respond for 14 days, the query can be closed without agreement.</li>
</ul>
<p>If the two sides still can't agree, an independent mediator or professional adviser may help.</p>
''',
    },
    {
        "key": "grower-multiple-apps",
        "title": "Can a grower work with more than one app?",
        "tags": ["growers", "multiple", "apps", "partnerships"],
        "summary": "Yes. Each app is a separate Cresco with its own plan and ledger.",
        "disclaimer": None,
        "body": '''
<p>A grower can work with several apps, including more than one from the same builder. Each partnership is its own Cresco in My Crescos, with its own messages, CrescoPlan and CrescoLedger.</p>
<p>It is worth being open with each builder about other commitments, especially with apps that compete with each other.</p>
<p><strong>[CONFIRM: is there any limit on the number of active Crescos a grower can have?]</strong></p>
''',
    },
    {
        "key": "grower-ending",
        "title": "How does a grower end a partnership or leave Crescopus?",
        "tags": ["growers", "ending", "withdraw", "leave", "card"],
        "summary": "Either side can end a partnership from its Cresco; its plan and ledger stay as a read-only record. A grower can also withdraw their card, which hides it from Find and lets them choose which partnerships to end. A withdrawn card can be restored.",
        "disclaimer": None,
        "body": '''
<h3>Ending a partnership</h3>
<p>Either side can end a partnership from the Cresco, giving a reason. Once it ends, its plan and ledger become read-only but stay available to both sides as a record.</p>
<h3>Withdrawing a grower card</h3>
<p>A grower can withdraw their card. It disappears from Find straight away, so nobody new can connect, and any pending connection requests are declined. The grower can choose which active partnerships to end at the same time; any left unticked carry on.</p>
<p>Plans and ledgers stay available to both sides either way, and a withdrawn card can be restored later from the dashboard.</p>
''',
    },
    {
        "key": "grower-cost",
        "title": "Does it cost a grower anything to use Crescopus?",
        "tags": ["growers", "cost", "fees", "free", "pricing"],
        "summary": "No. Crescopus is free today. Any partnership started while it is free stays free for its lifetime.",
        "disclaimer": None,
        "body": '''
<p>Crescopus doesn't charge anything today: no fee for cards, connecting or the revenue a grower shares with a builder.</p>
<p>A fee may be introduced later for partnerships started from that point on. Any partnership started while Crescopus is free stays free for its lifetime.</p>
<p>The earliest builders and growers also carry a founding member mark on their profile.</p>
<p>Some extras, such as more CrescoGuide summaries, may come with a premium subscription in future.</p>
''',
    },
]
