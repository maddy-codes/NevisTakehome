# Blocker Ledger

Written by the resolver agent. 11 blocker(s) flagged, 9 case(s) decided without flagging.
Matrix rules are defined in `src/flag_matrix.py`.

## Blockers (flagged)

### blk_client_c4eea67c — Missing primary advisor; departed service representative  (rule F1, case `client:c4eea67c`)
- **Affected**: George Whitfield, Whitfield, CU-5005
- **Account CU-5005**: G. Whitfield, Pershing, 670,000 USD, as of 2025-06-30
- **Trigger**: The household has no primary Advisor, and its Service Rep is the departed contractor A. Novak.
- **Evidence**: Advisor: null; Service Rep: "A. Novak"; Notes: "Another Harborline client. Anna was looking after him before she left the firm — needs reassigning to someone current." Slack: "Don't guess. Flag those to me" and "A. Novak ... is Anna Novak, a contractor who left us last year."
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana.
  - Option B: Keep the household out of canonical output until Dana assigns a current roster advisor.
  - Option C: Retain the household with no primary advisor and tag it pending reassignment.
- **Proposed default**: Option B: Keep the household out of canonical output until Dana assigns a current roster advisor.
- **Question**: Which current roster advisor should own the Whitfield household?

### blk_client_bc3491c1 — Missing primary advisor  (rule F1, case `client:bc3491c1`)
- **Affected**: Joris Vandermeer, Vandermeer, CU-6021
- **Account CU-6021**: Joris Vandermeer, Pershing, 1,620,000 USD, as of 2025-06-30
- **Trigger**: The active Vandermeer household has an exact account match but no primary Advisor.
- **Evidence**: Advisor: null; Service Rep: null; Account Holder: "Joris Vandermeer"; Slack: "Where the Advisor field is blank ... Don't guess. Flag those to me."
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana.
  - Option B: Keep the household and account out of canonical output until Dana assigns the advisor.
  - Option C: Retain the household with no advisor and tag it pending assignment.
- **Proposed default**: Option B: Keep the household and account out of canonical output until Dana assigns the advisor.
- **Question**: Which current roster advisor should own the Vandermeer household?

### blk_client_511f8b2f — Missing primary advisor  (rule F1, case `client:511f8b2f`)
- **Affected**: Louis Petit, Petit, CU-6020
- **Account CU-6020**: Louis Petit, Schwab, 540,000 USD, as of 2025-06-30
- **Trigger**: The Harborline household has never been assigned a proper advisor of record; Marcus Webb is listed only as Service Rep.
- **Evidence**: Advisor: null; Service Rep: "Marcus Webb"; Notes: "Harborline book. Never got a proper advisor of record assigned." Slack: "Service Rep is just whoever handles day-to-day paperwork ... don't treat them as the advisor."
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana.
  - Option B: Keep the household and account out of canonical output until Dana assigns the advisor.
  - Option C: Retain the household with Marcus Webb as a service-rep tag and mark advisor assignment pending.
- **Proposed default**: Option B: Keep the household and account out of canonical output until Dana assigns the advisor.
- **Question**: Which current roster advisor should own the Petit household?

### blk_client_504504a6 — Missing primary advisor  (rule F1, case `client:504504a6`)
- **Affected**: Maria Delgado, Delgado, CU-5004, Review — Delgado
- **Account CU-5004**: Maria Delgado, Schwab, 1,240,000 USD, as of 2024-12-31
- **Trigger**: The household has no primary Advisor. Marcus Webb is servicing the account, while the note says a proper advisor of record still needs to be assigned.
- **Evidence**: Advisor: null; Service Rep: "Marcus Webb"; Notes: "Marcus has been servicing the account but she doesn't really have a proper advisor of record assigned — should sort that out." Slack: "Don't guess" and "Service Rep ... don't treat them as the advisor."
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana.
  - Option B: Keep the household and account out of canonical output until Dana assigns the advisor.
  - Option C: Retain the household with Marcus Webb preserved only as a service-rep tag and advisor assignment pending.
- **Proposed default**: Option B: Keep the household and account out of canonical output until Dana assigns the advisor.
- **Question**: Which current roster advisor should own the Delgado household?

### blk_client_a2dd7e0b — Active status contradicts deceased tag  (rule F4, case `client:a2dd7e0b`)
- **Affected**: Omar Farouk, Farouk Household, CU-6035
- **Account CU-6035**: Omar Farouk, Schwab, 1,660,000 USD, as of 2025-06-30
- **Trigger**: The CRM marks Omar Farouk ACTIVE while the same record carries the tag "Deceased."
- **Evidence**: Status: "Active"; Tags: "Deceased"; Account Holder: "Omar Farouk"; Account CU-6035 market value: $1,660,000. No Slack guidance addresses Omar Farouk's status.
- **Options**:
  - Option A: Keep Omar Farouk ACTIVE pending estate-handling instructions.
  - Option B: Set the Farouk household INACTIVE pending estate-handling instructions.
  - Option C: Hold the household and account out of canonical output until Dana confirms the status.
