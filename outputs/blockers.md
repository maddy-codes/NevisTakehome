# Blocker Ledger

Written by the resolver agent. 11 blocker(s) flagged, 9 case(s) decided without flagging.
Matrix rules are defined in `src/flag_matrix.py`.

## Blockers (flagged)

### blk_client_c4eea67c — Missing primary advisor  (rule F1, case `client:c4eea67c`)
- **Affected**: George Whitfield, Whitfield, CU-5005
- **Account CU-5005**: G. Whitfield, Pershing, 670,000 USD, as of 2025-06-30
- **Trigger**: Advisor is blank and the only operational assignment points to departed contractor A. Novak.
- **Evidence**: Advisor: null; Service Rep: "A. Novak"; note: "Another **Harborline** client. Anna was looking after him before she left the firm — needs reassigning to someone current." Dana: "A. Novak" is Anna Novak, a contractor who left and whose clients need reassigning.
- **Options**:
  - Option A — Assign George Whitfield to a current roster advisor chosen by Dana.
  - Option B — Keep the household unassigned pending Dana’s advisor decision.
  - Option C — Exclude the household and its account from canonical output until reassignment is confirmed.
- **Proposed default**: Option B — Keep the household unassigned pending Dana’s advisor decision.
- **Question**: Which current roster advisor should be the primary advisor for George Whitfield?

### blk_client_bc3491c1 — Missing primary advisor  (rule F1, case `client:bc3491c1`)
- **Affected**: Joris Vandermeer, Vandermeer, CU-6021
- **Account CU-6021**: Joris Vandermeer, Pershing, 1,620,000 USD, as of 2025-06-30
- **Trigger**: The Advisor field is blank and there is no Service Rep or other settled advisor assignment.
- **Evidence**: Advisor: null; Service Rep: null; Name: "Joris Vandermeer"; matching account: CU-6021.
- **Options**:
  - Option A — Assign Joris Vandermeer to a current roster advisor chosen by Dana.
  - Option B — Keep the household unassigned pending Dana’s advisor decision.
  - Option C — Exclude the household and CU-6021 from canonical output until reassignment is confirmed.
- **Proposed default**: Option B — Keep the household unassigned pending Dana’s advisor decision.
- **Question**: Which current roster advisor should be the primary advisor for Joris Vandermeer?

### blk_client_511f8b2f — Missing primary advisor  (rule F1, case `client:511f8b2f`)
- **Affected**: Louis Petit, Petit, CU-6020
- **Account CU-6020**: Louis Petit, Schwab, 540,000 USD, as of 2025-06-30
- **Trigger**: Advisor is blank; Marcus Webb is listed only as Service Rep and cannot be treated as the advisor.
- **Evidence**: Advisor: null; Service Rep: "Marcus Webb"; note: "**Harborline** book. Never got a proper advisor of record assigned." Dana: "Service Rep is just whoever handles day-to-day paperwork... don't treat them as the advisor."
- **Options**:
  - Option A — Assign Louis Petit to a current roster advisor chosen by Dana.
  - Option B — Keep the household unassigned pending Dana’s advisor decision.
  - Option C — Exclude the household and CU-6020 from canonical output until reassignment is confirmed.
- **Proposed default**: Option B — Keep the household unassigned pending Dana’s advisor decision.
- **Question**: Which current roster advisor should be the primary advisor for Louis Petit?

### blk_client_504504a6 — Missing primary advisor  (rule F1, case `client:504504a6`)
- **Affected**: Maria Delgado, Delgado, CU-5004, Review — Delgado
- **Account CU-5004**: Maria Delgado, Schwab, 1,240,000 USD, as of 2024-12-31
- **Trigger**: No primary advisor is assigned; the Service Rep is Marcus Webb and the related meeting was attended by departed contractor A. Novak. The account valuation is also older than the latest custodian quarter-end.
- **Evidence**: Advisor: null; Service Rep: "Marcus Webb"; note: "Marcus has been servicing the account but she doesn't really have a proper advisor of record assigned — should sort that out." Meeting attendee: "A. Novak"; CU-5004 As_Of_Date: "2024-12-31"; latest feed quarter-end: "2025-06-30".
- **Options**:
  - Option A — Assign Maria Delgado to a current roster advisor chosen by Dana and confirm whether the 2024-12-31 valuation should be retained pending refresh.
  - Option B — Keep the household unassigned and its account out of canonical output pending advisor assignment and valuation confirmation.
  - Option C — Assign a current roster advisor chosen by Dana, retain the dated valuation, and tag the account pending a refreshed custodian value.
