# Slack export — channel #nevis-onboarding

Export of a shared channel between the Nevis onboarding team and the client
(Beaconcrest Advisors, a fictional RIA). Client-side contact is **Dana Ruiz,
Head of Operations**. Nevis-side is **Alex (onboarding)**. Newest messages last.

---

**Alex** — Mon 10:02
Hi Dana — starting to map your book into our model. A few things I want to get right
before I trust the numbers. First: a chunk of the clients in your Notion have
`Status = Legacy`. What does Legacy mean to you operationally?

**Dana Ruiz** — Mon 10:14
Legacy = the book we picked up when we acquired **Harborline Advisors** back in 2019.
They're normal active clients now, nothing special about how we service them. We just
keep the tag so we can report on the acquired book separately when the partners ask.

**Alex** — Mon 10:15
Got it — so treat them as active clients, but preserve the "acquired from Harborline"
lineage somewhere. 👍

**Dana Ruiz** — Mon 10:16
Exactly.

**Alex** — Mon 10:31
Next: your Notion has an **Advisor** field and a separate **Service Rep** field, and
sometimes only one of the two is filled in. Which one is the "real" advisor for a
household in your world?

**Dana Ruiz** — Mon 10:40
The Advisor is the one who owns the relationship — that's the real advisor. Service Rep
is just whoever handles day-to-day paperwork, can be a junior or an ops person, don't
treat them as the advisor. Where the Advisor field is blank that's honestly just sloppy
data entry on our side.

**Alex** — Mon 10:42
And when the Advisor is blank — safe to fall back to the Service Rep, or would
you rather we leave it unassigned and come back to you?

**Dana Ruiz** — Mon 10:49
Don't guess. Flag those to me and I'll tell you the right advisor. Except — heads up —
you'll see **A. Novak** in the Service Rep field on a couple of the Harborline clients.
That's Anna Novak, a contractor who left us last year. Those clients need reassigning,
so definitely surface anything still pointing at her.

**Alex** — Mon 11:05
Will do. On balances — the custodian file has both a Market Value and a Cost Basis
column. For "AUM" in your reporting, which one do you mean?

**Dana Ruiz** — Mon 11:07
Market value, always, as of the most recent quarter-end. Ignore cost basis, that's just
there for tax stuff.

**Alex** — Mon 11:20
One of the accounts (Al-Rashid) comes through in **EUR** from a European custodian.
Everything else is USD. How do you want that handled for reporting?

**Dana Ruiz** — Mon 11:23
We report everything in USD. That one's held in euros because the client is based in
Geneva. Convert it to USD for the totals — use whatever quarter-end FX rate you'd
normally use, just note that you did it.

**Alex** — Mon 11:41
Last two housekeeping ones. (1) I'm seeing **Dmitri Petrov** twice in Notion with
slightly different names. (2) The **Thompson** household shows as "Former"/"Churned."

**Dana Ruiz** — Mon 11:52
(1) Yeah, Petrov is a known duplicate — someone created him twice during the Notion
import and we never cleaned it up. Same person, just collapse them. (2) Thompson left us
in 2023, we're winding the last account down.
Mark them inactive, they shouldn't count toward active AUM.

**Alex** — Mon 11:53
Perfect, thank you — that unblocks most of it. I'll come back with a shortlist of the
ones I couldn't resolve from this.
