Hi Dana — I’ve consolidated the remaining exceptions into seven decisions. You can reply with the option letters and any names/values where applicable.

1. **Missing primary advisors — four households**
   - **Trigger:** Advisor is blank; Service Rep cannot be promoted, and A. Novak must be reassigned rather than retained.
   - **Evidence:** George Whitfield — active Harborline client, USD 670,000, Service Rep A. Novak; Joris Vandermeer — active client, USD 1,620,000, no Advisor; Louis Petit — active Harborline client, USD 540,000, Marcus Webb listed only as Service Rep; Maria Delgado — USD 1,240,000 balance dated 2024-12-31, Marcus Webb listed only as Service Rep, and A. Novak attended a 2025 review.
   - **Candidate options:** **A)** Assign each household to a current advisor from Priya Raman, Marcus Webb, Elena Sokolova, James Okafor, Sofia Marchetti, David Feldman, or Grace Bennett (please specify George/Joris/Louis/Maria); **B)** leave all four unassigned pending later operations review.
   - **Proposed default:** **B** for all four until you provide explicit assignments; never use A. Novak or infer from Service Rep.
   - **Question:** Which current primary advisor should own George Whitfield, Joris Vandermeer, Louis Petit, and Maria Delgado?

2. **Stale account valuations — current AUM treatment**
   - **Trigger:** Supplied market values are older than the requested latest quarter-end.
   - **Evidence:** Maria Delgado’s balance is USD 1,240,000 as of 2024-12-31; CU-5004 is likewise only valued through 2024-12-31; Thompson Joint CU-5009 has no valuation newer than 2023-09-30; Oliver Ashford CU-6024 has no valuation newer than 2024-09-30.
   - **Candidate options:** **A)** Provide/confirm 2025-06-30 market values for Maria/CU-5004 and CU-6024, and provide a current CU-5009 value; **B)** exclude stale balances from current AUM (set CU-5009 to null unless confirmed closed).
   - **Proposed default:** **B** until refreshed values or closure are confirmed.
   - **Question:** Can operations provide 2025-06-30 market values for Maria/CU-5004 and Oliver Ashford CU-6024, and either a current value or closure confirmation for Thompson CU-5009?

3. **Omar Farouk status and AUM inclusion**
   - **Trigger:** Contradictory canonical status fields.
   - **Evidence:** Omar Farouk has a USD 1,660,000 account assigned to Sofia Marchetti; CRM Status is Active while Tags contains Deceased.
   - **Candidate options:** **A)** Canonical status ACTIVE and include USD 1,660,000 in active AUM; **B)** canonical status INACTIVE and exclude it from active AUM.
   - **Proposed default:** **B**, pending confirmation, because the Deceased tag conflicts with active-client treatment.
   - **Question:** Should Omar Farouk be ACTIVE or INACTIVE, and should the USD 1,660,000 remain in active AUM?

4. **Kenji Nakamura IRA householding**
   - **Trigger:** The personal IRA has an unresolved household assignment.
   - **Evidence:** CU-5011; CRM note says Kenji is an authorized signer for Nakamura Holdings LLC and also opened a personal IRA, with an explicit instruction to determine whether the IRA belongs under the LLC household or his own; the April 2025 meeting records the same open decision.
   - **Candidate options:** **A)** Roll CU-5011 into Nakamura Household with the LLC assets; **B)** create/use a separate Kenji Nakamura personal household.
   - **Proposed default:** **A**, unless you prefer separate personal-household reporting.
   - **Question:** Should CU-5011 roll up to Nakamura Household or be reported under a separate Kenji Nakamura household?

5. **Orphan custodian accounts — identity and ownership**
   - **Trigger:** Custodian accounts have no matching CRM client or household.
   - **Evidence:** CU-5010 belongs to Carlos Vasquez, who appears only in the custodian file; CU-6025 belongs to Priyanka Mehta, who likewise appears only in the custodian file. Neither has a supplied CRM client, household, advisor, or meeting record.
   - **Candidate options:** **A)** Provide/create the matching CRM client/household and current primary advisor for each; **B)** hold both accounts out of canonical output until identity resolution.
   - **Proposed default:** **B** for both accounts.
   - **Question:** What CRM client/household and primary advisor should own CU-5010 (Carlos Vasquez) and CU-6025 (Priyanka Mehta), or should we keep them excluded pending resolution?

