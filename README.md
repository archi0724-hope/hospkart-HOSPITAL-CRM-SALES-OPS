# HOSPkart Hospital CRM + SmartBot + WhatsApp

To remove one imported worksheet without resetting the dashboard, open **Data & backups → Manage imported Excel data**, choose **Remove** beside the specific worksheet, workbook, or imported section, enter the admin password, and type the displayed confirmation. A checkpoint is saved first. Other imports, saved client records, call history, feedback, and the original Excel file are retained. Refresh preserves the removal; an intentional checkpoint restore or re-import can bring the data back.

Configure the admin password on this computer by double-clicking `set_admin_password.bat` (or running `.venv/Scripts/python.exe set_admin_password.py` from this directory). The password must have at least 12 characters; only its hash is saved in the ignored file `data/admin_password.hash`. Changing an existing password requires the current password. Alternatively, administrators can configure `ADMIN_PASSWORD_HASH` in the private environment. Removal is disabled until a password is configured, and the server checks the password for each removal request.

This local app stores imported data and checkpoints in browser IndexedDB. The password protects the dashboard's removal controls, not direct access to browser storage or operating-system files. Removal affects the current browser's imported copy. The original workbook remains available for deliberate re-import.

VS Code-ready demo that combines the HOSPkart hospital/client CRM dashboard with:

- floating SmartBot icon in the bottom-right corner
- OpenAI-powered chatbot adapted from the idea in `archi0724/smartbot`
- official Meta WhatsApp Cloud API connection
- WhatsApp handoff for each hospital/client
- manual WhatsApp message sending
- approved-template scheduling for follow-ups
- inbound WhatsApp webhook logging
- optional AI auto-replies to inbound hospital messages
- SQLite logs for WhatsApp messages and scheduled jobs

The referenced SmartBot repository inspired this assistant. This project uses the OpenAI Responses API so the assistant can be embedded directly inside the HOSPkart CRM dashboard.

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

Minimum for SmartBot:

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

CRM records are saved in the current browser's IndexedDB and remain after refresh. Hospital & Clients, RGHS, Leads & Queries, Already Served, Doctors, and HOSPkart Potential Leads each have independent record stores. On first load, legacy RGHS-tagged clients and active pipeline clients are copied into the RGHS and Leads stores; the originals remain in Hospital & Clients, and later edits do not synchronize between copies. Existing localStorage records automatically migrate on the same site address: the app copies and verifies them before removing their old copies. Unreadable records and unrelated site data are kept. Imports and their safety checkpoints save in one transaction, so a failed write preserves the previous state. IndexedDB avoids localStorage's small quota; the browser's available disk space still applies. Keep using the same address (`localhost` and `127.0.0.1` have separate browser storage). Use **Data & backups** to download a checkpoint before changing browsers or clearing browser storage. JSON downloads work even if saving a browser checkpoint fails. SmartBot and WhatsApp API features require the Python server.

Chrome, Edge, and different site addresses have separate saved data. To transfer everything, click **Prepare full data backup** in the original browser, then **Restore JSON checkpoint** in the new browser. This transfers clients, calls, feedback, imported sections, and every invoice worksheet. Storage that is blocked or unreadable is reported on the page; unreadable saved values are retained for recovery. Recent backup retention adapts to browser storage limits. Imports and checkpoint restores roll back if saving fails.

## Reset the dashboard permanently

In **Data & backups**, acknowledge permanent deletion, type **RESET DASHBOARD**, and click **Clear all dashboard data**. Reset removes all clients, calls, feedback, imported sections, work colors, saved checkpoints, email/WhatsApp history and scheduled follow-ups. **No backup is created**, saved checkpoints become **0**, and records remain empty after refreshing. Other dashboard tabs in the same browser reload to show the cleared data. Credentials and sender configuration remain available for new work.

The Python server must be running to clear messaging history. If a follow-up is currently being processed, wait for it to finish and reset again. Backend errors leave the browser records and checkpoints in place. Previously downloaded files and messages already sent to customers cannot be recalled by resetting the dashboard.

## Dashboard layout

The Dashboard overview and combined records table show data from the separate Hospital & Clients, RGHS, Already Served, Doctors, HOSPkart Potential Leads, and Leads & Queries stores. Each combined-table row identifies its workspace, and dashboard search, filters, KPIs, follow-ups, and overview export cover all stored workspaces. Each workspace opens as its own page through sidebar or mobile navigation; only the Dashboard intentionally combines all workspace data. Legacy RGHS matches and active leads are copied into independent stores on first load; changes remain in their own workspace.

