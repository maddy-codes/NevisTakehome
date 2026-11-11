# Blocker Ledger

Written by the resolver agent. 11 blocker(s) flagged, 9 case(s) decided without flagging.
Matrix rules are defined in `src/flag_matrix.py`.

## Blockers (flagged)

### blk_client_c4eea67c — Missing primary advisor  (rule F1, case `client:c4eea67c`)
- **Affected**: George Whitfield, Whitfield, CU-5005
- **Account CU-5005**: G. Whitfield, Pershing, 670,000 USD, as of 2025-06-30
- **Trigger**: Advisor is blank and only the departed Service Rep A. Novak is present.
- **Evidence**: CRM note: "Another Harborline client. Anna was looking after him before she left the firm — needs reassigning to someone current." Dana said not to fall back to Service Rep and to flag blank Advisor fields.
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana as George Whitfield's primary advisor.
  - Option B: Hold the Whitfield household without a primary advisor until Dana provides the reassignment.
  - Option C: Set the household inactive pending reassignment.
- **Proposed default**: Option B: Hold the Whitfield household without a primary advisor until Dana provides the reassignment.
- **Question**: Which current roster advisor should be the primary advisor for George Whitfield?

### blk_client_bc3491c1 — Missing primary advisor  (rule F1, case `client:bc3491c1`)
- **Affected**: Joris Vandermeer, Vandermeer, CU-6021
- **Account CU-6021**: Joris Vandermeer, Pershing, 1,620,000 USD, as of 2025-06-30
- **Trigger**: Advisor field is blank.
- **Evidence**: Joris Vandermeer has no Advisor and no Service Rep in the CRM record. Canonical rule requires one primary advisor per household; Dana instructed that blank Advisor fields must not be guessed or filled from another role.
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana as Joris Vandermeer's primary advisor.
  - Option B: Hold the Vandermeer household without a primary advisor until Dana provides the assignment.
  - Option C: Set the household inactive pending advisor assignment.
- **Proposed default**: Option B: Hold the Vandermeer household without a primary advisor until Dana provides the assignment.
- **Question**: Which current roster advisor should be the primary advisor for Joris Vandermeer?

### blk_client_511f8b2f — Missing primary advisor  (rule F1, case `client:511f8b2f`)
- **Affected**: Louis Petit, Petit, CU-6020
- **Account CU-6020**: Louis Petit, Schwab, 540,000 USD, as of 2025-06-30
- **Trigger**: Advisor field is blank; only Service Rep Marcus Webb is present.
- **Evidence**: CRM note: "Harborline book. Never got a proper advisor of record assigned." Dana said Service Rep is not the advisor and blank Advisor fields must be flagged.
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana as Louis Petit's primary advisor.
  - Option B: Hold the Petit household without a primary advisor until Dana provides the assignment.
  - Option C: Set the household inactive pending advisor assignment.
- **Proposed default**: Option B: Hold the Petit household without a primary advisor until Dana provides the assignment.
- **Question**: Which current roster advisor should be the primary advisor for Louis Petit?

### blk_client_504504a6 — Missing primary advisor and stale valuation  (rule F1, case `client:504504a6`)
- **Affected**: Maria Delgado, Delgado, CU-5004, Review — Delgado
- **Account CU-5004**: Maria Delgado, Schwab, 1,240,000 USD, as of 2024-12-31
- **Trigger**: Advisor field is blank and only Service Rep Marcus Webb is present; the sole account valuation predates the latest custodian quarter-end.
- **Evidence**: CRM note: "Marcus has been servicing the account but she doesn't really have a proper advisor of record assigned — should sort that out." Account CU-5004 is dated 2024-12-31, while the current custodian feed includes 2025-06-30. The meeting attendee is A. Novak, whom Dana identified as a departed contractor; that attendee is not an advisor assignment.
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana and retain the 2024-12-31 valuation pending a refreshed valuation decision.
  - Option B: Hold the Delgado household and CU-5004 out until Dana provides the advisor assignment and confirms how to handle the stale valuation.
  - Option C: Set the Delgado household inactive pending advisor reassignment and valuation review.
- **Proposed default**: Option B: Hold the Delgado household and CU-5004 out until Dana provides the advisor assignment and confirms how to handle the stale valuation.
- **Question**: Which current roster advisor should be primary for Maria Delgado, and should CU-5004's 2024-12-31 valuation be held pending a refreshed quarter-end value?

### blk_client_a2dd7e0b — Contradictory status information  (rule F4, case `client:a2dd7e0b`)
- **Affected**: Omar Farouk, Farouk Household, CU-6035
- **Account CU-6035**: Omar Farouk, Schwab, 1,660,000 USD, as of 2025-06-30
- **Trigger**: CRM Status is Active while the source tag is Deceased.
- **Evidence**: The record has Status "Active" and Tags "Deceased". No Slack message addresses Omar Farouk or resolves this contradiction.
- **Options**:
  - Option A: Mark Omar Farouk and the Farouk Household INACTIVE and exclude the $1,660,000 account from active AUM.
  - Option B: Retain Active status while Dana confirms whether the Deceased tag is erroneous or requires a household transition.
  - Option C: Hold the household and CU-6035 out of canonical output pending Dana's determination.
