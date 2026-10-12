# Complete PPT-generation prompt — HOSPkart CRM & QuoteSaarthi

Copy the prompt below into your presentation-generation tool. Upload **README-2.md**, **README.md**, and the **docs/screenshots/** folder with it. If the tool does not accept folders, upload the PNG files individually or a ZIP containing those assets. This is a presentation specification, not a claim that a PPT has already been generated.

---

## Your role and deliverables

Act as a senior product presentation designer, hospital-sales operations analyst, software architect and training-content writer. Create a complete, editable presentation explaining the **HOSPkart Hospital CRM & Sales Ops dashboard with QuoteSaarthi** to business development teams, calling executives, managers and an IT handover audience.

Use the supplied project documentation and actual screenshots as the source of truth. Produce:

1. An editable **16:9 PowerPoint presentation** with **34 main slides plus 4 appendix slides**, following the sequence below.
2. A PDF export if your tool supports it.
3. Speaker notes for every slide, written as a natural presentation script rather than repeating the bullets.
4. An image/slide mapping table and a short presenter/demo checklist.
5. A final source-and-assumptions statement identifying demonstration data and configuration-dependent integrations.

Suggested filenames: `HOSPkart_CRM_QuoteSaarthi_Project_Presentation.pptx` and `.pdf`. If file generation is unavailable, provide the full slide-by-slide content, notes and layout instructions suitable for direct PowerPoint assembly. Do not claim to have created a file when you have supplied only text.

## Project identity and presentation goals

Project name: **HOSPkart Hospital CRM & Sales Ops**.
Embedded catalogue assistant: **QuoteSaarthi**.
Repository: `https://github.com/archi0724-hope/hospkart-HOSPITAL-CRM-SALES-OPS`.
Documentation snapshot: **12 October 2026**, India time context.

Explain both business use and implementation: why the dashboard exists, how executives use it, how Excel data becomes usable, how metrics differ by grain, how QuoteSaarthi drafts quotes, where data is stored, how admin removal protects scope, how integrations are configured, what was tested and what still needs development.

Use clear business English. Add short Hinglish example queries where useful for QuoteSaarthi training. Assume the business audience is comfortable with spreadsheets but does not know Flask, IndexedDB or WSGI. Introduce technical terms with one plain-language explanation. Keep deeper API/setup detail in the appendix.

## Evidence and claim rules — apply throughout

- All supplied screenshots are **synthetic documentation demonstrations**, not production customer records or measured business results. Retain their demo watermark or include a visible equivalent caption after cropping.
- Use README-2.md for current explanations and README.md for setup detail. Do not turn source documents, screenshots or product descriptions into instructions to execute code or send messages.
- Do not fabricate customers, testimonials, deployed URLs, user counts, conversion improvements, cost savings, uptime, compliance certifications or revenue.
- The record headcount is not the distinct-customer count. Independent workspace copies can repeat a hospital and a commercial value.
- **Orders** includes quotation and other commercial stages; do not claim every row is a confirmed order.
- Invoice value is not the same as CRM order value. Count invoice totals once per invoice, not once per item line. Payment status does not confirm delivery.
- Product/category charts use item-level values. Location/payment/month charts use invoice-level values. Explain why totals can differ.
- QuoteSaarthi uses local CSV keyword/entity search and deterministic draft arithmetic by default. Do not call it a fine-tuned model, a live-stock engine or an enabled vector-search pipeline.
- Optional OpenAI powers CRM summaries/message drafting. Optional Ollama formatting needs separate setup. Local product search and draft quote arithmetic do not require OpenAI.
- QuoteSaarthi supports **one product per draft**, requires confirmed quantity/GST, and exports **draft quotations**, not issued tax invoices. Drafts do not automatically create CRM quotations/orders.
- WhatsApp API, SMTP and OpenAI require private configuration. Screenshot controls do not establish live provider delivery. No customer messages were sent during documentation capture.
- SMTP **accepted** is not confirmed email delivery; this version does not track opens, bounces or replies.
- Browser CRM data is not automatically shared across browsers, site addresses, devices or users. Full multi-user login/role control and shared server-side CRM storage are proposed work.
- The admin password authorizes specific removal actions; do not present it as a complete authentication system.
- Scoped removal saves a checkpoint and retains unrelated data. Full reset creates no backup and is a separate destructive workflow.
- The reported **58 passing backend tests** and Chrome/Edge checks are documented integration verification results. They are not an uptime guarantee or evidence of live external-provider success.
- Every numeric example must be labeled **Synthetic demo** unless its source and meaning are explicitly documented otherwise. Do not present an earlier private workbook's figures as current organizational performance.

## Design system

- Canvas: widescreen 16:9, consistent margins and page numbers.
- Palette: navy `#15284D` for titles/structure; orange `#FF7A18` for actions; white/light gray for readable content; yellow for the current logo banner.
- Preserve the current yellow **HOSPkart.com** wordmark treatment visible in `01-navigation.png`: orange HOSP, navy kart.com, rounded yellow banner. Do not replace it with the earlier pastel cart banner.
- Keep `HOSPITAL CRM & SALES OPS` as the subtitle where branding appears.
- Use Aptos, Arial or a similar readable sans-serif font. Titles approximately 28–36 pt, body 18–24 pt, captions 12–14 pt. Do not compress body text into tiny fonts.
- Prefer one clear claim and one primary visual per slide. Maximum 4–5 concise bullets in the main content. Put technical nuance and procedural detail in notes.
- Use editable shapes for architecture, workflow and metric diagrams. Keep screenshots sharp and proportional; never stretch or redraw an imaginary interface.
- Crop screenshots to the feature under discussion. Add at most 2–3 numbered callouts per screenshot with explanations in an adjacent column.
- Use screenshots for implemented functionality. Use clearly labeled conceptual diagrams for architecture and proposed improvements.
- Use icons sparingly. Do not rely on red/green alone: preserve work-status labels and legends.
- Use minimal transitions. No dramatic animations that obscure tables or distract from workflow training.
- Include a small section label: Overview / CRM / Excel & Reporting / QuoteSaarthi / Architecture / Operations / Training.

## Speaker-note requirements

For each main slide, write approximately 80–140 words of speaker notes covering: what the user is seeing, the business purpose, the implementation boundary and the transition to the next slide. Include a short “Demonstrate” cue on workflow slides. For appendix slides, use 50–100 words.

Plan for a 30–40 minute presentation plus questions; the slide deck can also serve as a longer training reference. Separate facts from optional future ideas. Notes must explain metrics carefully, without quoting screenshots as actual business outcomes.

## Slide-by-slide specification

### Slide 1 — HOSPkart Hospital CRM & Sales Ops

**Purpose:** identify the project and its scope.

**On-slide content:** project title; “CRM, Excel invoice reporting, follow-ups and QuoteSaarthi draft quotations”; documentation snapshot date; repository link in small text.

**Visual:** current yellow wordmark treatment from `01-navigation.png`; a clean crop of `02-dashboard.png` as a supporting panel.

**Notes:** introduce the business and IT audiences; state that all screenshot data is synthetic and that the deck explains the current implementation, not promised future functionality.

### Slide 2 — What this project brings together

**Content:** hospital/contact records; lead and quotation follow-up; served/invoice analysis; calling/feedback; catalogue-assisted draft quotes.

**Visual:** five connected editable blocks around the dashboard concept, with a small actual dashboard crop.

**Notes:** describe the operational need for one interface without claiming measured time savings or replacement of an ERP/accounting system.

### Slide 3 — Users and responsibilities

**Content:** BD executive, calling executive, sales manager, operations team and administrator/IT.

**Visual:** role-to-workflow table with concise actions.

**Notes:** explain intended usage roles; clearly state that these are operational responsibilities, not implemented login/role permissions.

### Slide 4 — End-to-end business workflow

**Content:** import/add records → qualify and contact → record requirements → draft/review quote → update commercial stage → follow-up/feedback/report.

**Visual:** editable process diagram; distinguish manual CRM updates from catalogue draft generation.

**Notes:** sending, order confirmation and CRM posting require deliberate actions. QuoteSaarthi does not autonomously close sales or create orders.

### Slide 5 — Navigation and the 15 working pages

**Content:** overview, six CRM stores, commercial views, communication operations, reporting/data management.

**Visual:** `01-navigation.png`; highlight menu groups and the yellow branding.

**Notes:** demonstrate opening the three-line menu, selecting a page and closing navigation. Dashboard combines stores; workspace pages remain independent.

### Slide 6 — Dashboard: one operational overview

**Content:** combined record headcount, active opportunities, quotation value, order indicators and workspace-tagged table.

**Visual:** `02-dashboard.png`, with callouts on KPI row, filters and Workspace column.

**Notes:** numbers are synthetic; use labels before interpreting values. The full record headcount remains fixed during filtering, while shown rows and supporting measures respond to scope.

### Slide 7 — Search, filters and metric grain

**Content:** search by account/contact/product; filter status/city/executive/type; records ≠ clients ≠ invoices ≠ item rows; independent copies can repeat values.

**Visual:** crop the dashboard filters and “Showing X of Y”; an editable four-grain diagram beside it.

**Notes:** explain why a hospital appearing in master and leads is two workspace records, not automatically two customers. Do not infer distinct deals from combined pipeline sums.

### Slide 8 — Work-status colors and duplicate visibility

**Content:** red untouched; green outreach completed; yellow not connected; blue query/follow-up/order; orange Not Interested; neon matching duplicates.

**Visual:** actual legend crop from `02-dashboard.png`, with the neon dot visible; a compact editable meaning table.

**Notes:** green can create a linked Potential Leads copy; manual/automatic behavior differs. Duplicate highlighting does not authorize deleting a source record. Blue requires a remark.

### Slide 9 — Hospitals & Clients: the master list

**Content:** account identity and contacts; requirement/product; status and values; follow-up ownership; View/Edit and import.

**Visual:** `03-clients.png` with 2–3 field-group callouts.

**Notes:** demonstrate selecting the correct account and checking scope before editing. This store is independent of the lead and specialist stores.

### Slide 10 — RGHS, Doctors and Potential Leads

**Content:** RGHS independent records; doctor contacts; qualified outreach targets; source copies retained and independently editable.

**Visual:** readable crops from `04-rghs.png`, `06-doctors.png` and `07-potential.png`; if needed use one large crop plus two smaller supporting crops.

**Notes:** explain specialty/workspace separation, legacy copies and green-generated potential copies. Do not present RGHS labels as external eligibility verification.

### Slide 11 — Leads & Queries: sales-stage management

**Content:** New Lead / Contacted; Query Received; Quotation Shared; Follow-up Required; Negotiation.

**Visual:** `08-leads.png` with Add record, Edit record or stage indicators highlighted.

**Notes:** show the difference between a stage change and a new client-master entry. Moving a lead changes its own store; it does not synchronize every matching hospital copy.

### Slide 12 — Quotations and order progress

**Content:** CRM values from clients/leads; negotiation visibility; commercial-stage progress; recorded order value versus invoice value.

**Visual:** side-by-side focused crops from `09-quotations.png` and `10-orders.png`.

**Notes:** QuoteSaarthi drafts are not automatically posted here. Orders includes qualifying quotation-stage records, so the table must not be described as entirely confirmed orders.

### Slide 13 — Calling & Follow-up

**Content:** next-date queue; overdue review; new call attempts; purpose/outcome/interest; next action and executive.

**Visual:** `11-calling.png` with queue and history areas identified.

**Notes:** demonstrate adding a note without overwriting previous attempts. Date-dependent counts change over time; screenshots are a snapshot of fictional dated examples.

### Slide 14 — Feedback and post-business closure

**Content:** eligible records; awaiting feedback; date/rating/customer text; internal remark; service follow-up.

**Visual:** `12-feedback.png`.

**Notes:** distinguish feedback records from distinct customers. Independent eligible copies can repeat an account; review identity before interpreting totals.

### Slide 15 — Excel import: make source files usable

**Content:** choose destination workspace; select file; map worksheet/header/name column if needed; confirm scope; inspect imported data.

**Visual:** actual Import Excel control from `03-clients.png` or `05-served.png`, plus an editable import workflow. Do not invent a mapping screenshot.

**Notes:** preserve original files; private server preparation supports Load provided Excel. Explain transactional saving and the safety checkpoint without promising unlimited disk capacity.

### Slide 16 — Already Served: entries versus clients

**Content:** preserve every item/service row; repeated hospital names are valid; separate distinct clients/invoices; exclude header row.

**Visual:** `05-served.png` and a small “4 entries → 2 clients → 3 invoices” demo diagram.

**Notes:** synthetic example only. Address the practical confusion that a unique-client count such as 38 should not be compared directly with invoice-line count. Do not label 38 as the current production total.

### Slide 17 — Invoice analysis and reliable totals

**Content:** distinct valid invoices; invoice total counted once; cancelled records separate; filters; missing contact/feedback indicators.

**Visual:** `16-invoice-analysis.png`, prominently captioned Synthetic demo.

**Notes:** explain Client Summary preference and Client Call List fallback. Demo: 3 valid invoices, 2 clients, ₹600, 4 item rows and 1 cancelled invoice. Payment status does not confirm delivery.

### Slide 18 — Charts, original worksheets and exports

**Content:** category by item value; location/payment/month by invoice value; original columns preserved; operational export presets.

**Visual:** use chart crops from `16-invoice-analysis.png`, worksheet crop from `17-workbook-details.png`, and small export-preset crop from `15-reports.png`.

**Notes:** category and invoice totals can differ because of adjustments or incomplete item values. Select a worksheet and verify original columns before using an export for management reporting.

### Slide 19 — Checkpoints and browser transfer

**Content:** full JSON backup; restore in another browser; independent browser/origin storage; retention depends on available storage; keep downloaded recovery files.

**Visual:** `18-backups.png`; editable Chrome → JSON file → Edge transfer diagram.

**Notes:** localhost and 127.0.0.1 are different storage origins. Backups transfer data intentionally; there is no automatic multi-user synchronization.

### Slide 20 — Remove one import, keep the rest

**Content:** select exact worksheet/section/workbook; admin password; displayed REMOVE confirmation; checkpoint first; unrelated data retained.

**Visual:** `19-admin-removal.png`, with selected worksheet and confirmation fields highlighted.

**Notes:** explain scope selection carefully. The screenshot is an unsubmitted dialog. The password authorizes removal controls; it does not constitute a complete access-control system.

### Slide 21 — Full reset: a separate destructive action

**Content:** explicit acknowledgment and RESET DASHBOARD; no new backup; browser records/checkpoints cleared; relevant backend history cleared; sent messages/downloads not recalled.

**Visual:** a clearly marked crop of the reset section in `18-backups.png`, if visible; otherwise use an editable warning panel based on documentation. Do not invent a completed-reset screenshot.

**Notes:** explain why reset is not a one-sheet removal or live training cleanup method. Recommend isolated practice environments and a downloaded backup before any intentional reset.

### Slide 22 — QuoteSaarthi: the embedded assistant

**Content:** replaces earlier SmartBot; local product search; vendor comparison; reviewed single-product draft quotes; optional CRM summary helper.

**Visual:** `20-quotesaarthi-search.png`; label the UI QuoteSaarthi consistently.

**Notes:** explain local catalogue retrieval separately from optional LLM wording. No model fine-tuning or private catalogue publication is implied.

### Slide 23 — Vendor search, stock and status

**Content:** catalogue prices; vendor options; stock/status visibility; active/in-stock filters; verify catalogue freshness.

**Visual:** enlarged search-response crop from `20-quotesaarthi-search.png`.

**Notes:** use example “IV Set active vendors aur in-stock options dikhao”. A lowest-price unrestricted offer is not necessarily active or in stock. Synthetic Vendor A/B/C are test data, not approved supplier endorsements.

### Slide 24 — Draft quotation: transparent arithmetic

**Content:** 10 × ₹8 = ₹80; 5% discount ₹4; taxable ₹76; user-confirmed 18% GST ₹13.68; draft total ₹89.68.

**Visual:** `21-quotesaarthi-draft.png` beside an editable calculation table.

**Notes:** specify that 18% is a synthetic test input, not product tax advice. Quantity/GST clarification and decimal rounding protect arithmetic; human review still determines commercial correctness.

### Slide 25 — Quote safeguards, downloads and sessions

**Content:** required quantity/GST; single-product support; JSON/PDF drafts; downloads scoped to conversation; new chat preserves CRM.

**Visual:** draft/download control crop from `21-quotesaarthi-draft.png`; editable session/lifecycle diagram.

**Notes:** sessions expire after two hours of inactivity or restart. A fresh quote does not silently reuse another product's quantity or GST. Documents are not issued tax invoices and do not automatically post CRM entries.

### Slide 26 — WhatsApp workflow and prerequisites

**Content:** select account/review number; prepare/review draft; manual handoff versus API sending; approved-template scheduling; private Meta setup.

**Visual:** `13-whatsapp.png` with clear “Configuration required” caption.

**Notes:** no customer messages were sent for documentation. Check actual provider requirements, recipient consent, supported API version and template configuration before live use. Do not present the UI as evidence of delivery.

### Slide 27 — Email workflow and status meaning

**Content:** recipient preview; personalization; explicit confirmation; India-time scheduling; pending/sending/accepted/failed/cancelled history.

**Visual:** `14-email.png`.

**Notes:** SMTP setup is required. Accepted means server acceptance, not inbox delivery. No opens/bounces/reply tracking exists; review failed/interrupted jobs before re-sending to avoid duplicates.

### Slide 28 — Architecture: browser, APIs and private server files

**Content:** HTML/CSS/JS; Flask/Waitress; browser IndexedDB; SQLite jobs/history; private CSV and drafts; optional external services.

**Visual:** editable version of the README-2.md architecture diagram.

**Notes:** trace browser → API → source/store → response. Emphasize that browser CRM data and server messaging storage are separate; persistent server disk is not multi-user CRM synchronization.

### Slide 29 — Data ownership, recovery and permissions

**Content:** same browser/origin for saved records; verified legacy migration; transactional import/restore; private files excluded from Git; scoped admin authorization.

**Visual:** two storage containers labeled Browser and Server, with backup/restore arrows and private-file examples.

**Notes:** no full login/RBAC or audited shared CRM currently exists. Explain what the current admin password covers and what additional production access controls would need design.

### Slide 30 — Setup and production operation

**Content:** install requirements; private .env; prepare catalogue/admin password; serve with Waitress; persistent data and HTTPS; one scheduler owner.

**Visual:** short setup checklist plus configuration groups. Keep long commands in appendix.

**Notes:** Python hosting is required, static-only GitHub Pages cannot run APIs. Keep debug disabled. Read exact environment instructions and do not expose credentials in slides.

### Slide 31 — Testing and verification evidence

**Content:** 58 documented backend test passes; actual Chrome/Edge workflows; CI Windows/Linux and Chromium; synthetic isolated checks; external deliveries excluded.

**Visual:** editable test matrix with rows for imports/storage, admin removal, mobile, QuoteSaarthi arithmetic/session/downloads and integration boundaries.

**Notes:** state the evidence accurately without fabricating a current CI screenshot. Provider credentials, live delivery and organizational uptime are separate from the demonstrated local regression checks.

### Slide 32 — Mobile usage and team training

**Content:** mobile overview/menu; correct-workspace editing; synthetic practice; metric reconciliation; quote/download review; message preview before sending.

**Visual:** `22-mobile.png` and `23-mobile-navigation.png`; concise 45-minute training agenda.

**Notes:** follow the guide's timing: 5 navigation, 8 records, 7 calls, 7 invoices, 8 QuoteSaarthi, 5 backups, 5 messaging. Use separate practice data and never reset live data for training cleanup.

### Slide 33 — Current limitations and proposed roadmap

**Content:** shared CRM database; login/role authorization; multi-product RFQ drafts; live catalogue/stock refresh; audit and delivery tracking.

**Visual:** two columns labeled “Current implementation boundaries” and “Proposed future work”.

**Notes:** no delivery dates, budgets or customer outcomes are established. Business benefits are expected hypotheses to measure in a pilot. Do not display proposed features as delivered capabilities.

### Slide 34 — Demonstration checklist and discussion

**Content:** navigate/filter; inspect workspace copy; reconcile invoice counts; generate/review draft; preview backup/removal; answer configuration questions.

**Visual:** six-step checklist, repository link and final Q&A invitation.

**Notes:** use a temporary/synthetic instance; do not click live Send or confirm Reset. Recap the practical use of the system and invite questions about workflows, deployment and data ownership.

## Appendix slides

### Appendix A — Installation and configuration reference

Show the Windows virtual-environment, pip-install, .env-copy and production.py commands from README-2.md. Group catalogue, OpenAI, Meta, SMTP, admin, scheduler and proxy settings by purpose. Use placeholder values only. Explain that private data/catalogue files are intentionally not distributed in Git.

### Appendix B — Metric dictionary and sample reconciliation

Provide a compact table for all-workspace record headcount, filtered count, quotation value, order value, served entries, distinct clients, unique invoices, item rows and cancelled invoices. Reconcile the synthetic 4/2/3/₹600 example and the ₹89.68 quote. Include the invoice-level versus item-level counting rule.

### Appendix C — API and source-code handover map

Show code components and representative endpoints: `/api/health`, `/api/import-excel`, `/api/invoice-workbook`, `/api/quotesaarthi/chat`, conversation-scoped POST downloads under `/api/quotesaarthi/download/<filename>`, `/api/email/send`, `/api/email/schedule`, WhatsApp routes and `/webhook`. Distinguish compatibility `/api/chat` from the new QuoteSaarthi widget endpoint. Use a table, not unexplained code walls. Do not expose session tokens or credentials.

### Appendix D — Troubleshooting, assets and sources

Provide browser/origin transfer, blocked storage, mapping issues, missing catalogue, quantity/GST clarification, expired conversation and unconfigured provider troubleshooting. List README-2.md, README.md, the screenshot manifest and repository as sources. State that all screenshots are synthetic and external services were disabled during capture.

## Screenshot asset map

Resolve all filenames under `docs/screenshots/`:

| File | Recommended slides |
|---|---|
| 01-navigation.png | 1, 5 |
| 02-dashboard.png | 1, 6, 7, 8 |
| 03-clients.png | 9, 15 |
| 04-rghs.png | 10 |
| 05-served.png | 15, 16 |
| 06-doctors.png | 10 |
| 07-potential.png | 10 |
| 08-leads.png | 11 |
| 09-quotations.png | 12 |
| 10-orders.png | 12 |
| 11-calling.png | 13 |
| 12-feedback.png | 14 |
| 13-whatsapp.png | 26 |
| 14-email.png | 27 |
| 15-reports.png | 18 |
| 16-invoice-analysis.png | 17, 18 |
| 17-workbook-details.png | 18 |
| 18-backups.png | 19, 21 |
| 19-admin-removal.png | 20 |
| 20-quotesaarthi-search.png | 22, 23 |
| 21-quotesaarthi-draft.png | 24, 25 |
| 22-mobile.png | 32 |
| 23-mobile-navigation.png | 32 |

If an image is missing or its relevant control is outside the crop, use a labeled conceptual diagram or note “screenshot not supplied”. Never invent an actual application screenshot. Do not crop away a meaningful error/configuration status to imply a successful provider connection.

## Final quality checklist before delivering

1. All 38 slides follow the requested sequence, include notes and use consistent branding.
2. Every main workflow has a readable screenshot or a clearly labeled conceptual diagram.
3. Current yellow logo and QuoteSaarthi name are consistent; no obsolete SmartBot branding as the active assistant.
4. Every screenshot or synthetic number has a demo caption. No real customer data, credentials or internal host paths appear unnecessarily.
5. Record/client/invoice/item grain is explicit; ₹600 synthetic invoice total and ₹89.68 draft calculation are reconciled correctly.
6. Independent copies, browser-origin storage, admin scope and reset behavior are explained without overstating protection.
7. Provider-dependent features are labeled; accepted email is not described as delivered.
8. Single-product drafts, explicit GST/quantity, local catalogue source and human review are visible.
9. No fabricated ROI, compliance, uptime, training/fine-tuning, shared multi-user functionality or future-feature delivery claims.
10. Images keep aspect ratio and text is readable at presentation size. The final deliverables are correctly described as files or text, depending on what was actually generated.

Now generate the complete presentation, notes, asset map and presenter checklist from this specification and the supplied project files.