## Excel imports

Invoice workbooks containing **Client Summary** and **Client Call List** load a unified dashboard with invoice totals, distinct clients, item details, categories, locations, payment statuses, and cancelled invoices. Original columns from all worksheets remain available in **Workbook details**. The sidebar displays the supplied HOSPkart banner without clipping.

To make a local invoice workbook available through **Load provided Excel**, run `.venv/Scripts/python.exe prepare_invoice_workbook.py "C:/path/to/invoices.xlsx"` from this directory. This creates `data/imported_invoice_workbook.json`; customer data, admin password hashes, generated screenshots, and runtime logs are excluded from Git. You can also use **Import Excel** directly. The original workbook checks `tests/check_invoice_dashboard.py` and `tests/check_import_removal.py` require this locally prepared workbook and Chrome/Edge respectively. The invoice check also accepts `BROWSER_CHANNEL=msedge`. Run the source-independent unit tests with `.venv/Scripts/python.exe -m unittest discover -s tests`.

Use **Import Excel** within **Already Served**, **Doctors**, or **Potential Leads** to upload that section's list. The importer recognizes common hospital/customer name headings, including annotated headings and headings below title rows. If it cannot recognize the name column, select the worksheet, header row, and hospital/customer name column in **Choose your Excel columns**. Check the preview, then confirm the import. Original spreadsheet columns are retained.

## Hospital work colors

Hospital names, list rows and follow-up cards show their work status: **red** for untouched records, **green** for completed outreach, **yellow** for calls that did not connect, and **blue** for queries, follow-ups, or orders. Completed-green client, lead, and RGHS records are copied into the separate HOSPkart Potential Leads workspace; the source record remains in its original workspace, and each source is copied only once. Recorded query, quotation, follow-up, and order stages take priority over ordinary outreach in Automatic mode. Preparing a draft, queuing an email or opening WhatsApp does not count as completed outreach; email must be accepted by the sender before it turns a record green.

The **Not Interested** pipeline status is available when updating a record and is shown with an orange badge; it does not change the record's separate work color. Duplicate hospital/client names are highlighted with a neon yellow-green row so they can be reviewed without deleting or merging records.

The Orders workspace tracks quotations, finalized orders, demand fulfilled, and served/completed records. **Demand Fulfilled** and **Order Finalized** are available as lead statuses; the Dashboard continues to include these stages in its overall order totals.

Use the color dropdown beside a hospital to set a manual color, or select **Automatic** to use saved activity again. A manual color stays in place after subsequent activity. **Remarks / color** opens the work-status editor; blue requires a remark describing the query, follow-up, or order. These controls are also available in Already Served, Doctors, and Potential Leads, where each imported section retains its own work status. The client form includes **Hospital work color** as well.

Colors and remarks are saved in the current browser and included in JSON checkpoints. Main client Excel exports include the resolved work color, work status label and manual/automatic mode. Email activity is synchronized from the backend while the dashboard is open. Keep a checkpoint before clearing browser data or changing browsers.

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

The queue is saved in SQLite. **Send now** jobs are picked up every 15 seconds (up to 50 per pass); scheduled jobs require `EMAIL_AUTOMATION_ENABLED=true`. Leave the local server running for either kind of sending. History shows pending, sending, accepted, failed and cancelled jobs. Accepted means SMTP accepted the message, not confirmed delivery. Cancel pending jobs from history. Failed jobs are not automatically retried; check your sender outbox before creating a replacement. If the server stops during sending, that job stays in `sending` to avoid automatic duplicate delivery. This local version does not track email opens, bounces or replies.

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

1. Move hospital/client master data from browser IndexedDB into the server database when shared access across users or devices is needed.
2. Add user login and role permissions for calling executives vs managers.
3. Encrypt or restrict access to contact information and API credentials.
4. Keep an explicit WhatsApp opt-in field and opt-out status for every hospital/contact.
5. Add audit logs for status changes, quotation updates and message sends.
6. Connect quotation/order data to your real source rather than allowing the AI to infer it.
7. Use an external job worker/scheduler for production scale rather than an in-process scheduler.

## Attribution

SmartBot concept adapted from:

`https://github.com/archi0724/smartbot`

Review and retain any license/attribution requirements from upstream dependencies when deploying.
