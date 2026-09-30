# KMJ Public Experience — Locked Direction

**Status:** OWNER LOCKED  
**Scope:** KMJ Main Platform landing page, public product pages, product artwork, demos, SEO/AEO presentation and future public-facing additions.

This file is an authoritative product/design constraint. Future chats, developers, agents and automation must preserve it unless the owner explicitly changes the lock.

## 1. Experience objective

The public experience must feel premium, cinematic, modern, cooperative, professional and trustworthy. The first impression should be visually magnetic and memorable without becoming noisy, gimmicky, gaming-like or difficult to use.

Use strong visual hierarchy and intentional eye travel: focal imagery -> product meaning -> benefit -> proof/status -> next action.

## 2. Colour is semantic, not decoration

Do **not** make the whole site red.

- KMJ red: brand signature, primary actions and selective emphasis.
- Blue/cyan: cloud, connectivity, infrastructure and technical systems where meaningful.
- Green: verified/available/success states.
- Amber/orange: preview, early access, attention or transitional states.
- Neutral black/charcoal/white: enterprise foundation, readability and trust.
- Other colours may be used when they improve the meaning of a product, industry or scene.

Maintain visual cohesion through typography, spacing, surfaces, lighting and interaction language rather than forcing one accent colour everywhere.

## 3. Product artwork

Every public product must have its **own separate, unique product-specific artwork**. Do not use one combined collage as the product asset and do not substitute generic placeholder art.

Artwork should explain the product visually at a glance. Keep the premium cinematic quality while making products visibly distinct. In particular, KMJ 360 Dome and KMJ Cinema Player must never look like the same product.

Default artwork target: 4:3 master with intentional desktop/mobile crops. Optimize delivery for responsive loading and performance.

Do not place decorative KMJ/KMJ TECHNO logo watermarks over artwork. Product/device branding may appear only when it belongs naturally to the depicted product/interface.

## 4. Product communication

A customer should quickly understand:
1. What is this?
2. Who is it for?
3. What problem does it solve?
4. What concrete benefit does it provide?
5. What is its current lifecycle/availability?
6. Can I see or try it?
7. What is the appropriate next action?

Product copy should be persuasive, clear and commercially useful, but must remain factual. Never fabricate capabilities, customers, certifications, benchmarks, market leadership, availability or proof.

Do not publish unsupported claims such as "#1", "world's best", guaranteed results or guaranteed search rankings. The quality target may be world-class; public claims require evidence.

## 5. Interactive understanding

Where interaction materially helps understanding, provide a lightweight browser demo/simulation. Demos must be clearly labelled as simulations when they are not connected to a real backend/product environment.

Prioritize demos for products whose workflow or value is difficult to communicate with static copy alone. Demo UX must explain the workflow, not merely animate the page.

## 6. Search and AI discovery

Optimize each canonical product page for conventional search engines and AI answer/search systems through:
- unique intent-aligned titles and descriptions;
- crawlable factual product copy;
- clear headings and semantic page structure;
- Product/SoftwareApplication or other appropriate structured data where factually valid;
- FAQ content when it answers real customer questions;
- use cases and audience context;
- canonical URLs;
- strong internal linking from landing, portfolio and related products;
- descriptive image alt text and optimized media;
- consistent product names, lifecycle facts and terminology across surfaces.

Do not keyword-stuff, generate doorway pages, hide text or use deceptive SEO. Search ranking is an outcome, not a guaranteed claim.

## 7. Conversion without deception

Design the path from curiosity -> understanding -> confidence -> demo/trial/contact/purchase. Calls to action must match actual lifecycle and commercial readiness.

Purchase stays fail-closed unless governed product state allows it. Research/planned products must not be presented as currently purchasable. Early access, preview and trial labels must reflect actual platform state.

## 8. Performance and accessibility

Visual richness must not sacrifice speed, mobile usability, accessibility or stability. Use responsive media, lazy loading below the fold, appropriate eager/preload only for critical media, readable contrast, keyboard-accessible interactions and reduced-motion-friendly behavior.

Desktop and mobile are first-class experiences.

## 9. Landing-page role

The landing page should orchestrate the portfolio rather than repeat every product page. It must create a compelling first impression, surface flagship products, show the wider ecosystem, communicate industries/use cases and roadmap truth, and route users to canonical product pages.

Preserve the owner-locked hero copy and established brand identity unless explicitly changed by the owner.

## 10. Change-control rule

Before merging a public-experience change, verify:
- it follows this specification;
- product facts/lifecycle are truthful;
- artwork is product-specific;
- desktop and mobile rendering are healthy;
- no unexpected horizontal overflow or console/runtime errors;
- canonical product links work;
- relevant CI/tests pass;
- production is not deployed merely because a design change merged.

When visual preference conflicts with factual accuracy, security, accessibility, lifecycle governance or purchase controls, those safety/truth constraints win.