- **Proposed default**: Option B — Keep the household unassigned and its account out of canonical output pending advisor assignment and valuation confirmation.
- **Question**: Which current roster advisor should be the primary advisor for Maria Delgado?

### blk_client_a2dd7e0b — Contradictory status and lifecycle tag  (rule F4, case `client:a2dd7e0b`)
- **Affected**: Omar Farouk, Farouk Household, CU-6035
- **Account CU-6035**: Omar Farouk, Schwab, 1,660,000 USD, as of 2025-06-30
- **Trigger**: The same CRM record is marked Active and tagged Deceased.
- **Evidence**: Status: "Active"; Tags: "Deceased"; account CU-6035 is dated 2025-06-30. No Slack message addresses Omar Farouk’s status.
- **Options**:
  - Option A — Retain Omar Farouk as ACTIVE and preserve the Deceased tag pending confirmation.
  - Option B — Mark Omar Farouk INACTIVE and exclude the account from active AUM pending confirmation.
  - Option C — Hold the household and account out of canonical output until the status is confirmed.
- **Proposed default**: Option B — Mark Omar Farouk INACTIVE and exclude the account from active AUM pending confirmation.
- **Question**: Should Omar Farouk remain ACTIVE or be marked INACTIVE because of the Deceased tag?

### blk_account_CU-5004 — Missing primary advisor  (rule F1, case `account:CU-5004`)
- **Affected**: CU-5004, Maria Delgado, Delgado
- **Account CU-5004**: Maria Delgado, Schwab, 1,240,000 USD, as of 2024-12-31
- **Trigger**: Maria Delgado has no CRM Advisor; Marcus Webb is listed only as Service Rep, and the meeting attendee was departed contractor A. Novak.
- **Evidence**: CRM: "proper advisor of record assigned" is missing. Slack: "Don't guess. Flag those to me" and A. Novak was "a contractor who left us last year."
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana.
  - Option B: Hold CU-5004 out until reassignment is confirmed.
  - Option C: Assign Marcus Webb as primary advisor.
- **Proposed default**: Option B — hold CU-5004 out until reassignment is confirmed.
- **Question**: Which current roster advisor should be primary for Maria Delgado's Delgado household?

### blk_account_CU-5011 — Pending household treatment decision  (rule F7, case `account:CU-5011`)
- **Affected**: CU-5011, Kenji Nakamura, Nakamura Holdings LLC, Nakamura
- **Account CU-5011**: Nakamura, Kenji, Fidelity, 210,000 USD, as of 2025-06-30
- **Trigger**: Operations/family have not decided whether Kenji's IRA belongs under the LLC household or is treated as his own.
- **Evidence**: CRM and meeting notes explicitly state the household treatment is undecided and should be flagged for ops.
- **Options**:
  - Option A: Roll CU-5011 into Nakamura household with Nakamura Holdings LLC.
  - Option B: Treat CU-5011 as Kenji Nakamura's own household account.
  - Option C: Hold CU-5011 out until treatment is confirmed.
- **Proposed default**: Option C — hold CU-5011 out until treatment is confirmed.
- **Question**: Should CU-5011 be reported under the Nakamura LLC household or as Kenji Nakamura's own account?

### blk_account_CU-5010 — Unmatched custodian account holder  (rule F2, case `account:CU-5010`)
- **Affected**: CU-5010, Carlos Vasquez
- **Account CU-5010**: Carlos Vasquez, Schwab, 980,000 USD, as of 2025-06-30
- **Trigger**: Carlos Vasquez has no matching CRM client or household, so the $980,000 account cannot be assigned to exactly one household.
- **Evidence**: Custodian: CU-5010, Carlos Vasquez, Market Value 980000, As_Of_Date 2025-06-30. CRM and meeting matches are empty.
- **Options**:
  - Option A: Link the account to an existing CRM household chosen by Dana.
  - Option B: Confirm Carlos Vasquez as a new client household and provide the primary advisor.
  - Option C: Hold CU-5010 out until ownership is confirmed.
- **Proposed default**: Option C — hold CU-5010 out until ownership is confirmed.
- **Question**: Which household should own CU-5010?