- **Proposed default**: Option B: Set the Farouk household INACTIVE pending estate-handling instructions.
- **Question**: Should the Farouk household be set INACTIVE because the CRM record is tagged "Deceased"?

### blk_account_CU-5004 — Missing primary advisor  (rule F1, case `account:CU-5004`)
- **Affected**: Maria Delgado, Delgado, CU-5004
- **Account CU-5004**: Maria Delgado, Schwab, 1,240,000 USD, as of 2024-12-31
- **Trigger**: The CRM Advisor field is blank; only Marcus Webb appears as Service Rep, and the note says Maria has no proper advisor of record.
- **Evidence**: Advisor: null; Service Rep: Marcus Webb; Notes: "Marcus has been servicing the account but she doesn't really have a proper advisor of record assigned — should sort that out." Slack: "Don't guess. Flag those to me" and "Service Rep is just whoever handles day-to-day paperwork ... don't treat them as the advisor."
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana as Maria Delgado's primary advisor.
  - Option B: Keep CU-5004 out of canonical reporting until Dana confirms the primary advisor.
  - Option C: Confirm whether Marcus Webb should be promoted from Service Rep to primary advisor.
- **Proposed default**: Option B — keep the account and household out of canonical reporting until the primary advisor is confirmed.
- **Question**: Which current roster advisor should be recorded as Maria Delgado's primary advisor?

### blk_account_CU-5011 — Pending household treatment decision  (rule F7, case `account:CU-5011`)
- **Affected**: Kenji Nakamura, Nakamura Holdings LLC, Nakamura, CU-5011
- **Account CU-5011**: Nakamura, Kenji, Fidelity, 210,000 USD, as of 2025-06-30
- **Trigger**: The CRM note and meeting note expressly leave the reporting treatment of Kenji's personal IRA undecided.
- **Evidence**: CRM Notes: "Not sure whether we report the IRA under the LLC household or treat it as his own — flag for ops." Meeting Notes: "Family still deciding whether Kenji's IRA sits under the LLC or on its own."
- **Options**:
  - Option A: Roll CU-5011 into the existing Nakamura household with the LLC account.
  - Option B: Treat CU-5011 as Kenji Nakamura's own household account, separate from the LLC account.
  - Option C: Hold CU-5011 out of canonical reporting until the family confirms the treatment.
- **Proposed default**: Option C — hold CU-5011 out until the household treatment is confirmed.
- **Question**: Should Kenji's personal IRA be reported under the Nakamura LLC household or separately under Kenji Nakamura?

### blk_account_CU-5010 — Unmatched custodian account holder  (rule F2, case `account:CU-5010`)
- **Affected**: Carlos Vasquez, CU-5010
- **Account CU-5010**: Carlos Vasquez, Schwab, 980,000 USD, as of 2025-06-30
- **Trigger**: Carlos Vasquez does not appear in the CRM context, so the account cannot be matched to exactly one existing household.
- **Evidence**: Account holder: Carlos Vasquez; matching CRM clients and notes: []; matching meetings: []; market value: $980,000; as of 2025-06-30.
- **Options**:
  - Option A: Identify an existing CRM client or household for Carlos Vasquez and link CU-5010 to it.
  - Option B: Confirm that Carlos Vasquez is a new client and provide the existing household record to use after CRM onboarding.
  - Option C: Hold CU-5010 out of canonical reporting until its household is confirmed.
- **Proposed default**: Option C — hold the account out until Carlos Vasquez is matched to exactly one household.
- **Question**: Which existing CRM household should receive account CU-5010 for Carlos Vasquez?

### blk_account_CU-6024 — Stale active-household valuation  (rule F5, case `account:CU-6024`)
- **Affected**: Oliver Ashford, Ashford, CU-6024
- **Account CU-6024**: Oliver Ashford, Fidelity, 1,450,000 USD, as of 2024-09-30
- **Trigger**: CU-6024 belongs to an ACTIVE household but its valuation is dated 2024-09-30, older than the 2025-06-30 quarter-end present in the custodian feed.
- **Evidence**: Household status: Active; account number: CU-6024; market value: $1,450,000; As_Of_Date: 2024-09-30; most recent quarter-end present in the feed: 2025-06-30. Slack: "Market value, always, as of the most recent quarter-end."
- **Options**:
  - Option A: Obtain and use a 2025-06-30 market value for CU-6024.
  - Option B: Retain the $1,450,000 value with its 2024-09-30 date and tag it as pending refresh.
  - Option C: Exclude CU-6024 from current active AUM until a current valuation is available.
