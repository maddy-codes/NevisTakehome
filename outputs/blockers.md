# Blocker Ledger

Written by the resolver agent. 11 blocker(s) flagged, 9 case(s) decided without flagging.
Matrix rules are defined in `src/flag_matrix.py`.

## Blockers (flagged)

### blk_client_c4eea67c — Missing primary advisor  (rule F1, case `client:c4eea67c`)
- **Affected**: George Whitfield, Whitfield, CU-5005
- **Account CU-5005**: G. Whitfield, Pershing, 670,000 USD, as of 2025-06-30
- **Trigger**: The Advisor field is blank and the only named relationship person is departed contractor A. Novak.
- **Evidence**: Advisor: null; Service Rep: “A. Novak”; Notes: “Another Harborline client. Anna was looking after him before she left the firm — needs reassigning to someone current.” Dana: “Don't guess. Flag those to me”; Dana identified A. Novak as a departed contractor.
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana.
  - Option B: Keep the household unassigned pending Dana’s advisor assignment.
  - Option C: Treat A. Novak as the advisor of record.
- **Proposed default**: Option B — keep the household unassigned pending Dana’s advisor assignment.
- **Question**: Which current roster advisor should be the primary advisor for the Whitfield household?

### blk_client_bc3491c1 — Missing primary advisor  (rule F1, case `client:bc3491c1`)
- **Affected**: Joris Vandermeer, Vandermeer, CU-6021
- **Account CU-6021**: Joris Vandermeer, Pershing, 1,620,000 USD, as of 2025-06-30
- **Trigger**: The active household has no primary advisor in the CRM record.
- **Evidence**: Advisor: null; Service Rep: null; Name: “Joris Vandermeer”. Dana: “Don't guess. Flag those to me and I'll tell you the right advisor.”
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana.
  - Option B: Keep the household unassigned pending Dana’s advisor assignment.
- **Proposed default**: Option B — keep the household unassigned pending Dana’s advisor assignment.
- **Question**: Which current roster advisor should be the primary advisor for the Vandermeer household?

### blk_client_511f8b2f — Missing primary advisor  (rule F1, case `client:511f8b2f`)
- **Affected**: Louis Petit, Petit, CU-6020
- **Account CU-6020**: Louis Petit, Schwab, 540,000 USD, as of 2025-06-30
- **Trigger**: The Advisor field is blank; Marcus Webb is listed only as Service Rep.
- **Evidence**: Advisor: null; Service Rep: “Marcus Webb”; Notes: “Harborline book. Never got a proper advisor of record assigned.” Dana said Service Rep is not the real advisor and blank Advisor fields must be flagged.
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana.
  - Option B: Keep the household unassigned pending Dana’s advisor assignment.
  - Option C: Treat Marcus Webb as the primary advisor.
- **Proposed default**: Option B — keep the household unassigned pending Dana’s advisor assignment.
- **Question**: Which current roster advisor should be the primary advisor for the Petit household?

### blk_client_504504a6 — Missing primary advisor  (rule F1, case `client:504504a6`)
- **Affected**: Maria Delgado, Delgado, CU-5004, Review — Delgado
- **Account CU-5004**: Maria Delgado, Schwab, 1,240,000 USD, as of 2024-12-31
- **Trigger**: The Advisor field is blank; the note expressly says Maria has no proper advisor of record. Marcus Webb is only the Service Rep and A. Novak is departed.
- **Evidence**: Advisor: null; Service Rep: “Marcus Webb”; Notes: “Marcus has been servicing the account but she doesn't really have a proper advisor of record assigned — should sort that out.” Meeting attendee: “A. Novak”. Dana said Service Rep is not the advisor and A. Novak is a departed contractor.
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana.
  - Option B: Keep the household unassigned pending Dana’s advisor assignment.
  - Option C: Treat Marcus Webb as the primary advisor.
- **Proposed default**: Option B — keep the household unassigned pending Dana’s advisor assignment.
- **Question**: Which current roster advisor should be the primary advisor for the Delgado household?

### blk_client_a2dd7e0b — Active status conflicts with deceased tag  (rule F4, case `client:a2dd7e0b`)
- **Affected**: Omar Farouk, Farouk Household, CU-6035
- **Account CU-6035**: Omar Farouk, Schwab, 1,660,000 USD, as of 2025-06-30
- **Trigger**: The CRM status is Active while the record carries the tag “Deceased.”
- **Evidence**: Status: “Active”; Tags: “Deceased”; Account CU-6035 is held by “Omar Farouk” with market value $1,660,000 as of 2025-06-30.
- **Options**:
  - Option A: Mark the Farouk household INACTIVE based on the Deceased tag.
  - Option B: Retain ACTIVE status pending Dana’s confirmation.
  - Option C: Hold the household and account out of canonical output pending confirmation.
