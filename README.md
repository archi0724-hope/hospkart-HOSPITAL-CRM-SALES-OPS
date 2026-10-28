# HOSPkart Hospital CRM + QuoteSaarthi + WhatsApp

## PostgreSQL and Drive workbook imports

Set the private server environment variable `DATABASE_URL` to your PostgreSQL connection URL (use TLS and a pooled URL where provided). Install `requirements.txt`, then start `python production.py`. The existing schema is initialized automatically. `/api/health` reports `database_engine: postgresql` when connected. A configured but unreachable PostgreSQL database fails visibly; it never switches to an empty SQLite database. Keep credentials out of Git and browser settings.

PostgreSQL holds shared CRM records, complaints, invoice worksheets, messages, spreadsheet connections, Drive bookmarks and saved workbook copies. Render Free can use an external PostgreSQL database without a paid disk. Files such as the optional QuoteSaarthi product catalogue still require separate provisioning; PostgreSQL does not make the server filesystem persistent. Without `DATABASE_URL`, local development continues using the existing SQLite database. Localhost and the hosted CRM share data only when intentionally configured to use the same database.

**Import Excel → Google Drive link** accepts a Sheets or Drive Excel file link and uses the existing preview, mapping and confirmation flow. Save links for other CRM users in **View saved Drive links**. A folder link is a source location: choose an individual workbook inside it for import. Use **Attach workbook copy** on a saved link to store a downloaded `.xlsx`/`.xls` privately in the shared database. **Import saved copy** reuses that snapshot without Google credentials; its saved time is displayed. Fetching the latest private Drive version still requires server Google credentials and Viewer access. Saved copies do not refresh automatically. Use the stable-ID spreadsheet connection for ongoing Leads/Queries synchronization.

To migrate an existing SQLite backup into an empty PostgreSQL destination, put `DIRECT_DATABASE_URL` (or `DATABASE_URL`) in an ignored, private dotenv file and run:

```powershell
.venv\Scripts\python.exe migrate_database.py --source-sqlite backup.db --connection-file data/.env.postgres-production
# Review counts, then repeat with --apply to copy all supported tables atomically.
```

Keep the original backup. Migration refuses an initialized/nonempty destination and verifies table counts. Exporting workspace JSON alone does not include message history or independent spreadsheet settings; use database backups for complete recovery. Maintain provider backups independently of this migration tool.

Verification: `python -m unittest discover -s tests` checks SQLite behavior and the database adapter. `CRM_TEST_DATABASE_URL` pointing at a dedicated local PostgreSQL database named `hospkart_test`, then `python tests/check_postgres.py`, checks real PostgreSQL migration, rollback, concurrent saves, sheet synchronization, XLSX export, saved workbook bytes, restart persistence and Chrome/Edge import workflows. Test databases are isolated from configured production credentials. CI runs the PostgreSQL checks with synthetic data.

## Shared uploads for all users

### Drive links in the import section

Use **Import Drive link** beside **Import Excel**, or open **Data & backups → Import from Google Drive**. Give the link a label, choose the destination section and save a Google Sheets/Drive Excel file link. Every user on this same server sees the saved links, including after reopening the browser. Repeat saves of the same file/section update the label instead of creating duplicates. **Open Drive file** and **Copy Drive link** share the source link; Google still controls access. Keep private files restricted and grant the intended viewers access rather than publishing them.

**Preview / import** reads a native Google Sheet or `.xlsx`/`.xls` file through authorized Google Drive access, then hands it to the existing Excel mapping, confirmation and checkpoint workflow. It does not save CRM records before confirmation. Importing into RGHS, Already Served, Doctors or Potential Leads replaces only that section, following the existing import confirmation. Imported data is shared with other users of this server. These are manual workbook imports; use **Connect for sync** for stable-ID, one-way Leads & Queries updates. Save-only links are not access-verified until an import/access check succeeds. Links remain after a dashboard record reset; removing a link never deletes imported records or the source file. Back up the configured database to retain link settings; workspace JSON checkpoints cover records separately.

Private workbook import uses server Application Default Credentials with `https://www.googleapis.com/auth/drive.readonly`, the enabled Google Drive API and Viewer sharing to the service account. Existing Google credentials configured only for `drive.metadata.readonly` need additional read scope for workbook downloads. There is no dashboard credential-upload field. Native Sheets export is limited by Google's [10 MB export limit](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/export); workbook imports are capped at 16 MB. Unsupported files, access failures and oversized downloads retain existing data. If server credentials are unavailable, open the private source link, download its Excel copy in Google Drive, and use **Import Excel**. Link-only sharing requires no server Google credentials.

**Copy this CRM link** copies the hosted server address for users on other networks. A localhost address is only useful on that computer, so the local dashboard explains that a hosted URL is needed. Localhost and Render remain separate databases: save/upload/import on the hosted CRM for its users to see it. A Drive bookmark does not upload a local Excel file to Drive or mirror one CRM server into another.

