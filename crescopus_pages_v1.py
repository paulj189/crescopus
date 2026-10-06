"""Crescopus content library, version 1 drafts (written from a builder's point of view).

Every fact I could not confirm from your design notes is marked <strong>[CONFIRM: ...]</strong>.
The content library will not let a page be submitted for review while any [CONFIRM marker is
still in it, so nothing unchecked can be approved by accident. Edit the text in the editor
(or here, before loading), then remove each marker once the fact is right.
"""

NOTICE = (
    "This page explains how Crescopus works. It is not legal, tax or financial advice. "
    "If it differs from the terms you have agreed to, those terms apply."
)

PAGES = [
    {
        "key": "what-is-crescopus",
        "title": "What is Crescopus?",
        "tags": ["start", "overview", "crescopus"],
        "summary": "Crescopus connects app builders with growers who can build an app's revenue. Instead of selling the app, you share the revenue with your grower.",
        "disclaimer": None,
        "body": '''
<p>Plenty of good apps stall because their builders don't have the time, skills or appetite to market and monetise them. Crescopus connects those builders with <strong>growers</strong>: people and small teams who specialise in growing an app's audience and income.</p>
<p>Instead of selling the app, you and a grower agree a <strong>revenue-share partnership</strong>. The grower does the growing, and you both share the income it brings.</p>
<h3>What Crescopus does</h3>
<ul>
<li>Helps you list your app and find a grower</li>
<li>Lets growers send proposals that you can compare</li>
<li>Tracks the revenue and works out each side's share</li>
<li>Gives you and your grower a place to message each other and manage the partnership</li>
</ul>
<h3>What Crescopus does not do</h3>
<ul>
<li>It never holds or moves your money. You and your grower settle directly with each other.</li>
<li>It does not take ownership of your app.</li>
<li>It does not give legal, tax or financial advice.</li>
</ul>
''',
    },
    {
        "key": "builders-and-growers",
        "title": "What is the difference between a builder and a grower?",
        "tags": ["roles", "builders", "growers"],
        "summary": "A builder owns the app. A grower brings the skills and effort to grow its revenue. Each partnership is between one builder and one grower.",
        "disclaimer": None,
        "body": '''
<h3>Builders</h3>
<p>A builder is the person or team who made the app and owns it. As a builder you list your app, receive proposals and decide which grower to work with. You stay in charge of the app itself.</p>
<h3>Growers</h3>
<p>A grower is someone who grows an app's audience and income, for example through marketing, promotion, pricing or distribution. A grower looks at listings and sends proposals that set out the revenue share they are proposing, their plan for growing the app, and their track record.</p>
<h3>One builder, one grower</h3>
<p>Each partnership is between one builder and one grower, and covers one revenue stream. See "What is a revenue stream?" to find out how that works.</p>
''',
    },
    {
        "key": "how-it-works",
        "title": "How does Crescopus work from start to finish?",
        "tags": ["start", "process", "getting-started", "steps"],
        "summary": "List your app, compare proposals, start with a trial, then formalise the partnership. Revenue is tracked and you settle directly with your grower.",
        "disclaimer": None,
        "body": '''
<ol>
<li><strong>List your app.</strong> Describe it and say which revenue streams you want help with.</li>
<li><strong>Connect.</strong> Growers can approach you, and you can approach growers. Either side can send a connection request, and the other side can accept or decline.</li>
<li><strong>Compare proposals.</strong> A proposal sets out the revenue share, the grower's growth plan and their track record.</li>
<li><strong>Choose one grower.</strong> Each partnership is one builder with one grower.</li>
<li><strong>Start a trial.</strong> You work together and message each other inside the partnership.</li>
<li><strong>Formalise.</strong> If the trial is going well, either side can propose making it a full partnership, and the other side accepts.</li>
<li><strong>Earn and settle.</strong> Revenue is tracked, Crescopus works out each side's share, and you settle directly with each other.</li>
<li><strong>Review or end it.</strong> Either side can end a partnership with a clean break.</li>
</ol>
<p><strong>[CONFIRM: check these steps and names (connection request, proposal, trial, formalise) match how the app works today.]</strong></p>
''',
    },
    {
        "key": "listing-your-app",
        "title": "How do I list my app?",
        "tags": ["listing", "builders", "getting-started"],
        "summary": "A listing tells growers what your app does and which revenue streams you'd like help with, so they can decide whether to send a proposal.",
        "disclaimer": None,
        "body": '''
<p>Your listing is how growers find and judge your app. The more accurate it is, the better the proposals you will receive.</p>
<h3>What to include</h3>
<ul>
<li>What the app does and who it is for</li>
<li>How it earns money today, if it does</li>
<li>Which revenue streams you would like a grower to work on</li>
<li>Honest figures. Revenue is tracked and checked later, so overstating it will not help you</li>
</ul>
<h3>Tips</h3>
<ul>
<li>Be specific about what is working and what is not</li>
<li>Say what kind of help you want, for example more users or better pricing</li>
<li>Connect RevenueCat if you use it, so your revenue can be checked automatically</li>
</ul>
<p><strong>[CONFIRM: list the actual listing fields, and where to find "create a listing" in the app.]</strong></p>
''',
    },
    {
        "key": "choosing-a-grower",
        "title": "How do I choose the right grower?",
        "tags": ["growers", "proposals", "choosing", "comparing"],
        "summary": "Compare proposals on the revenue share, the growth plan and the grower's track record, and talk to the grower before you decide.",
        "disclaimer": None,
        "body": '''
<h3>What to compare</h3>
<ul>
<li><strong>The revenue share</strong> they are proposing, and exactly what it applies to</li>
<li><strong>Their growth plan</strong>: is it specific to your app, or generic?</li>
<li><strong>Their track record</strong>: past partnerships and how they ended</li>
</ul>
<h3>Questions worth asking</h3>
<ul>
<li>Which similar apps have you grown, and what happened?</li>
<li>What will you do in the first few weeks?</li>
<li>What access to my app or accounts do you need, and why?</li>
<li>How will you report progress to me?</li>
<li>What happens if results are slow?</li>
</ul>
<h3>Take your time</h3>
<p>You choose one grower per partnership, so it is worth talking to more than one. Starting with a trial lets you see how it works in practice before you commit.</p>
''',
    },
    {
        "key": "trust-and-safety",
        "title": "Can I trust a grower?",
        "tags": ["start", "trust", "safety", "track-record", "growers"],
        "summary": "Crescopus gives you information to judge a grower and keeps your money out of the middle, but it cannot guarantee how any grower will behave.",
        "disclaimer": NOTICE,
        "body": '''
<p>No platform can guarantee how someone will behave. What Crescopus does is give you information and structure so that you are not relying on trust alone.</p>
<h3>What helps you judge a grower</h3>
<ul>
<li><strong>Track record.</strong> Past partnerships count towards a grower's record, including the reasons given when a partnership ended.</li>
<li><strong>Tracked revenue.</strong> Revenue is tracked, and checked automatically where RevenueCat is connected, so figures are not taken purely on trust.</li>
<li><strong>Your money stays with you.</strong> Crescopus never holds your money, so there is no pot of funds for anyone to disappear with.</li>
<li><strong>You keep your app.</strong> A partnership shares revenue. It does not transfer ownership.</li>
</ul>
<h3>What Crescopus cannot do</h3>
<ul>
<li>Guarantee that a grower will deliver results</li>
<li>Collect a share that someone fails to pay you, because it does not handle payments</li>
</ul>
<p><strong>[CONFIRM: say what checks, if any, Crescopus makes on growers when they join, and who can see a grower's track record.]</strong></p>
<h3>Sensible precautions</h3>
<ul>
<li>Start with a trial before you formalise</li>
<li>Ask for examples or references</li>
<li>Give a grower only the access they need for the revenue stream they are working on</li>
<li>Keep your conversations inside the partnership, so there is a record</li>
</ul>
''',
    },
    {
        "key": "app-ownership",
        "title": "Do I keep ownership of my app?",
        "tags": ["ownership", "builders", "rights"],
        "summary": "Yes. A Crescopus partnership shares revenue. It is not a sale, and you remain the owner of your app.",
        "disclaimer": NOTICE,
        "body": '''
<p>You stay the owner of your app. A partnership gives your grower a share of the revenue from the stream they work on. It does not give them a stake in the app itself.</p>
<ul>
<li>You are not selling your app</li>
<li>Growers do not receive equity in your app through Crescopus</li>
<li>Either side can end the partnership with a clean break</li>
</ul>
<p><strong>[CONFIRM: check that your terms say the builder always keeps ownership, and say how any code, accounts or customer data a grower works with are handled.]</strong></p>
''',
    },
    {
        "key": "how-money-works",
        "title": "Does Crescopus handle my money?",
        "tags": ["start", "money", "payments", "settlement"],
        "summary": "No. Crescopus never holds or moves money. Revenue is tracked, the split is calculated, and you and your grower settle directly with each other.",
        "disclaimer": NOTICE,
        "body": '''
<p>No. Crescopus never holds or moves money, and your payments never pass through us. That is deliberate: it keeps your money out of the middle.</p>
<h3>How it works</h3>
<ol>
<li>Revenue from your app is tracked, either automatically through RevenueCat or from figures reported by the person who receives it.</li>
<li>Crescopus works out each side's share from those figures, using the revenue share you agreed.</li>
<li>You and your grower settle directly with each other, using your own payment methods.</li>
</ol>
<p><strong>[CONFIRM: say who pays whom, how often, and the default settlement period.]</strong></p>
<h3>Worth knowing</h3>
<ul>
<li>Because Crescopus does not handle payments, it cannot collect an unpaid share for you.</li>
<li>You are responsible for your own tax affairs. Consider getting independent advice.</li>
</ul>
''',
    },
    {
        "key": "revenue-tracking",
        "title": "How is revenue tracked and checked?",
        "tags": ["revenue", "tracking", "revenuecat", "verification"],
        "summary": "Where possible, revenue comes straight from RevenueCat so it can be checked. Otherwise it is reported by the person who receives it.",
        "disclaimer": None,
        "body": '''
<p>Crescopus tracks revenue in one of two ways:</p>
<ul>
<li><strong>Automatically through RevenueCat</strong>, where your app uses it. The figures come straight from RevenueCat, so they can be checked.</li>
<li><strong>Self-reported</strong>, where that is not possible. The person who receives the revenue enters the figures, so they rely more on trust.</li>
</ul>
<p>Either way, Crescopus then works out each side's share from the tracked figures.</p>
<h3>Tips</h3>
<ul>
<li>If you can, connect RevenueCat. It gives both sides more confidence.</li>
<li>If figures are self-reported, agree up front how you will check them, for example by sharing statements from time to time.</li>
</ul>
<p><strong>[CONFIRM: say what checks Crescopus applies to self-reported figures, and how often figures are updated.]</strong></p>
''',
    },
    {
        "key": "revenue-streams",
        "title": "What is a revenue stream?",
        "tags": ["revenue", "streams", "channels"],
        "summary": "A revenue stream is a channel your app earns through. A partnership covers one stream, so one app can have different growers for different streams.",
        "disclaimer": None,
        "body": '''
<p>A revenue stream is a channel through which your app earns money, such as:</p>
<ul>
<li>In-app purchases through the app stores</li>
<li>Web payments, for example through RevenueCat</li>
<li>Advertising</li>
<li>An existing payment processor</li>
<li>Something else</li>
</ul>
<h3>Why it matters</h3>
<p>Each partnership covers one revenue stream. That means one app can have a different grower, on different terms, for each stream. For example, one grower might work on advertising while another works on web subscriptions.</p>
<p>It also keeps things clear: each grower is rewarded only for the stream they work on.</p>
''',
    },
    {
        "key": "revenue-share",
        "title": "How is the revenue share worked out?",
        "tags": ["revenue", "split", "share", "terms"],
        "summary": "The revenue share is agreed before you start. Crescopus then works out each side's share from the tracked revenue.",
        "disclaimer": NOTICE,
        "body": '''
<p>The revenue share is set out in the proposal you accept, so you know the terms before you begin. After that, Crescopus works out each side's share from the revenue it tracks for the stream.</p>
<p><strong>[CONFIRM: say whether the share applies to all revenue from the stream or only to revenue above a baseline, and whether app store fees and taxes are taken off before the split.]</strong></p>
<h3>Questions to ask before you agree</h3>
<ul>
<li>What exactly does the percentage apply to?</li>
<li>Is there a starting baseline, so the grower is rewarded only for growth?</li>
<li>Are store fees and taxes taken off before the split?</li>
<li>Does the share change over time?</li>
</ul>
<p>Crescopus may also charge a platform fee in future. It would be separate from the split between you and your grower. See "Does Crescopus cost anything?"</p>
''',
    },
    {
        "key": "trial-and-formalising",
        "title": "What is a trial, and what is a CrescoPact?",
        "tags": ["trial", "formalise", "crescopact", "partnership"],
        "summary": "A partnership starts as a trial. If it is going well, either side can propose to formalise it as a CrescoPact, and the other side accepts.",
        "disclaimer": NOTICE,
        "body": '''
<p>When you and a grower decide to work together, the partnership starts as a <strong>trial</strong>. It gives you both a chance to see how it works before you commit.</p>
<p>If it is going well, either side can <strong>propose to formalise</strong> it. When the other side accepts, the partnership becomes a CrescoPact, the agreement that sets out how you will work together.</p>
<p>You will see a notice when your grower has proposed formalising and is waiting for your answer.</p>
<p><strong>[CONFIRM: define what a CrescoPact is, say how long a trial lasts, and say what changes when a partnership is formalised.]</strong></p>
''',
    },
    {
        "key": "ending-a-partnership",
        "title": "How do I end a partnership?",
        "tags": ["ending", "clean-break", "exit", "partnership"],
        "summary": "Either side can end a partnership with a clean break. A reason is required, the other side can see it, and some terms carry on afterwards.",
        "disclaimer": NOTICE,
        "body": '''
<p>Either you or your grower can end a partnership with a <strong>clean break</strong>.</p>
<h3>What a clean break involves</h3>
<ul>
<li>You must give a reason.</li>
<li>The other side can see your reason, and it counts towards your track record on Crescopus.</li>
<li>Some terms carry on afterwards. In particular, the "non-circumvention tail" stops either side going around Crescopus to carry on the same arrangement elsewhere.</li>
</ul>
<p><strong>[CONFIRM: say how long the non-circumvention tail lasts.]</strong></p>
<h3>What happens to revenue already earned</h3>
<p><strong>[CONFIRM: this rule is not yet decided. Do not publish this page until it is, and have the wording checked by a professional.]</strong></p>
<h3>Before you end a partnership</h3>
<ul>
<li>Talk to your grower first. Many problems are easier to solve by talking.</li>
<li>Read the terms of your partnership.</li>
<li>If you are unsure of your rights, get independent legal advice.</li>
</ul>
''',
    },
    {
        "key": "costs-and-fees",
        "title": "Does Crescopus cost anything?",
        "tags": ["costs", "fees", "pricing", "free"],
        "summary": "Listing and matching are free for now. A platform fee on the ongoing revenue share is planned, separate from the split between you and your grower.",
        "disclaimer": NOTICE,
        "body": '''
<p>Listing your app and being matched with growers are free for now.</p>
<p>Crescopus plans to charge a <strong>platform fee</strong> on the ongoing revenue share in future. It would be separate from the split between you and your grower, so it would not come out of your grower's share or yours. The planned fee is linked to the revenue a partnership earns, not to an upfront charge.</p>
<p><strong>[CONFIRM: check the current position, state the fee once it is set, and say how and when users will be told before any fee applies.]</strong></p>
''',
    },
    {
        "key": "how-crescopus-differs",
        "title": "How is Crescopus different from selling my app or hiring a marketer?",
        "tags": ["comparison", "alternatives", "selling"],
        "summary": "You keep your app and share the upside with a grower, instead of selling it or paying upfront for marketing whether or not it works.",
        "disclaimer": None,
        "body": '''
<h3>Selling your app</h3>
<p>You receive a one-off payment and give up ownership and any future income.</p>
<h3>Hiring a marketer or agency</h3>
<p>You usually pay upfront or on a fixed fee, whether or not the app grows.</p>
<h3>A Crescopus partnership</h3>
<p>You keep your app, and your grower is rewarded through a share of the revenue their work brings in. Both of you have a reason to see the app succeed.</p>
<h3>The trade-offs</h3>
<ul>
<li>You give up part of the future revenue from the stream your grower works on</li>
<li>If the app does not grow, your grower may earn little, so choose someone you trust to stay committed</li>
<li>It is an ongoing working relationship, not a one-off transaction</li>
</ul>
''',
    },
    {
        "key": "getting-help",
        "title": "Who can I contact if I need help?",
        "tags": ["start", "help", "support", "contact"],
        "summary": "For questions about using Crescopus, contact support. For legal, tax or money disputes, get independent professional advice.",
        "disclaimer": NOTICE,
        "body": '''
<h3>Questions about using Crescopus</h3>
<p>Contact our support team. <strong>[CONFIRM: add the support email address or contact page.]</strong></p>
<h3>Disagreements with your grower</h3>
<p>Start by talking inside the partnership messages. <strong>[CONFIRM: say whether Crescopus helps to resolve disagreements, and how.]</strong></p>
<h3>Legal, tax or financial questions</h3>
<p>Crescopus cannot give legal, tax or financial advice. If you have a dispute about money, a contract or your rights, please get independent professional advice.</p>
<p>This guide only shows information that has been written and approved by Crescopus, so it cannot answer everything.</p>
''',
    },
]


def fields_for(page):
    """The content fields for one page, in the shape the content library expects."""
    return {
        "summary": {"type": "short_text", "label": "In short", "value": page["summary"]},
        "body": {"type": "rich_text", "label": "More detail", "value": page["body"].strip()},
    }