6. **Redwood Capital prospect interaction**
   - **Trigger:** A prospecting interaction references an entity absent from CRM.
   - **Evidence:** Meeting note says, “Referred lead — not in the CRM yet.” The attendee is James Okafor (ADV-004), and the referenced entity is Redwood Capital.
   - **Candidate options:** **A)** Create Redwood Capital as a CRM prospect/household and link the interaction; **B)** link it to an existing CRM entity if Redwood Capital is an alias, or exclude it until the entity is identified.
   - **Proposed default:** **A**, after confirming it is not an alias.
   - **Question:** Should Redwood Capital be created as a new CRM prospect/household, or does it correspond to an existing entity under another name?

7. **Household-level Risk Profile and Fee Schedule policy — four spouse conflicts**
   - **Trigger:** Spouses within the same household have conflicting Risk Profile and/or Fee Schedule values, and the meanings of Tier 1, Tier 2, and See LOE are not defined.
   - **Evidence:** Thompson: Bill (Risk=Moderate, Fee=Tier 1), Sarah (Risk=Aggressive, Fee=1.10%); Abramson: Daniel (Conservative, 0.85%), Rachel (Aggressive, 1.00%); Chen: Linda (Moderate, 0.85%), Robert (Conservative, 1.00%); Sullivan: Megan (Moderate, 0.85%), Tom (Aggressive, Tier 1).
   - **Candidate options:** **A)** Keep values at the individual client/account level and use the primary contact’s values for household-level reporting; **B)** apply one household-wide Risk Profile and Fee Schedule, using the primary contact’s values or another rule you specify. For fee labels, please define the bps/rates for Tier 1, Tier 2, and See LOE.
   - **Proposed default:** **A**, preserving each individual’s values and using the primary contact at household level; retain explicit percentage fees as supplied.
   - **Question:** Do you approve option A for all four households, and what rates do Tier 1, Tier 2, and See LOE represent?

---

## Detailed Clarification Specifications
### 1. [Missing primary advisors] Which current primary advisor should own George Whitfield, Joris Vandermeer, Louis Petit, and Maria Delgado?
- **ID**: `advisor-assignments`
- **Trigger**: Advisor is blank; Service Rep cannot be promoted, and A. Novak must be reassigned rather than retained.
- **Evidence**: George Whitfield — active Harborline client, USD 670,000, Service Rep A. Novak; Joris Vandermeer — active client, USD 1,620,000, no Advisor; Louis Petit — active Harborline client, USD 540,000, Marcus Webb listed only as Service Rep; Maria Delgado — USD 1,240,000 balance dated 2024-12-31, Marcus Webb listed only as Service Rep, and A. Novak attended a 2025 review.
- **Candidate Options**:
  - A) Assign each to a current advisor: Priya Raman, Marcus Webb, Elena Sokolova, James Okafor, Sofia Marchetti, David Feldman, or Grace Bennett; specify George/Joris/Louis/Maria.
  - B) Leave all four unassigned pending operations review.
- **Proposed Default**: B for all four until Dana provides explicit assignments; never use A. Novak or infer from Service Rep.

### 2. [Stale account valuations] Can operations provide 2025-06-30 market values for Maria/CU-5004 and Oliver Ashford CU-6024, and either a current value or closure confirmation for Thompson CU-5009?
- **ID**: `stale-valuations`
- **Trigger**: Supplied market values are older than the requested latest quarter-end.
- **Evidence**: Maria Delgado’s balance is USD 1,240,000 as of 2024-12-31; CU-5004 is likewise only valued through 2024-12-31; Thompson Joint CU-5009 has no valuation newer than 2023-09-30; Oliver Ashford CU-6024 has no valuation newer than 2024-09-30.
- **Candidate Options**:
  - A) Provide/confirm 2025-06-30 market values for Maria/CU-5004 and CU-6024, and provide a current CU-5009 value.
  - B) Exclude stale balances from current AUM; set CU-5009 to null unless confirmed closed.