- **Proposed default**: Option C — exclude the stale account from current active AUM until a 2025-06-30 valuation is available.
- **Question**: Should CU-6024 be refreshed to 2025-06-30, or held out of current active AUM until that valuation is available?

### blk_account_CU-6025 — Unmatched custodian account holder  (rule F2, case `account:CU-6025`)
- **Affected**: Priyanka Mehta, CU-6025
- **Account CU-6025**: Priyanka Mehta, Schwab, 670,000 USD, as of 2025-06-30
- **Trigger**: Priyanka Mehta does not appear in the CRM context, so the account cannot be matched to exactly one existing household.
- **Evidence**: Account holder: Priyanka Mehta; matching CRM clients and notes: []; matching meetings: []; market value: $670,000; as of 2025-06-30.
- **Options**:
  - Option A: Identify an existing CRM client or household for Priyanka Mehta and link CU-6025 to it.
  - Option B: Confirm that Priyanka Mehta is a new client and provide the existing household record to use after CRM onboarding.
  - Option C: Hold CU-6025 out of canonical reporting until its household is confirmed.
- **Proposed default**: Option C — hold the account out until Priyanka Mehta is matched to exactly one household.
- **Question**: Which existing CRM household should receive account CU-6025 for Priyanka Mehta?

### blk_interaction_02076175 — Meeting client not in CRM  (rule F3, case `interaction:02076175`)
- **Affected**: Redwood Capital, Intro Call — Redwood Capital
- **Trigger**: The prospecting meeting names Redwood Capital, but no existing CRM household matches it.
- **Evidence**: Meeting: Intro Call — Redwood Capital; Client: Redwood Capital; Notes: "Referred lead — not in the CRM yet." Matching CRM clients and notes: []; matching custodian accounts: [].
- **Options**:
  - Option A: Add Redwood Capital to the CRM as a prospect household and then attach the interaction.
  - Option B: Link the interaction to an existing household if Dana identifies Redwood Capital as an alias for one.
  - Option C: Hold the interaction out until Redwood Capital is matched to an existing household or formally added to the CRM.
- **Proposed default**: Option C — hold the interaction out until an existing household match or CRM prospect record is confirmed.
- **Question**: Should Redwood Capital be added as a new prospect household, or does it correspond to an existing CRM household?

## Decided without flagging

- `client:2f805d00` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian match for Francesca Bianchi; CU-6022 is a 2025-06-30 CHF individual account. Convert the CHF market value to USD using the quarter-end assembler rate. Preserve the meaningful Swiss custodian/francs note.
- `client:f91a0e32` — auto_apply (confidence 0.99, deterministic): The CRM record has valid roster advisor Grace Bennett. Held Away is a meaningful source attribute, not a contradiction. No custodian account is supplied for Voss, so AUM is null rather than zero.
- `client:32e22ca3` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian match for Mei Lin Tan; CU-6027 is a 2025-06-30 USD individual account. Preserve the meaningful contact preference from the note.
- `client:99068c0d` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian match for Sophie Laurent; CU-6039 is a 2025-06-30 USD individual account. Preserve the referral note and referring person as meaningful source attributes.
- `client:b669d445` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian match for Wei Zhang; CU-6033 is a 2025-06-30 USD individual account. Preserve the quarterly review note and Do Not Contact tag as meaningful source attributes.
- `client:271b01a3` — auto_apply (confidence 0.99, deterministic): Yusuf Al-Rashid has an exact CRM record, an exact custodian holder match, and a matching Review meeting attended by Marcus Webb. The account note says he is based in Geneva and held in euros; the account is dated 2025-06-30. EUR is converted to USD under the established quarter-end FX rule.
- `account:CU-5009` — auto_apply (confidence 0.99, slack_knowledge): The established rule maps Thompson Joint to the Thompson household. Slack confirmed the Thompson household is Former/Churned and must be marked INACTIVE and excluded from active AUM. The stale valuation does not trigger F5 because the household is inactive. Cost Basis is ignored under the established rule.
- `interaction:9ca85635` — auto_apply (confidence 0.99, llm): The meeting client Nora Lindholm exactly matches the active Lindholm Household and the existing account. A missing attendee does not prevent the interaction from rolling up to the existing household; no advisor is being inferred for the interaction.
- `interaction:0ec3b693` — auto_apply (confidence 0.99, slack_knowledge): The meeting client "Thompson" is covered by the established alias rule linking it to Bill Thompson and the Thompson household. Slack confirmed Thompson is inactive and should not count toward active AUM; the note about possible re-engagement does not override that settled status.