- **Proposed default**: Option C — hold the household and account out of canonical output pending confirmation.
- **Question**: Should the Farouk household remain ACTIVE, be marked INACTIVE, or be held pending estate-status confirmation?

### blk_account_CU-5004 — Missing primary advisor  (rule F1, case `account:CU-5004`)
- **Affected**: CU-5004, Maria Delgado, Delgado
- **Account CU-5004**: Maria Delgado, Schwab, 1,240,000 USD, as of 2024-12-31
- **Trigger**: Maria Delgado's Advisor field is blank; Marcus Webb appears only as Service Rep.
- **Evidence**: Advisor: null; Service Rep: Marcus Webb. Note: "Marcus has been servicing the account but she doesn't really have a proper advisor of record assigned — should sort that out." Dana: "Don't guess. Flag those to me".
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana as Maria Delgado's primary advisor.
  - Option B: Confirm Maria Delgado should remain unassigned pending a later advisor decision.
  - Option C: Confirm another CRM advisor assignment supplied by Dana.
- **Proposed default**: Option B — hold the account out rather than fabricate a primary advisor.
- **Question**: Which current roster advisor should be the primary advisor of record for Maria Delgado?

### blk_account_CU-5011 — Pending household decision  (rule F7, case `account:CU-5011`)
- **Affected**: CU-5011, Kenji Nakamura, Nakamura Holdings LLC, Nakamura
- **Account CU-5011**: Nakamura, Kenji, Fidelity, 210,000 USD, as of 2025-06-30
- **Trigger**: Operations has not decided whether Kenji's personal IRA belongs under the LLC household or separately.
- **Evidence**: CRM note: "Not sure whether we report the IRA under the LLC household or treat it as his own — flag for ops." Meeting note: "Family still deciding whether Kenji's IRA sits under the LLC or on its own."
- **Options**:
  - Option A: Roll CU-5011 into the Nakamura household with Nakamura Holdings LLC.
  - Option B: Create or use a separate personal household for Kenji's IRA.
  - Option C: Keep CU-5011 pending until the family decision is final.
- **Proposed default**: Option C — hold the IRA out until the household treatment is confirmed.
- **Question**: Should CU-5011 roll into the Nakamura household with the LLC, or be treated as Kenji's separate personal account?

### blk_account_CU-5010 — Unmatched custodian account holder  (rule F2, case `account:CU-5010`)
- **Affected**: CU-5010, Carlos Vasquez
- **Account CU-5010**: Carlos Vasquez, Schwab, 980,000 USD, as of 2025-06-30
- **Trigger**: Carlos Vasquez cannot be matched to a CRM client or household in the supplied context.
- **Evidence**: Account holder: "Carlos Vasquez"; matching_crm_clients_and_notes: []; matching_meetings: [].
- **Options**:
  - Option A: Provide the existing CRM client or household for Carlos Vasquez.
  - Option B: Confirm Carlos Vasquez is a new client and provide the household to use.
  - Option C: Confirm the account should be excluded from the canonical book.
- **Proposed default**: Option A — hold the account until Dana identifies the existing household.
- **Question**: Which existing CRM household should receive custodian account CU-5010 for Carlos Vasquez?

### blk_account_CU-6024 — Stale active-household valuation  (rule F5, case `account:CU-6024`)
- **Affected**: CU-6024, Oliver Ashford, Ashford
- **Account CU-6024**: Oliver Ashford, Fidelity, 1,450,000 USD, as of 2024-09-30
- **Trigger**: The account belongs to an ACTIVE household, but its valuation is dated 2024-09-30 while the most recent custodian quarter-end is 2025-06-30.
- **Evidence**: Household status: Active. CU-6024 market value: $1,450,000; As_Of_Date: 2024-09-30. Supplied custodian records include As_Of_Date: 2025-06-30.
- **Options**:
  - Option A: Accept the 2024-09-30 valuation for canonical reporting.
  - Option B: Obtain a refreshed 2025-06-30 valuation and replace the stale value.
  - Option C: Keep the account pending until the valuation is refreshed or explicitly accepted.
