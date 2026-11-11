# Round 2 Clarifications — Beaconcrest Advisors

Operational decisions and proposed defaults following Round 1 onboarding review.

---

### Operational Decisions Required

### 1. Missing primary advisor; departed service representative — Which current roster advisor should own each of the Whitfield, Vandermeer, Petit and Delgado households?

- **Trigger**: The Whitfield, Vandermeer, Petit and Delgado households have no primary Advisor. Whitfield's Service Rep is the departed contractor A. Novak; Petit and Delgado show Marcus Webb only as Service Rep; Vandermeer has no Service Rep.
- **Evidence**: George Whitfield / Whitfield / CU-5005 (Pershing; $670,000; as of 2025-06-30); Joris Vandermeer / Vandermeer / CU-6021 (Pershing; $1,620,000; as of 2025-06-30); Louis Petit / Petit / CU-6020 (Schwab; $540,000; as of 2025-06-30); Maria Delgado / Delgado / CU-5004 / Review — Delgado (Schwab; $1,240,000; as of 2024-12-31). Advisor: null for all five entries. Service Rep: "A. Novak" for Whitfield; "Marcus Webb" for Petit and Delgado; null for Vandermeer. Notes include: "Another Harborline client. Anna was looking after him before she left the firm — needs reassigning to someone current."; "Harborline book. Never got a proper advisor of record assigned."; and "Marcus has been servicing the account but she doesn't really have a proper advisor of record assigned — should sort that out." Slack: "Don't guess. Flag those to me"; "A. Novak ... is Anna Novak, a contractor who left us last year."; and "Service Rep is just whoever handles day-to-day paperwork ... don't treat them as the advisor."
- **Candidate Options**:
  - **Option A**: Assign a current roster advisor chosen by Dana to each household.
  - **Option B**: Exclude each household and account from reporting until Dana assigns a current roster advisor.
  - **Option C**: Retain each household without a primary advisor and mark the assignment pending, preserving the Service Rep information where present.
- **Proposed Default**: **Option B — exclude each household and account from reporting until Dana assigns a current roster advisor.**

### 2. Active status contradicts deceased tag — Should the Farouk household be set INACTIVE because the CRM record is tagged "Deceased"?

- **Trigger**: The CRM marks Omar Farouk ACTIVE while the same record carries the tag "Deceased."
- **Evidence**: Omar Farouk / Farouk Household / CU-6035 (Schwab; $1,660,000; as of 2025-06-30). Status: "Active"; Tags: "Deceased"; Account Holder: "Omar Farouk." No Slack guidance addresses Omar Farouk's status.
- **Candidate Options**:
  - **Option A**: Keep Omar Farouk ACTIVE pending estate-handling instructions.
  - **Option B**: Set the Farouk household INACTIVE pending estate-handling instructions.
  - **Option C**: Exclude the household and account from reporting until Dana confirms the status.
- **Proposed Default**: **Option B: Set the Farouk household INACTIVE pending estate-handling instructions.**

### 3. Pending household treatment decision — Should Kenji's personal IRA be reported under the Nakamura LLC household or separately under Kenji Nakamura?

- **Trigger**: The CRM note and meeting note expressly leave the reporting treatment of Kenji's personal IRA undecided.
- **Evidence**: Kenji Nakamura / Nakamura Holdings LLC / Nakamura / CU-5011 (Fidelity; $210,000; as of 2025-06-30). CRM Notes: "Not sure whether we report the IRA under the LLC household or treat it as his own — flag for ops." Meeting Notes: "Family still deciding whether Kenji's IRA sits under the LLC or on its own."
- **Candidate Options**:
  - **Option A**: Roll CU-5011 into the existing Nakamura household with the LLC account.
  - **Option B**: Treat CU-5011 as Kenji Nakamura's own household account, separate from the LLC account.
  - **Option C**: Exclude CU-5011 from reporting until the family confirms the treatment.
- **Proposed Default**: **Option C — exclude CU-5011 from reporting until the household treatment is confirmed.**

### 4. Unmatched custodian account holder — Which existing CRM household should receive CU-5010 for Carlos Vasquez and CU-6025 for Priyanka Mehta?

- **Trigger**: Carlos Vasquez and Priyanka Mehta do not appear in the CRM context, so neither account can be matched to exactly one existing household.
- **Evidence**: Carlos Vasquez / CU-5010 (Schwab; $980,000; as of 2025-06-30); matching CRM clients and notes: []; matching meetings: []. Priyanka Mehta / CU-6025 (Schwab; $670,000; as of 2025-06-30); matching CRM clients and notes: []; matching meetings: [].
- **Candidate Options**:
  - **Option A**: Identify an existing CRM client or household for each person and link the account to it.
  - **Option B**: Confirm that either person is a new client and provide the existing household record to use after CRM onboarding.
  - **Option C**: Exclude each account from reporting until its household is confirmed.
- **Proposed Default**: **Option C — exclude each account from reporting until Carlos Vasquez or Priyanka Mehta is matched to exactly one household.**

### 5. Stale active-household valuation — Should CU-6024 be refreshed to 2025-06-30, or held out of current active AUM until that valuation is available?

- **Trigger**: CU-6024 belongs to an ACTIVE household but its valuation is dated 2024-09-30, older than the 2025-06-30 quarter-end present in the custodian feed.
- **Evidence**: Oliver Ashford / Ashford / CU-6024 (Fidelity; $1,450,000; as of 2024-09-30). Household status: Active; account number: CU-6024; most recent quarter-end present in the feed: 2025-06-30. Slack: "Market value, always, as of the most recent quarter-end."
- **Candidate Options**:
  - **Option A**: Obtain and use a 2025-06-30 market value for CU-6024.
  - **Option B**: Retain the $1,450,000 value with its 2024-09-30 date and tag it as pending refresh.
  - **Option C**: Exclude CU-6024 from current active AUM until a current valuation is available.
- **Proposed Default**: **Option C — exclude CU-6024 from current active AUM until a 2025-06-30 valuation is available.**

### 6. Meeting client not in CRM — Should Redwood Capital be added as a new prospect household, or does it correspond to an existing CRM household?

- **Trigger**: The prospecting meeting names Redwood Capital, but no existing CRM household matches it.
- **Evidence**: Redwood Capital / Intro Call — Redwood Capital. Meeting: Intro Call — Redwood Capital; Client: Redwood Capital; Notes: "Referred lead — not in the CRM yet." Matching CRM clients and notes: []; matching custodian accounts: [].
- **Candidate Options**:
  - **Option A**: Add Redwood Capital to the CRM as a prospect household and then attach the interaction.
  - **Option B**: Link the interaction to an existing household if Dana identifies Redwood Capital as an alias for one.
  - **Option C**: Exclude the interaction from reporting until Redwood Capital is matched to an existing household or formally added to the CRM.
- **Proposed Default**: **Option C — exclude the interaction from reporting until an existing household match or CRM prospect record is confirmed.**

---

Once confirmed, these decisions will be applied automatically and the Beaconcrest book will be finalized in Nevis.