- **Proposed default**: Option A: Mark Omar Farouk and the Farouk Household INACTIVE and exclude the $1,660,000 account from active AUM.
- **Question**: Should the Deceased tag take precedence and the Farouk Household be marked INACTIVE, or should Status remain Active?

### blk_account_CU-5004 — missing primary advisor  (rule F1, case `account:CU-5004`)
- **Affected**: CU-5004, Maria Delgado, Delgado
- **Account CU-5004**: Maria Delgado, Schwab, 1,240,000 USD, as of 2024-12-31
- **Trigger**: The CRM Advisor field is blank; only Service Rep Marcus Webb is present, and the source note says the proper advisor of record is not assigned.
- **Evidence**: CRM note: "Marcus has been servicing the account but she doesn't really have a proper advisor of record assigned — should sort that out." Slack: "Don't guess. Flag those to me" when Advisor is blank.
- **Options**:
  - Option A: Assign a current roster advisor chosen by Dana as Maria Delgado's primary advisor and use the 2025-06-30 valuation when confirmed current.
  - Option B: Keep Maria Delgado's household unassigned and hold CU-5004 out of the canonical output pending Dana's advisor decision.
  - Option C: Treat Marcus Webb as the primary advisor, despite his being listed only as Service Rep.
- **Proposed default**: Option B
- **Question**: Which current roster advisor should own the Delgado household? Until confirmed, should CU-5004 remain held out because its primary advisor is missing and its last valuation is 2024-12-31?

### blk_account_CU-5011 — pending household treatment  (rule F7, case `account:CU-5011`)
- **Affected**: CU-5011, Kenji Nakamura, Nakamura Holdings LLC, Nakamura
- **Account CU-5011**: Nakamura, Kenji, Fidelity, 210,000 USD, as of 2025-06-30
- **Trigger**: The CRM note and meeting note state that the family is still deciding whether Kenji's personal IRA belongs under the LLC household or on its own.
- **Evidence**: CRM note: "Not sure whether we report the IRA under the LLC household or treat it as his own — flag for ops." Meeting note: "Family still deciding whether Kenji's IRA sits under the LLC or on its own."
- **Options**:
  - Option A: Roll CU-5011 into the existing Nakamura household with Nakamura Holdings LLC.
  - Option B: Create or use a separate personal household for Kenji Nakamura and roll CU-5011 there.
  - Option C: Hold CU-5011 out of the canonical output until Dana confirms the reporting treatment.
- **Proposed default**: Option C
- **Question**: Should Kenji Nakamura's personal IRA, CU-5011, roll into the Nakamura LLC household or be reported in a separate personal household?

### blk_account_CU-5010 — unmatched custodian account holder  (rule F2, case `account:CU-5010`)
- **Affected**: CU-5010, Carlos Vasquez
- **Account CU-5010**: Carlos Vasquez, Schwab, 980,000 USD, as of 2025-06-30
- **Trigger**: Carlos Vasquez has no matching CRM client or household in the supplied context.
- **Evidence**: The supplied cross-source context contains no matching CRM clients, notes, or meetings for Carlos Vasquez.
- **Options**:
  - Option A: Provide the existing CRM household that owns CU-5010.
  - Option B: Confirm that Carlos Vasquez is a current client and identify the household and primary advisor from the current roster.
  - Option C: Hold CU-5010 out of the canonical output until an existing household match is confirmed.
- **Proposed default**: Option C
- **Question**: Which existing CRM household and current primary advisor should own CU-5010 for Carlos Vasquez?

### blk_account_CU-6024 — stale active-household valuation  (rule F5, case `account:CU-6024`)
- **Affected**: CU-6024, Oliver Ashford, Ashford
- **Account CU-6024**: Oliver Ashford, Fidelity, 1,450,000 USD, as of 2024-09-30
- **Trigger**: The active Ashford household's account valuation is dated 2024-09-30, older than the 2025-06-30 quarter-end in the custodian feed.
- **Evidence**: Oliver Ashford is marked Active. CU-6024 has As_Of_Date 2024-09-30; the latest supplied custodian quarter-end is 2025-06-30.
- **Options**:
  - Option A: Confirm that the 2024-09-30 market value remains acceptable for canonical reporting.
  - Option B: Retain CU-6024 with its original date and tag it pending a refreshed valuation.
  - Option C: Hold CU-6024 out of active AUM until a 2025-06-30 or later valuation is supplied.
- **Proposed default**: Option C
- **Question**: Should CU-6024 be held out of active AUM until a valuation at the 2025-06-30 quarter-end or later is available?