- **Proposed Default**: B until refreshed values or closure are confirmed.

### 3. [Status contradiction] Should Omar Farouk be ACTIVE or INACTIVE, and should the USD 1,660,000 remain in active AUM?
- **ID**: `omar-status`
- **Trigger**: Contradictory canonical status fields.
- **Evidence**: Omar Farouk has a USD 1,660,000 account assigned to Sofia Marchetti; CRM Status is Active while Tags contains Deceased.
- **Candidate Options**:
  - A) Canonical status ACTIVE and include USD 1,660,000 in active AUM.
  - B) Canonical status INACTIVE and exclude it from active AUM.
- **Proposed Default**: B, pending confirmation, because the Deceased tag conflicts with active-client treatment.

### 4. [Household assignment] Should CU-5011 roll up to Nakamura Household or be reported under a separate Kenji Nakamura household?
- **ID**: `kenji-ira-household`
- **Trigger**: The personal IRA has an unresolved household assignment.
- **Evidence**: CU-5011; CRM note says Kenji is an authorized signer for Nakamura Holdings LLC and also opened a personal IRA, with an explicit instruction to determine whether the IRA belongs under the LLC household or his own; the April 2025 meeting records the same open decision.
- **Candidate Options**:
  - A) Roll CU-5011 into Nakamura Household with the LLC assets.
  - B) Create/use a separate Kenji Nakamura personal household.
- **Proposed Default**: A, unless Dana prefers separate personal-household reporting.

### 5. [Orphan accounts] What CRM client/household and primary advisor should own CU-5010 and CU-6025, or should we keep them excluded pending resolution?
- **ID**: `orphan-custodian-accounts`
- **Trigger**: Custodian accounts have no matching CRM client or household.
- **Evidence**: CU-5010 belongs to Carlos Vasquez, who appears only in the custodian file; CU-6025 belongs to Priyanka Mehta, who likewise appears only in the custodian file. Neither has a supplied CRM client, household, advisor, or meeting record.
- **Candidate Options**:
  - A) Provide/create the matching CRM client/household and current primary advisor for each.
  - B) Hold both accounts out of canonical output until identity resolution.
- **Proposed Default**: B for both accounts.

### 6. [Orphan interaction] Should Redwood Capital be created as a new CRM prospect/household, or does it correspond to an existing entity under another name?
- **ID**: `redwood-prospect`
- **Trigger**: A prospecting interaction references an entity absent from CRM.
- **Evidence**: Meeting note says, “Referred lead — not in the CRM yet.” The attendee is James Okafor (ADV-004), and the referenced entity is Redwood Capital.
- **Candidate Options**:
  - A) Create Redwood Capital as a CRM prospect/household and link the interaction.
  - B) Link it to an existing CRM entity if Redwood Capital is an alias, or exclude it until identified.
- **Proposed Default**: A, after confirming it is not an alias.

### 7. [Household attribute conflicts] Do you approve option A for all four households, and what rates do Tier 1, Tier 2, and See LOE represent?
- **ID**: `household-risk-fee-policy`
- **Trigger**: Spouses within the same household have conflicting Risk Profile and/or Fee Schedule values, and Tier 1, Tier 2, and See LOE are undefined.
- **Evidence**: Thompson: Bill (Risk=Moderate, Fee=Tier 1), Sarah (Risk=Aggressive, Fee=1.10%); Abramson: Daniel (Conservative, 0.85%), Rachel (Aggressive, 1.00%); Chen: Linda (Moderate, 0.85%), Robert (Conservative, 1.00%); Sullivan: Megan (Moderate, 0.85%), Tom (Aggressive, Tier 1).
- **Candidate Options**:
  - A) Keep values at the individual client/account level and use the primary contact’s values for household-level reporting.
  - B) Apply one household-wide Risk Profile and Fee Schedule, using the primary contact’s values or another rule Dana specifies.
- **Proposed Default**: A, preserving individual values and using the primary contact at household level; retain explicit percentage fees as supplied.