### blk_account_CU-6024 — Stale valuation in active household  (rule F5, case `account:CU-6024`)
- **Affected**: CU-6024, Oliver Ashford, Ashford
- **Account CU-6024**: Oliver Ashford, Fidelity, 1,450,000 USD, as of 2024-09-30
- **Trigger**: CU-6024's valuation is older than the most recent quarter-end in the custodian feed; Slack does not address stale valuations.
- **Evidence**: CU-6024 As_Of_Date: 2024-09-30; latest feed quarter-end: 2025-06-30; Oliver Ashford Status: Active.
- **Options**:
  - Option A: Retain $1,450,000 dated 2024-09-30 with a pending tag.
  - Option B: Hold CU-6024 out of current AUM until a 2025-06-30 valuation is supplied.
  - Option C: Replace it with a current-quarter value chosen by Dana.
- **Proposed default**: Option B — hold CU-6024 out until a 2025-06-30 valuation is supplied.
- **Question**: Should CU-6024 be held out of current AUM until a 2025-06-30 valuation is supplied?

### blk_account_CU-6025 — Unmatched custodian account holder  (rule F2, case `account:CU-6025`)
- **Affected**: CU-6025, Priyanka Mehta
- **Account CU-6025**: Priyanka Mehta, Schwab, 670,000 USD, as of 2025-06-30
- **Trigger**: Priyanka Mehta has no matching CRM client or household, so the $670,000 account cannot be assigned to exactly one household.
- **Evidence**: Custodian: CU-6025, Priyanka Mehta, Market Value 670000, As_Of_Date 2025-06-30. CRM and meeting matches are empty.
- **Options**:
  - Option A: Link the account to an existing CRM household chosen by Dana.
  - Option B: Confirm Priyanka Mehta as a new client household and provide the primary advisor.
  - Option C: Hold CU-6025 out until ownership is confirmed.
- **Proposed default**: Option C — hold CU-6025 out until ownership is confirmed.
- **Question**: Which household should own CU-6025?

### blk_interaction_02076175 — Meeting client not in CRM  (rule F3, case `interaction:02076175`)
- **Affected**: interaction:02076175, Redwood Capital
- **Trigger**: Redwood Capital has no existing CRM household and the note says the lead is not in the CRM.
- **Evidence**: Meeting note: "Referred lead — not in the CRM yet." Matching CRM clients and accounts are empty.
- **Options**:
  - Option A: Add/confirm Redwood Capital as a CRM prospect household.
  - Option B: Link the interaction to an existing household chosen by Dana.
  - Option C: Hold the interaction out until a CRM household is confirmed.
- **Proposed default**: Option C — hold the interaction out until a CRM household is confirmed.
- **Question**: Which CRM household should own the Redwood Capital interaction, or should Redwood Capital first be added as a prospect?

## Decided without flagging

- `client:2f805d00` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian match for Francesca Bianchi; account CU-6022 is an Individual account dated 2025-06-30. The CHF balance is retained for assembler quarter-end conversion to USD. Notes preserve the Geneva/Swiss-custodian context.
- `client:f91a0e32` — auto_apply (confidence 0.98, deterministic): Gerald Voss has a populated roster advisor, Grace Bennett, and no custodian account was supplied. The Held Away tag is business meaningful and is preserved; with no known account, AUM remains null rather than zero.
- `client:32e22ca3` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian holder match for Mei Lin Tan; CU-6027 is an Individual USD account dated 2025-06-30. The communication preference in the note is preserved as a source tag.
- `client:99068c0d` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian holder match for Sophie Laurent; CU-6039 is an Individual USD account dated 2025-06-30. The referral note and referring person are preserved as business context.
- `client:b669d445` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian holder match for Wei Zhang; CU-6033 is an Individual USD account dated 2025-06-30. The quarterly review note and Do Not Contact tag are preserved.
- `client:271b01a3` — auto_apply (confidence 0.99, deterministic): Exact CRM, custodian, and meeting match for Yusuf Al-Rashid; Marcus Webb is the roster advisor. The note and EUR custodian record are consistent.
- `account:CU-5009` — auto_apply (confidence 0.99, slack_knowledge): Thompson Joint matches Bill and Sarah Thompson's joint household. Dana confirmed Thompson left in 2023 and should be inactive; stale valuation does not trigger F5 for an inactive household.
- `interaction:9ca85635` — auto_apply (confidence 0.99, llm): Nora Lindholm exactly matches the active Lindholm Household, whose primary advisor is Priya Raman. A blank attendee does not prevent household linkage.
- `interaction:0ec3b693` — auto_apply (confidence 0.99, llm): The meeting alias Thompson resolves to Bill Thompson and the existing Thompson household. Slack confirms the household is inactive; the winding-down note is retained as a business note.