### blk_account_CU-6025 — unmatched custodian account holder  (rule F2, case `account:CU-6025`)
- **Affected**: CU-6025, Priyanka Mehta
- **Account CU-6025**: Priyanka Mehta, Schwab, 670,000 USD, as of 2025-06-30
- **Trigger**: Priyanka Mehta has no matching CRM client or household in the supplied context.
- **Evidence**: The supplied cross-source context contains no matching CRM clients, notes, or meetings for Priyanka Mehta.
- **Options**:
  - Option A: Provide the existing CRM household that owns CU-6025.
  - Option B: Confirm that Priyanka Mehta is a current client and identify the household and primary advisor from the current roster.
  - Option C: Hold CU-6025 out of the canonical output until an existing household match is confirmed.
- **Proposed default**: Option C
- **Question**: Which existing CRM household and current primary advisor should own CU-6025 for Priyanka Mehta?

### blk_interaction_02076175 — meeting client not in CRM  (rule F3, case `interaction:02076175`)
- **Affected**: Intro Call — Redwood Capital, Redwood Capital
- **Trigger**: The prospecting meeting names Redwood Capital, but no existing CRM household matches it.
- **Evidence**: Meeting note: "Referred lead — not in the CRM yet." There are no matching CRM clients or custodian accounts.
- **Options**:
  - Option A: Provide an existing CRM household to which Redwood Capital's prospecting interaction belongs.
  - Option B: Keep the interaction out of the canonical output until Redwood Capital is onboarded as an existing household.
  - Option C: Create a new household from the prospecting meeting.
- **Proposed default**: Option B
- **Question**: Does Redwood Capital correspond to an existing CRM household, or should this prospecting interaction remain outside the canonical output until the lead is onboarded?

## Decided without flagging

- `client:2f805d00` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian-holder match for Francesca Bianchi; active Bianchi household and Sofia Marchetti map to ADV-005. Account CU-6022 is Individual, CHF, market value 2,100,000 as of 2025-06-30. Preserve the note's Geneva and CHF facts; the assembler must convert CHF to USD at quarter-end. Cost basis is not used.
- `client:f91a0e32` — auto_apply (confidence 0.98, deterministic): Gerald Voss has an explicit Active status, Grace Bennett maps to ADV-007, and the Held Away tag is a business-meaningful source attribute. The custodian context contains CU-6023 for Bill Fitzgerald, not Gerald Voss; it is not assigned to Voss. With no known Voss account, AUM remains null rather than zero.
- `client:32e22ca3` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian-holder match links Mei Lin Tan to Tan Household and CU-6027. Sofia Marchetti maps to ADV-005; status is Active and the account is Individual, USD, $495,000 as of 2025-06-30. The note is a meaningful contact preference and is preserved.
- `client:99068c0d` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian-holder match links Sophie Laurent to Laurent Household and CU-6039. James Okafor maps to ADV-004; status is Active and the account is Individual, USD, $530,000 as of 2025-06-30. Preserve the referral note and Referred By field as business context.
- `client:b669d445` — auto_apply (confidence 0.99, deterministic): Exact CRM and custodian-holder match links Wei Zhang to Zhang Household and CU-6033. James Okafor maps to ADV-004; status is Active and the account is Individual, USD, $1,930,000 as of 2025-06-30. Preserve the quarterly review cadence and Do Not Contact instruction.
- `client:271b01a3` — auto_apply (confidence 0.99, deterministic): Exact CRM, custodian, and meeting match for Yusuf Al-Rashid. Advisor Marcus Webb is on the CRM record, the household is Al-Rashid, and the account is a 2025-06-30 EUR account. Preserve the source note that the client is based in Geneva and the account is held in euros; the assembler converts the market value to USD at quarter-end. Website and other empty fields have no canonical business meaning and are dropped.
- `account:CU-5009` — auto_apply (confidence 0.99, slack_knowledge): Thompson is a Slack-confirmed departed household: Former and Churned map to INACTIVE, and the last account is being wound down. The existing confirmed holder mapping links Thompson Joint to the Thompson household. The stale 2023-09-30 valuation does not require a stale-valuation blocker because Slack explicitly settled Thompson's inactive treatment.
- `interaction:9ca85635` — auto_apply (confidence 0.98, llm): The interaction client Nora Lindholm exactly matches the existing active Lindholm Household and its current primary advisor Priya Raman. A missing meeting attendee is not a canonical household-link blocker; the interaction can roll to the existing household without inventing an attendee.
- `interaction:0ec3b693` — auto_apply (confidence 0.99, slack_knowledge): The existing confirmed meeting alias maps Thompson to Bill Thompson, and the Bill/Sarah records share the Thompson household. Slack confirms the household is inactive and should not count toward active AUM; the interaction can still be retained against that existing household. The meeting note is preserved as a business-meaningful operational note.
