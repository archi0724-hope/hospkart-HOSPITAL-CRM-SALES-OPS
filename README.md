# HOSPkart Hospital CRM + SmartBot + WhatsApp

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

Enter the hospital and contact details, requirement, quotation value, follow-up date, and remark, then click **Save record**. Use **Edit record** on a saved card to change its details. Changing **Status** moves that record to the corresponding stage and updates the counts. **Move existing** lets you assign an existing hospital to a stage.

CRM records are saved in the current browser's localStorage and remain after refresh. Use **Data & backups** to download a checkpoint before changing browsers or clearing browser storage. SmartBot and WhatsApp API features require the Python server.

## Hospital work colors

Hospital names, list rows and follow-up cards show their work status: **red** for untouched records, **green** for connected calls or accepted outreach, **yellow** for calls that did not connect, and **blue** for queries or orders. Recorded query/quotation/order stages take priority over ordinary outreach in Automatic mode. Preparing a draft, queuing an email or opening WhatsApp does not count as completed outreach; email must be accepted by the sender before it turns a record green.

Use the color dropdown beside a hospital to set a manual color, or select **Automatic** to use saved activity again. A manual color stays in place after subsequent activity. **Remarks / color** opens the work-status editor; blue requires a remark describing the query or order. These controls are also available in Already Served, Doctors, and Potential Leads, where each imported section retains its own work status. The client form includes **Hospital work color** as well.

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

Before using this as your live HOSPkart CRM:

1. Move hospital/client master data from browser `localStorage` into the server database.
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