- **Proposed default**: Option C — retain the source value and date with a pending tag, but hold it from finalized AUM reporting.
- **Question**: Should CU-6024's 2024-09-30 market value be accepted, or should operations obtain a refreshed 2025-06-30 valuation?

### blk_account_CU-6025 — Unmatched custodian account holder  (rule F2, case `account:CU-6025`)
- **Affected**: CU-6025, Priyanka Mehta
- **Account CU-6025**: Priyanka Mehta, Schwab, 670,000 USD, as of 2025-06-30
- **Trigger**: Priyanka Mehta cannot be matched to a CRM client or household in the supplied context.
- **Evidence**: Account holder: "Priyanka Mehta"; matching_crm_clients_and_notes: []; matching_meetings: [].
- **Options**:
  - Option A: Provide the existing CRM client or household for Priyanka Mehta.
  - Option B: Confirm Priyanka Mehta is a new client and provide the household to use.
  - Option C: Confirm the account should be excluded from the canonical book.
- **Proposed default**: Option A — hold the account until Dana identifies the existing household.
- **Question**: Which existing CRM household should receive custodian account CU-6025 for Priyanka Mehta?

### blk_interaction_02076175 — Meeting client not in CRM  (rule F3, case `interaction:02076175`)
- **Affected**: interaction:02076175, Redwood Capital, Intro Call — Redwood Capital
- **Trigger**: The Redwood Capital prospecting meeting has no matching CRM client or household.
- **Evidence**: Client: "Redwood Capital". Note: "Referred lead — not in the CRM yet." matching_crm_clients_and_notes: [].
- **Options**:
  - Option A: Add Redwood Capital to the CRM as a prospect household, then attach the interaction.
  - Option B: Identify an existing CRM household that Redwood Capital represents.
  - Option C: Exclude the interaction until a CRM household exists.
- **Proposed default**: Option C — hold the interaction out rather than mint a household from the meeting.
- **Question**: Which existing or newly created CRM household should receive the Redwood Capital prospecting interaction?

## Decided without flagging

- `client:2f805d00` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian-holder match for Francesca Bianchi; Advisor Sofia Marchetti matches roster ADV-005. The note's “francs” and custodian Currency CHF identify the non-USD account; the assembler should convert it to USD at quarter-end. Market value is $2,100,000 CHF before conversion, dated 2025-06-30.
- `client:f91a0e32` — auto_apply (confidence 0.99, deterministic): Exact CRM client record supplies primary advisor Grace Bennett (ADV-007), and the account-holder context is unrelated to this client. The Held Away tag is business-meaningful and should be preserved; no custodian account is matched, so AUM is null rather than zero.
- `client:32e22ca3` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian-holder match for Mei Lin Tan; Advisor Sofia Marchetti matches roster ADV-005. The note is a meaningful communication preference and should be preserved as a source tag.
- `client:99068c0d` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian-holder match for Sophie Laurent; Advisor James Okafor matches roster ADV-004. The referral note and Referred By value are business-meaningful and preserved.
- `client:b669d445` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian-holder match for Wei Zhang; Advisor James Okafor matches roster ADV-004. “Do Not Contact” and the quarterly review note are business-meaningful and preserved.
- `client:271b01a3` — auto_apply (confidence 0.99, deterministic): Exact CRM, custodian, and meeting match for Yusuf Al-Rashid. CRM names Marcus Webb as Advisor; the EUR note is corroborated by custodian account CU-5008 dated 2025-06-30. Apply market value in USD through the quarter-end FX process; do not use cost basis.
- `account:CU-5009` — auto_apply (confidence 0.99, slack_knowledge): Thompson Joint matches the Thompson household through Bill and Sarah Thompson. Slack explicitly directed that Thompson is INACTIVE and excluded from active AUM; the stale valuation therefore does not trigger the active-household stale valuation rule. Cost basis is ignored.
- `interaction:9ca85635` — auto_apply (confidence 0.99, llm): Nora Lindholm matches the existing Lindholm Household and the supplied context identifies Priya Raman as household advisor. Missing meeting attendee does not prevent the interaction from rolling up to the existing household.
- `interaction:0ec3b693` — auto_apply (confidence 0.99, slack_knowledge): The meeting client label Thompson is resolved to the existing Bill Thompson/Thompson household. Slack confirmed Thompson is inactive and excluded from active AUM; the re-engagement note does not change that settled status.
