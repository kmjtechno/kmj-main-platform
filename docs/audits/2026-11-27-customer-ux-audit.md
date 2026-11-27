# Customer workspace UX audit (2026-11-27)

Source: three owner screenshots (Licensing Hub, Purchase Center, My KMJ Services dashboard) of a signed-in customer-side account. Findings come from those screenshots only; nothing was measured with real customers, analytics or accessibility tooling. Status: audit, not a claim of production readiness.

## Fixed in this slice
- Dashboard "Explore KMJ products" listed 14 cards, most "Not available for purchase". Now purchasable products show first; the rest fold into an "In development (N)" section.

## Findings still open (need owner decision or a separate slice)
1. **Contradictory state.** Dashboard says "0 authorized services" while Licensing Hub shows an Active KSLP license (KMJ_CLOUDOS) and "No entitlement recorded". An entitlement, a KSLP license record and a purchase are different records, but the UI does not explain the difference where the customer sees them side by side. Needs a plain-language explanation and a cross-link, and a data check on why this account has a license with no entitlement.
2. **Jargon.** KSLP, entitlement, "Ref a5032ff6", "device bindings", "online status: not verified" are shown unexplained.
3. **Licensing Hub length and repetition.** About eight sections and the same disclaimers repeated. The next action ("verify your license") is not obviously actionable.
4. **Unlaunched pricing shown to customers.** The monthly-usage card lists planned Community, Pro, Team prices labelled "Proposal · Not live". Owner should decide whether customers should see proposed prices at all.
5. **Purchase Center shows no price or plan.** Customer chooses an organization and product and requests a purchase with no price, plan, or what happens next beyond "confirmed separately by the operator". The three step chips look like buttons but are not interactive.
6. **Duplicate navigation.** "Browse products" and "Entire catalog" go to the same place; "My Services" vs "My KMJ Services" naming.
7. **Onboarding after Google sign-up.** Identity (name, verified email) comes from Google; phone, country and company are collected on the post-sign-in profile page. Not yet verified live with a real Google sign-up (the first live attempt hit a 429, fixed in PR #1265, not yet deployed).

## Not checked
Mobile and tablet layouts of these pages, keyboard and screen-reader behaviour, colour contrast, load time, and any customer's own experience.