When DATABASE_URL is unset, the Render Free web service uses an ephemeral filesystem, so its SQLite data and saved links cannot survive redeploys, restarts or idle spin-down. For lasting hosted data, configure a paid service with a persistent disk, set `CRM_DATA_DIR` inside that disk, and migrate/restore the existing database before relying on it; alternatively set DATABASE_URL to a durable external PostgreSQL database as described above. See [Render Free storage limits](https://render.com/docs/free#local-files-lost-on-redeploy). The Drive-link feature does not change the hosting plan or incur an automatic upgrade.

Drive checks: `python -m unittest discover -s tests` and `python tests/check_drive_import.py`. They use temporary SQLite databases, synthetic workbook downloads and independent Chrome/Edge profiles to check shared links, private permissions failures, preview/confirmation, imported record visibility, reload and sync handoff. They do not publish customer workbooks or change Drive sharing.


### Shared database behavior

Upload Excel or save a CRM record once: everyone opening this same CRM server sees the saved data. All six workspaces, call history, feedback, uploaded workbook sheets, remarks and recent checkpoints use PostgreSQL when DATABASE_URL is set; otherwise they use the existing SQLite database at `CRM_DATA_DIR/hospkart_crm.db` (default `data/hospkart_crm.db`). No separate database account is required for local sharing. A new shared database starts empty; fictional demo records are not automatically published.

After updating, reload the CRM in the original browser/site address where your uploads were saved. Valid saved records automatically migrate if the shared database is still uninitialized. The previous browser copy is preserved. If shared records already exist, the banner offers **Download preserved browser data** and **Restore preserved data for all users**; restoration requires confirmation and creates a checkpoint first. Unreadable older data is retained as a raw recovery download.

Saving succeeds only after the server commits the transaction. If the network or database fails, saved data stays unchanged and unsaved changes can be downloaded. Concurrent stale edits receive a conflict message and do not overwrite the latest records. Browser storage being blocked does not prevent server saves. Other idle dashboards refresh within about five seconds; users with open editors finish or close them before receiving refreshed records.

If the server says **Use the CRM dashboard on this server to save shared records**, the request was rejected by the page-address check; this is different from an unavailable database. Use the actual server URL, rather than opening an HTML file directly. HTTPS proxies may forward to the HTTP server while preserving the same public Host and port; those requests are supported. Different hosts, ports, cross-site requests and untrusted forwarded-host headers are still rejected. If a proxy rewrites Host, configure the known proxy peer using `TRUSTED_PROXY` and `TRUSTED_PROXY_COUNT`, or preserve the public Host in the proxy. Never trust arbitrary forwarded headers from the internet. Successful browser migration retains a recovery copy without showing the warning banner; the banner remains for failed saves, unreadable records or older data needing review. Run `tests/check_proxy_migration.py` to verify real HTTPS-to-HTTP migration and error messages in Chrome/Edge with temporary certificates and data.

To use this across different networks, all users need the same hosted or protected tunnel URL pointing at this server. `localhost` on another computer points to that other computer. Hosting must use PostgreSQL or retain `CRM_DATA_DIR` on persistent storage; deploy one scheduler-owning process. A tunnel still requires this computer and server to stay running. This change connects shared storage; it does not create a public URL or add account sign-in.

Backend checks: `.venv\Scripts\python.exe -m unittest discover -s tests`. Multi-user browser checks: `.venv\Scripts\python.exe tests/check_shared_workspace.py` (or `tests/check_production_browsers.py`). They use temporary SQLite databases, synthetic uploads and independent Chrome/Edge profiles to verify migration, visibility, imports, worksheets, backups, concurrent saves, failures and restart persistence.

## Complaints in Leads & Queries

Open **Leads & Queries → Complaints → + Add Complaint**. Enter the customer/hospital, subject and details; optionally link an existing lead or customer record, choose a priority, and assign an owner. Review issues using search and the status, priority and owner filters. The summary shows total, pending, resolved/closed and high/urgent pending complaints.

Use **View / Update** to work through **Open → In Progress → Resolved → Closed**. **Resolve** opens the complaint with resolution notes required; it does not mark an issue resolved until the notes are saved. Resolved complaints retain the resolution and timestamp, and **Reopen** makes the same complaint ID active again. Complaints are saved in the shared database workspace, refresh for other idle users, survive restarts and are included in JSON checkpoints. Restoring an older checkpoint without a complaints field preserves the current complaints. Full dashboard reset clears complaints for everyone. No automatic customer messages are sent.

Verification: `python tests/check_complaints.py` uses temporary data and separate Chrome/Edge profiles to check creation, shared visibility, required resolutions, reopening, filters, safe text rendering, backup compatibility, reload and mobile controls. Backend complaint validation, reset and stale-edit protection run with `python -m unittest discover -s tests`.


## Leads and Queries: Excel export and linked Google Sheets

### Google Form responses

In **Leads & Queries → Connect Spreadsheet**, save the spreadsheet link and the full Google Forms respondent link. The dashboard shows **Open Lead / Query Form** for the team. Saving links only saves setup preferences; it does not verify Google permissions or begin importing. In Google Forms, check **Responses → Link to Sheets** and select this same spreadsheet. The CRM cannot change or verify a form's response destination from its respondent link.

Choose **Google Form responses (one worksheet)**, check access, select the response tab and load columns. The importer suggests mappings for Timestamp, Lead Generator Name, Customer Full Name, Customer Contact Number, Customer Email Address, Type of Submission, Hospital or Organization Name, Products or Services of Interest, Detailed Description of Lead or Query, Date of Lead Generation and Urgency Level. Preview the results before importing. Existing separate Leads/Queries tab connections still work.

Each response creates one lead. **New Sales Lead** and **New Lead** create only a lead. **Product Inquiry**, **Customer Query**, **Existing Customer Query**, **Query**, **Service Inquiry** and **Service Request** also create one related query. Other submission types are rejected for review. Different submissions from the same customer remain separate leads. The hospital/organization becomes the lead name when supplied; the customer's name stays in Contact Person. Empty/missing email placeholders such as “not provided” are omitted with a preview warning; malformed email addresses are rejected. Form dates use the spreadsheet's locale and time zone, and phone numbers stay text.

Map a unique immutable **Response ID** if available. Otherwise the submission timestamp acts as the source ID. Keep that timestamp unique and unchanged; duplicate timestamps are rejected and changing a timestamp creates a different identity. IDs use the source spreadsheet, response tab and immutable response key, so sorting rows or editing names/details does not create duplicates. Keep the response tab name unchanged. The CRM does not add columns or write back to the source. Deleting a response removes its source-owned lead, linked query and linked workspace copies on the next successful sync. Form sync keeps existing CRM pipeline stages and query statuses; query content changes update the last-updated timestamp.

Private form-response sync uses the same server Google credentials and Viewer sharing described below. Preview/import and automatic refresh need those credentials on the server running the dashboard, including Render separately. A connected Google account in an assistant does not supply credentials to Flask. Keep the sheet restricted and share it with the service account; never commit its key file. Google Forms may require sign-in according to the owner's settings.

Open **Leads & Queries → Export Excel**, or use **Export Excel** on the Dashboard. The download is a real `.xlsx` workbook with **Leads** and **Queries** worksheets, readable headers, frozen header rows, filters, and date cells. IDs and phone numbers are text, including leading zeros. Only documented business fields are exported; credentials and internal fields are excluded. Unknown historical dates stay blank; legacy display dates that cannot be parsed are retained as text. Timestamp cells are exported in UTC.

Choose **All Leads and Queries records** or **Currently filtered records**. All records means the independent Leads & Queries workspace, including closed stages. On that workspace, filtered export uses its lead filters and query filters separately, matching the displayed tables. On Dashboard, filtered export includes visible records from the Leads & Queries workspace and queries related to those visible leads. Other workspace records are not included in this workbook. **Existing workspace export** keeps the previous dashboard/invoice export available, and other workspace export buttons still work.

The existing CRM stores lead requirements on the lead rather than in a separate queries table. A local lead in **Query Received** therefore appears as a query with a stable `CRM-Q:<Lead ID>` ID. Once independent spreadsheet queries exist for that lead, those queries are shown instead. Historical creation/update dates are not invented.

### Configure access to private Google Sheets

1. Install the updated dependencies: `.venv\Scripts\python.exe -m pip install -r requirements.txt` (or `uv pip install --python .venv\Scripts\python.exe -r requirements.txt`).
2. In your Google Cloud project, enable the **Google Sheets API** and **Google Drive API**, and create a service account for reading CRM spreadsheets. See [Google service-account credentials](https://cloud.google.com/iam/docs/creating-managing-service-account-keys).
3. Store its JSON credentials in a private location **outside this repository**, for example `C:/private/hospkart-google-reader.json`. Restrict the file to the operating-system account running the CRM. Add this line to the private `.env`: `GOOGLE_APPLICATION_CREDENTIALS=C:/private/hospkart-google-reader.json`. Do not upload the JSON through the dashboard or commit it. On a host that supplies keyless Application Default Credentials, use those credentials and set `GOOGLE_SHEETS_USE_ADC=true` instead. See [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).
4. Share each source spreadsheet with that service account’s `client_email` as **Viewer**. Keep General access **Restricted**. No public sharing or write permission is needed. The server requests only `spreadsheets.readonly` and `drive.metadata.readonly` scopes; see the [Sheets read API](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get).
5. Restart the server. Open **Connect Spreadsheet**, paste the native Google Sheets link or its Drive file link, and click **Check link and access**. The server verifies the file type and authorized access. Excel files in Drive, shortcuts, and other formats are unsupported: open Excel in Google Sheets, choose **File → Save as Google Sheets**, and use the resulting native Sheets link.

This is a server-managed connection for this CRM installation, using its existing local/private access model. It does not add per-user Google sign-in. Connection settings, imported records and validation reports are saved in the configured database (PostgreSQL or the existing SQLite file); credentials remain in the server credential store. Keep the database and credential file private. Google API responses and spreadsheet endpoints are not cached. Google’s link is parsed into a file ID; the server never fetches arbitrary pasted URLs.

### Prepare, preview and synchronize

Use two separate tabs with unique column headers in **row 1**. Suggested headers:

- **Leads:** `Lead ID`, `Name`, `Company`, `Email`, `Phone`, `Source`, `Status`, `Assigned Owner`, `Created Date`, `Follow-up Date`. The mapper also supports the existing CRM contact, location, requirement, product, quotation/order values, last-contact date, priority and remark fields.
- **Queries:** `Query ID`, `Related Lead ID`, `Subject`, `Query Details`, `Status`, `Assigned Owner`, `Created Date`, `Last Updated Date`.

Lead ID and Name are required for leads. Query ID, Related Lead ID and Subject are required for queries. IDs must be unique within their tab, case-sensitive and 1–128 letters, digits, dots, colons, hyphens or underscores. Set IDs and phone cells to **Plain text** before entering them: zeros already discarded by Google Sheets cannot be reconstructed. Dates must be `YYYY-MM-DD` or ISO timestamps; a custom `yyyy-mm-dd` sheet date format also works because the reader requests formatted values. Use existing CRM pipeline statuses for leads. Blank status defaults to **New Lead** for leads and **Open** for queries. Amounts must be non-negative numbers. Limits: 20,000 source/export records per tab, 200 source columns, 10,000 characters per cell and 12 MB per API payload/response.

Select both tabs, click **Load columns**, and map each source column to one CRM field. Automatic suggestions can be changed. Select automatic refresh **Off**, **5**, **15**, **30** or **60** minutes, then click **Preview and validate**. Review counts and sample rows before **Import valid rows and save connection**. Previewing does not change CRM data or the saved connection. Import applies that exact reviewed snapshot; previews expire after 15 minutes and are rejected if another import/sync changed the connection revision. An invalid connection or mapping leaves the previous connection in place.

**Sync Now** reads the saved source again. Stable Lead IDs and Query IDs determine inserts and updates; names and row positions are never used. Duplicate IDs reject every occurrence. Missing IDs, invalid values and queries with missing/rejected leads are listed for review. Valid rows can still import; rejected existing rows retain their previous values. A source row disappearing removes its source-owned lead/query and linked workspace copies on the next successful sync, updating dashboard counts. A valid header-only worksheet removes all of that source's imported rows. Failed reads or validation errors postpone removals; manual records and records from other sources remain. Unmapped CRM fields are retained; blank mapped cells clear their values. Switching source sheets uses the same ID space, so review matching IDs carefully. Removal ownership is tracked for the active connection.

Linked records are persisted in the configured database and merged into the shared lead workspace inside the same server transaction. Existing records and features remain available; a matching shared Lead ID receives the linked fields. The source sheet controls those fields: local edits may be replaced by the next sync or reload. Independent synced queries are read from the configured database. There is no write-back. Counts, tables, stage board, query status breakdown and filter options refresh after importing. The connected name, **Open Linked Sheet**, last successful sync time in IST, counts of added/updated/unchanged/rejected records and failures remain visible.

Sync report counts describe imported records; a new imported record matching a shared Lead ID updates that record rather than increasing its headcount. Rejected rows show tab, row, ID and reason; **Download all validation issues** includes the complete issue list. Existing JSON checkpoints cover shared workspace data. Back up the configured database as well to retain independent queries, connection settings and sync reports.

Automatic sync requires the server to remain running with `SCHEDULER_ENABLED=true` and **one scheduler-owning process**, as required by the existing messaging scheduler. It checks due work every minute, so a run may start up to a minute after the chosen interval. A sleeping host cannot refresh while asleep; manual sync still works when available. Open dashboards poll shared workspace changes every five seconds while visible and idle; spreadsheet status and independent queries refresh every 30 seconds. Failed network calls, permissions, headers or database writes preserve the last successfully saved data and sync timestamp. Correct the sheet/configuration, then retry. **Clear all dashboard data** also clears synced records and disables automatic sync; it retains connection settings for deliberate reconnection or manual sync.

### Verification

Run `.venv\Scripts\python.exe -m unittest discover -s tests` for backend regression coverage, including stable IDs, duplicates, relationships, preview isolation/expiry, rollback, persistence, automatic scheduling and real XLSX types. With `requirements-dev.txt` installed and Chrome/Edge available, run `.venv\Scripts\python.exe tests/check_spreadsheet_sync.py` for the actual connect → map → preview → import → sync → export workflow. These checks use temporary databases, fresh browser profiles and synthetic Google responses; they never modify a real spreadsheet or reset live CRM records. Live Google authorization, API quotas, organization sharing policies and a real hosted automatic refresh must be verified with your configured account and source sheet.

For a complete illustrated walkthrough, see [README-2.md](README-2.md). Use [PPT_GENERATION_PROMPT.md](PPT_GENERATION_PROMPT.md) with the 23 synthetic screenshots in `docs/screenshots/` to create a project presentation.

## QuoteSaarthi setup and team practice

QuoteSaarthi replaces the floating HOSPkart SmartBot. Product search, vendor comparison and single-product draft quotations use the handover CSV catalogue locally, without an OpenAI key. CRM summaries and reviewed WhatsApp follow-up drafts read saved CRM data locally without an AI key. This integration uses the handover agent and keyword catalogue search; it does not fine-tune a model or install the archive's virtual environment/vector database.

Install the project requirements, then prepare your private catalogue from the supplied ZIP or a CSV:

```powershell
.venv\Scripts\python.exe prepare_quotesaarthi_catalog.py "C:\Users\Archi\Downloads\HospKart-BD-Chatbot-IT-Handover.zip"
```

Restart the server after preparing or updating the catalogue. CSV inputs require `product_name`, `vendor_name` and `price` columns. The default file is `data/quotesaarthi/products.csv` under `CRM_DATA_DIR`; an administrator can override it with `QUOTESAARTHI_CATALOG_PATH`. Catalogue data, conversation logs and generated documents are excluded from Git. Production hosts need their own private catalogue and a persistent writable `CRM_DATA_DIR`; cloning the public repository alone does not supply products. Missing catalogue configuration leaves the CRM dashboard available and gives a setup message in chat.

Keep `QUOTESAARTHI_USE_OLLAMA=false` for the default local search/template responses. Optional Ollama formatting requires the `ollama` Python package, a running Ollama service and the configured model; the app does not download a model automatically.

Practise in a separate browser profile:

1. Open **QuoteSaarthi** and ask `IV Set ki vendor listing low-to-high pricing mein dikhao`.
2. Ask `Syringe 3 ml ka vendor-wise price comparison do`. Check catalogue prices, stock and vendor status before choosing.
3. Ask `Quote IV Set 50 units with 5% discount and GST 18%`, substituting the verified product and correct tax rate. Missing quantity or GST produces a clarification, not an assumed quote.
4. Select **Download JSON** or **Download PDF**. Review the product, vendor, quantity, discount, GST and final amount before sharing. These are drafts, not issued tax invoices, and do not automatically create CRM orders or quotations.
5. Use the header's **New conversation** control to clear product selection without deleting CRM data. Conversations are separate per browser tab and expire after two hours of inactivity or a server restart. Start a fresh conversation if an old session expires.
6. Use **CRM summary**, **Queries**, **Complaints**, **Follow-ups** or **Test CRM knowledge**. Saved data is read on every CRM question; new uploads need no manual training step or AI key.

One product is supported per draft. Send separate requests for multiple products. The guided invoice workflow collects customer details and confirmed GST, but its downloads remain draft quotations. No customer data or message sending is required for training.

Verification for this integration: 58 backend tests passed. Actual Chrome and Edge passed the new Waitress-based catalogue search, multi-turn GST clarification, JSON/PDF download, conversation isolation, reload, mobile layout and CRM preservation checks. Existing Chrome/Edge dashboard checks also passed, including repeated imports, migration, rollback and admin removal. Run `python tests/check_quotesaarthi.py` after installing `requirements-dev.txt`; tests use a temporary synthetic catalogue and never reset the live dashboard. CI also runs this flow with Playwright Chromium.

To remove one imported worksheet without resetting the dashboard, open **Data & backups → Manage imported Excel data**, choose **Remove** beside the specific worksheet, workbook, or imported section, enter the admin password, and type the displayed confirmation. A checkpoint is saved first. Other imports, saved client records, call history, feedback, and the original Excel file are retained. Refresh preserves the removal; an intentional checkpoint restore or re-import can bring the data back.

Configure the admin password on this computer by double-clicking `set_admin_password.bat` (or running `.venv/Scripts/python.exe set_admin_password.py` from this directory). The password must have at least 12 characters; only its hash is saved in the ignored file `data/admin_password.hash`. Changing an existing password requires the current password. Alternatively, administrators can configure `ADMIN_PASSWORD_HASH` in the private environment. Removal is disabled until a password is configured, and the server checks the password for each removal request.

Imported data and checkpoints are stored in the shared database. Admin-authorized import removal affects all users of this CRM; a shared checkpoint is saved first. The original Excel file remains available for deliberate re-import. The admin password protects the removal control; this application still requires an authenticated deployment or protected tunnel for access control.

VS Code-ready demo that combines the HOSPkart hospital/client CRM dashboard with:

- floating QuoteSaarthi icon in the bottom-right corner
- local catalogue assistant and automatic shared-database CRM knowledge
- official Meta WhatsApp Cloud API connection
- WhatsApp handoff for each hospital/client
- manual WhatsApp message sending
- approved-template scheduling for follow-ups
- inbound WhatsApp webhook logging
- optional AI auto-replies to inbound hospital messages
- Database logs for WhatsApp messages and scheduled jobs

The earlier SmartBot integration inspired the CRM summary helper. QuoteSaarthi's catalogue agent comes from the supplied IT handover and runs inside the existing dashboard; optional CRM messaging uses the OpenAI Responses API.

## 1. Open in VS Code

Open this folder:

```text
hospkart_crm_smartbot
```

## 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Command Prompt:

```bat
python -m venv .venv
.venv\Scripts\activate
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install packages

```bash
pip install -r requirements.txt
```

## 4. Create `.env`

Copy `.env.example` to `.env` and add your credentials.

Optional configuration for legacy OpenAI chat and WhatsApp automation replies (the QuoteSaarthi CRM widget uses local saved data):

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
```

Create your API key at https://platform.openai.com/api-keys and keep it in the private `.env` file. Restart the Python server after changing credentials. OpenAI API usage requires API access and billing; the app does not use your ChatGPT login.

Minimum for WhatsApp Cloud API:

```env
WHATSAPP_GRAPH_API_VERSION=v23.0
WHATSAPP_ACCESS_TOKEN=your_meta_access_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_VERIFY_TOKEN=your_private_verify_token
```

Use the Graph API version currently shown/supported by your Meta developer app; do not assume the example version will remain current forever.

## 5. Run

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

Do **not** open `templates/index.html` directly with Live Server when you want SmartBot/API/WhatsApp features; those features need the Python server.

## Manually manage the sales pipeline

Open **Leads & Queries**. Each stage has **+ Add record** to enter a hospital directly into New Lead / Contacted, Query Received, Quotation Shared, Follow-up Required, or Negotiation.

Enter the hospital and contact details, requirement, quotation value, follow-up date, and remark, then click **Save record**. Use **Edit record** on a saved card to change its details. Changing **Status** moves that record to the corresponding stage and updates the counts. **Move existing** lets you assign an existing lead to a stage. Lead records are stored separately from the Hospital & Clients master; editing a lead does not update its original client record.

CRM records, call history, feedback, independent workspace sections, imported invoice worksheets and recent checkpoints are saved transactionally in the server database. Every user of the same CRM installation sees the same saved data. IndexedDB is only a recovery/cache copy. Legacy browser records migrate automatically when the shared database is uninitialized; a browser with other legacy records cannot overwrite an initialized shared workspace. A preserved local copy is available to download and explicitly restore after review.

Chrome, Edge and different devices now share records when they connect to the same CRM server. Other open dashboards check for updates every five seconds while visible and idle; active editors and import confirmations are preserved. Stale saves are rejected instead of overwriting another user’s changes. Unsaved changes are kept as a downloadable recovery copy. JSON checkpoints restore the shared dashboard for everyone, so review the confirmation carefully.

## Reset the dashboard permanently

In **Data & backups**, acknowledge permanent deletion, type **RESET DASHBOARD**, and click **Clear all dashboard data**. Reset removes all clients, calls, feedback, imported sections, work colors, saved checkpoints, email/WhatsApp history and scheduled follow-ups. **No backup is created**, saved checkpoints become **0**, and records remain empty after refreshing. Other dashboard tabs in the same browser reload to show the cleared data. Credentials and sender configuration remain available for new work.

The Python server must be running to clear shared CRM and messaging history. Reset is one server transaction and affects every user, including shared imports, checkpoints, synced records and follow-up history. A stale reset is rejected. Previously downloaded files and messages already sent to customers cannot be recalled. The source spreadsheet and connection credentials remain available, with automatic spreadsheet sync disabled after reset.

## Dashboard layout

The Dashboard overview and combined records table show data from the separate Hospital & Clients, RGHS, Already Served, Doctors, HOSPkart Potential Leads, and Leads & Queries stores. Its **All-Workspace Record Headcount** KPI always shows the full record total across those workspaces; filtering the table changes the clearly labeled “Showing X of Y” result count, not the headcount. Each workspace page automatically recalculates its own clearly named headcounts and supporting counts after records are added, edited, imported, or filtered. Already Served distinguishes every imported invoice/service entry from the number of distinct hospitals/clients, so repeated invoice lines remain visible without being mistaken for unique clients. Use the three-line menu to open workspace navigation; follow-ups are managed in the Calling & Follow-up workspace rather than on the Dashboard. Each workspace opens as its own page; only the Dashboard intentionally combines all workspace data. Legacy RGHS matches and active leads are copied into independent stores on first load; changes remain in their own workspace.

## Excel imports

Invoice workbooks containing **Client Summary** and **Client Call List** load invoice totals, distinct clients, item details, categories, locations, payment statuses, and cancelled invoices under **Reports & Export**. The **Already Served** workspace keeps every **Client Call List** data row separately, including repeated hospital and invoice entries; its count excludes the spreadsheet header row. This keeps the main Dashboard focused on its all-workspace overview and headcount. Original columns from all worksheets remain available in **Workbook details**. The sidebar displays the supplied HOSPkart banner without clipping.

To make a local invoice workbook available through **Load provided Excel**, run `.venv/Scripts/python.exe prepare_invoice_workbook.py "C:/path/to/invoices.xlsx"` from this directory. This creates `data/imported_invoice_workbook.json`; customer data, admin password hashes, generated screenshots, and runtime logs are excluded from Git. You can also use **Import Excel** directly. The original workbook checks `tests/check_invoice_dashboard.py` and `tests/check_import_removal.py` require this locally prepared workbook and Chrome/Edge respectively. The invoice check also accepts `BROWSER_CHANNEL=msedge`. Run the source-independent unit tests with `.venv/Scripts/python.exe -m unittest discover -s tests`.

Use **Import Excel** within **Already Served**, **Doctors**, or **Potential Leads** to upload that section's list. The importer recognizes common hospital/customer name headings, including annotated headings and headings below title rows. If it cannot recognize the name column, select the worksheet, header row, and hospital/customer name column in **Choose your Excel columns**. Check the preview, then confirm the import. Original spreadsheet columns are retained.

## Hospital work colors

Hospital names, list rows and follow-up cards show their work status: **red** for untouched records, **green** for completed outreach, **yellow** for calls that did not connect, and **blue** for queries, follow-ups, or orders. Completed-green client, lead, and RGHS records are copied into the separate HOSPkart Potential Leads workspace; the source record remains in its original workspace, and each source is copied only once. Recorded query, quotation, follow-up, and order stages take priority over ordinary outreach in Automatic mode. Preparing a draft, queuing an email or opening WhatsApp does not count as completed outreach; email must be accepted by the sender before it turns a record green.

The **Not Interested** pipeline status is available when updating a record and is shown with an orange badge; it does not change the record's separate work color. A hospital/client name is shown in neon text only when it appears more than once across the workspace data, including linked Potential Leads copies; names that appear only once are not highlighted. Rows and cards are not highlighted.

The Orders workspace tracks quotations, finalized orders, demand fulfilled, and served/completed records. **Demand Fulfilled** and **Order Finalized** are available as lead statuses; the Dashboard continues to include these stages in its overall order totals.

Use the color dropdown beside a hospital to set a manual color, or select **Automatic** to use saved activity again. A manual color stays in place after subsequent activity. **Remarks / color** opens the work-status editor; blue requires a remark describing the query, follow-up, or order. These controls are also available in Already Served, Doctors, and Potential Leads, where each imported section retains its own work status. The client form includes **Hospital work color** as well.

Colors and remarks are saved in the shared database and included in JSON checkpoints. Main client Excel exports include the resolved work color, work status label and manual/automatic mode. Email activity is synchronized while the dashboard is open. Keep a database backup and download a checkpoint before a major import or restore.

## Email follow-ups

Open **Email Follow-ups** to send to all customers in **Hospitals & Clients**, only customers whose follow-up date is due, or one selected customer. Add customer email addresses through **View / Edit** first. Missing/invalid email addresses are skipped; duplicate addresses receive one email per batch. Other independently imported sections are not included in the client master.

Review the recipient list and first personalized message, then use **Send now** or choose a future date/time (India time) and **Schedule follow-ups**. Supported placeholders are `{{name}}`, `{{contact}}`, `{{product}}`, and `{{requirement}}`. Each recipient gets a separate email; other customers' addresses are never included.

Use **Email follow-up** beside customers on the dashboard, client master, lead cards, quotations, orders, feedback, calling queue and call history. These shortcuts open a draft for that customer with a message suited to their follow-up stage. A future CRM follow-up date is suggested at 10:00 India time; overdue dates are left blank so you can send now or choose a new schedule. The call and feedback drawers also offer email shortcuts. **Email due follow-ups** on the calling page prepares a batch for customers due today or overdue. All drafts require review before sending.

Configure these values in your private `.env` file using your email provider's SMTP settings, then restart Python:

```env
SMTP_HOST=your-provider-smtp-host
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=your-sender-account
SMTP_PASSWORD=your-provider-smtp-credential
EMAIL_FROM=your-sender@example.com
EMAIL_FROM_NAME=HOSPkart
EMAIL_AUTOMATION_ENABLED=true
```

For implicit TLS use `SMTP_SECURITY=ssl` and your provider's SSL port (usually 465). Keep credentials in `.env`, never in dashboard fields. Sending uses Python's [SMTP client](https://docs.python.org/3/library/smtplib.html) with verified TLS.

The queue is saved in the configured database. **Send now** jobs are picked up every 15 seconds (up to 50 per pass); scheduled jobs require `EMAIL_AUTOMATION_ENABLED=true`. Leave the local server running for either kind of sending. History shows pending, sending, accepted, failed and cancelled jobs. Accepted means SMTP accepted the message, not confirmed delivery. Cancel pending jobs from history. Failed jobs are not automatically retried; check your sender outbox before creating a replacement. If the server stops during sending, that job stays in `sending` to avoid automatic duplicate delivery. This local version does not track email opens, bounces or replies.

## 6. WhatsApp Cloud API setup

You need a Meta business portfolio, a WhatsApp Business Account and a WhatsApp-enabled business phone number. Configure your Meta app for WhatsApp Cloud API, then set the webhook callback to:

```text
https://YOUR-PUBLIC-DOMAIN/webhook
```

For local testing, expose port 5000 using a secure HTTPS tunnel such as Cloudflare Tunnel or ngrok, then use the resulting HTTPS URL as the webhook callback.

Webhook verify token must match `WHATSAPP_VERIFY_TOKEN` in `.env`.

## 7. Follow-up automation

Automated scheduled messages use an approved Meta message template. In `.env`:

```env
WHATSAPP_AUTOMATION_ENABLED=true
```

Then open **WhatsApp Automation** inside the CRM, select a hospital, enter its real WhatsApp number, approved template name, schedule date/time, and confirm that the client has agreed to receive WhatsApp business messages.

The scheduler checks pending jobs once per minute.

## 8. AI inbound auto-reply

Keep this disabled during testing:

```env
WHATSAPP_AUTO_REPLY_ENABLED=false
```

After you are satisfied with the response quality, you can set it to `true`. The bot is instructed not to invent prices, order confirmations, technical specifications or medical information.

## 9. Important WhatsApp operating rule

Free-form messages are suitable when the customer-service conversation window is open after a customer message. Business-initiated/out-of-window follow-ups should use approved Meta templates. The scheduler in this demo intentionally uses templates.

## 10. Production suggestions

Start this Flask application with a Python host, using `pip install -r requirements.txt` followed by `python production.py`. The Windows and Linux launch scripts use Waitress, a WSGI server, and work in Chrome and Edge through the server URL. Open `http://127.0.0.1:5000/` locally. `dashboard_demo.html` now opens the same served application rather than a stale standalone copy. GitHub Pages and other static-only hosts cannot run the Python APIs. Keep debug mode disabled.

Set `CRM_DATA_DIR` to an absolute persistent directory when deploying so SQLite, the local admin hash, and a prepared private workbook survive application releases. Configure `ADMIN_PASSWORD_HASH` or run `set_admin_password.py` on the host before using admin removal. Customer workbook contents are deliberately excluded from this public repository: import the Excel file after deployment, prepare it on the host, or restore a JSON checkpoint. Browser data does not automatically synchronize between users or devices.

Run exactly one server process while `SCHEDULER_ENABLED=true`. For multiple web processes, set `SCHEDULER_ENABLED=false` on them and arrange one scheduler owner before enabling automated follow-ups. Deploy behind the host's HTTPS termination and configure its trusted proxy behavior; the admin action checks request origin. This change does not introduce full user accounts or shared server-side client storage.

For an HTTPS reverse proxy, set `TRUSTED_PROXY` to the proxy's actual peer IP and `TRUSTED_PROXY_COUNT` to its hop count. The proxy must supply `X-Forwarded-Proto`, `X-Forwarded-Host`, and (when needed) `X-Forwarded-Port`. Waitress trusts those headers only from the configured proxy, so HTTPS admin-origin checks can work without trusting arbitrary forwarded headers.

Verification: install `requirements-dev.txt`, then run `python -m unittest discover -s tests` and `python tests/check_production_browsers.py`. The browser check uses actual installed Chrome and Edge against Waitress, temporary synthetic data, repeated large imports, corrupt/blocked storage, save rollback, JSON transfer, mobile navigation, and password-checked removal. CI uses Playwright Chromium with synthetic data; private customer files are unnecessary.

Before using this as your live HOSPkart CRM:

1. Add application sign-in and per-user permissions before exposing the shared CRM publicly.
2. Add user login and role permissions for calling executives vs managers.
3. Encrypt or restrict access to contact information and API credentials.
4. Keep an explicit WhatsApp opt-in field and opt-out status for every hospital/contact.
5. Add audit logs for status changes, quotation updates and message sends.
6. Connect quotation/order data to your real source rather than allowing the AI to infer it.
7. Use an external job worker/scheduler for production scale rather than an in-process scheduler.

## Team training (35 minutes)

Use a separate CRM server and temporary database with fictional records for practice. A separate browser profile connected to the same server shares the live data and is not an isolated training environment. Start with the Windows launch script or `python production.py`; open the server URL instead of the HTML file.

| Time | Exercise | What the trainee should check |
| --- | --- | --- |
| 5 minutes | Open navigation and visit Dashboard, Hospitals & Clients, RGHS, Already Served, Doctors, Potential Leads, and Leads & Queries. | Each workspace has its own records. Dashboard combines them; linked copies count separately. |
| 7 minutes | Import a practice Excel file into its intended workspace. If prompted, select the worksheet, header row and name column. | Preview names and columns before confirming. Refresh and confirm that the saved rows remain. |
| 7 minutes | Add or edit a practice lead, save a calling note, add a next follow-up date, and change work color with a remark. | The record appears in the correct stage. Call history survives refresh. A blue record has a useful remark. |
| 5 minutes | Open Reports & Export and compare invoice analysis with the Already Served page. | Served entries and distinct hospitals are different counts; invoice totals are counted once per invoice. |
| 5 minutes | Download a JSON checkpoint; restore it in another practice browser/profile. | Counts, remarks, worksheets and call history match. Excel export is useful for reporting; JSON is the full restore file. |
| 6 minutes | Ask SmartBot for a summary and a selected-hospital follow-up draft. | Check the counts against the UI and review the draft before sending it yourself. |

**Daily routine:** open Calling & Follow-up, review overdue and due-today records, record the outcome and next action, update the appropriate workspace, then download a JSON checkpoint at the end of the working day. Edits to independent lead/RGHS/Potential Leads copies do not automatically edit the Hospital & Clients master.

**Work colors:** red means untouched, yellow means a call did not connect, green means completed outreach, and blue means a query/follow-up/order. Green source records can create a linked Potential Leads copy. Orange labels Not Interested. Neon names identify duplicates across the workspace records; they do not prove duplicate invoices or incorrect data.

**Admin practice:** in a separate practice profile, open Data & backups → Manage imported Excel data, choose one worksheet or section, enter the configured admin password and the displayed `REMOVE …` phrase. Verify that other worksheets, records, calls and feedback remain. Restore the safety checkpoint to practise recovery. The dashboard reset clears all browser records/checkpoints and server messaging history; do not use it to remove one Excel sheet or as a training cleanup step on the live server.

**Understanding the supplied invoice workbook:** the verified workbook has 38 distinct hospitals/clients, 61 non-cancelled invoices, 202 non-cancelled served item entries and ₹31,35,013.91 in invoice value. The cancelled sheet has 152 item rows representing 6 invoices. The Already Served entry headcount is 202; 38 is its distinct-client count. Counts describe this workbook, not every future upload. The overall workspace headcount can exceed both because it includes records and linked copies from all workspaces.

## Automatic QuoteSaarthi CRM knowledge and testing

QuoteSaarthi reads the latest saved database workspace and independent queries in a consistent read transaction on each CRM question. It never relies on browser-provided totals, names or remarks. The browser sends only the selected record ID/workspace and current view. A new upload, spreadsheet sync or saved edit is immediately available to the next question; no vector index or model retraining is needed. Saved Google Sheet links alone do not import rows. Unsaved edits and unavailable sources are not guessed.

The widget supports all-workspace summaries, per-workspace counts/statuses, queries, pending or resolved complaints, overdue/today follow-up queues, hospital/name/ID lookup, deduplicated invoice totals, connection guidance and reviewed message drafts. Answers show their saved revision and explain that browser filters are not applied. The server date is evaluated in Asia/Kolkata on every request. Workspace copies and repeated service entries count separately; distinct name/city combinations are a separate measure. Query fallback matches the existing dashboard when a lead is marked Query Received and has no independent query. Follow-up queues include closed-stage records with saved dates, matching the dashboard. Lists show at most 12 records with full queue counts.

**Test CRM knowledge** runs read-only data checks for missing/duplicate record IDs within workspaces, invalid follow-up dates, missing query/lead relationships and invalid invoice totals. Checks run on every CRM question and when the widget opens; the status displays the latest checked revision. These are data checks, not a guarantee of every possible answer's correctness. Failed database reads produce an error instead of stale or invented answers. Chat cannot modify CRM records, resolve complaints, send messages or delete imports. CRM questions use local deterministic replies and do not send CRM records to an external model for training or inference. Catalogue pricing and quote generation keep their existing separate workflow.

Automated tests run on GitHub pushes/PRs. Run `.venv\Scripts\python.exe -m unittest discover -s tests` locally, then `python tests/check_crm_knowledge.py` and `python tests/check_quotesaarthi.py` with the development dependencies installed. The browser checks use temporary synthetic data and verify the real widget, count accuracy, new uploads becoming available without reloading, query links, complaint handling, read-only behavior, message drafts, reload/mobile layout and existing catalogue exports in Chrome/Edge. The suite uses mocked provider failures where relevant and sends no customer messages. No secret, customer data or generated model weights are committed.

| Practice prompt | Expected response to review |
| --- | --- |
| “Summarize all workspaces and overdue follow-ups.” | Workspace-specific counts, full queue totals, and a clearly limited sample of follow-ups. |
| “Why are served entries different from hospital counts?” | Multiple invoice item entries can belong to one hospital; workspace copies can also increase overall headcount. |
| “Draft a quotation follow-up for the selected hospital.” | A short draft based on its recorded requirement and status, without invented price or dispatch promises. |
| “Delete only one Excel worksheet.” | Instructions for the admin removal controls, with no claim that chat deleted anything. |
| “Confirm that my message was sent.” | No invented send confirmation; verify the application's messaging status. |

This updates live knowledge and answer rules; it does not fine-tune model weights. The CRM widget works without OpenAI configuration or billing. The separate legacy `/api/chat` endpoint still uses its optional OpenAI configuration. Review drafts and source records before acting on them; automated checks cover the documented workflows rather than every possible natural-language question.

## Verification record — 9 October 2026

43 backend tests passed. Actual Chrome and Edge checks passed against Waitress using isolated synthetic data, including 20 repeated imports per browser, full legacy storage with 1,743 clients, save rollback, failed migration recovery, emergency JSON export, cross-browser transfer, mobile navigation, admin removal, reset across tabs and SmartBot chat/context transmission. Private workbook checks also passed for invoice calculations, re-import, grouped-record migration, reload, exports and scoped removal/restoration.

The private workbook tests use temporary databases and prepared workbook copies. They do not re-seed or reset the live dashboard. To run them without creating a live server workbook, set `HOSPKART_TEST_WORKBOOK` to the private Excel path, then run `python tests/check_invoice_dashboard.py` and `python tests/check_import_removal.py`. Without that variable, the scripts copy an existing local prepared workbook into temporary test storage. Customer workbook contents remain excluded from Git. No customer email or WhatsApp message was sent during these checks; the live OpenAI provider was not called.

The sidebar uses the requested yellow rounded banner with an orange/navy `HOSPkart.com` wordmark. It renders directly in the page and retains the `HOSPITAL CRM & SALES OPS` subtitle. The earlier pastel artwork remains available as `static/hospkart-logo-pastel.png`.

## Attribution

SmartBot concept adapted from:

`https://github.com/archi0724/smartbot`

Review and retain any license/attribution requirements from upstream dependencies when deploying.


### Dashboard access and activity history

The shared dashboard allows uploads, edits, spreadsheet configuration/sync, restores and deletion without a username or password. `/admin` redirects to the dashboard. Open **Data & backups → Activity log** or `/activity` to view recorded changes.

Changes are attributed to **Dashboard user**. Without individual sign-in, the history cannot identify a person. It records the time in IST, affected API/area, tables, record IDs (up to 50), changed field names and added/edited/removed counts. Customer field values and workbook content are not copied into history. Database changes and their audit event commit in the same transaction; audit failure rolls the change back. History survives dashboard reset and has no edit/delete endpoint.

Exact deletion/reset confirmations, same-origin write checks and stale-save protection remain enabled. Automatic synchronization is attributed to `System: auto_sync`. Inbound WhatsApp writes still require `WHATSAPP_APP_SECRET` and a valid Meta signature. Google access configuration and sheet sharing are separate from dashboard access.

The default is `ADMIN_ACCESS_REQUIRED=false`. The server owner can explicitly restore the legacy account gate with `ADMIN_ACCESS_REQUIRED=true`; existing named-account tools and authenticated-mode tests are retained.

Verification: `python -m unittest discover -s tests`, `python tests/check_dashboard_access.py`, and `python tests/check_admin_access.py`. Checks use isolated temporary databases and synthetic records.


### Connected spreadsheet display and counts

Once connected, Leads & Queries shows the saved connection status, form link and records. Spreadsheet setup lives in an **Manage spreadsheet** dialog. Sync details are collapsed by default. The lead/query navigation badge uses the lead workspace headcount; the query summary uses saved query records, including linked form queries after their lead moves to another pipeline stage. Imported form responses contribute one lead each to dashboard headcount; their linked query is displayed separately and does not add a second lead. Repeated sync keeps stable record IDs and does not inflate totals.

Verification: `python tests/check_connected_sheet_dashboard.py` checks connected display, spreadsheet management, saved query counts, headcount updates and repeat sync in Chrome/Edge with synthetic records.

### Database startup recovery

If configured PostgreSQL is unavailable during startup, the web process keeps the dashboard layout and navigation available while returning HTTP 503 for data APIs. A saved browser copy is labeled as potentially out of date; without a copy, unavailable counts display a dash. Editing stays disabled, and the page checks for recovery once per minute. Static assets remain available. Database initialization is retried at most once per minute, and background jobs wait until it succeeds. Existing records stay in the configured database; no SQLite fallback is created. This lets a TCP-health-checked Render service start during an outage, but data remains unavailable until the database/account limit is restored. `/api/health` continues to return 503 while initialization is pending.
