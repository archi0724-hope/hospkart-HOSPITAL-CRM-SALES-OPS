# HOSPkart Hospital CRM + SmartBot + WhatsApp

VS Code-ready demo that combines the HOSPkart hospital/client CRM dashboard with:

- floating SmartBot icon in the bottom-right corner
- Gemini chatbot adapted from the idea in `archi0724/smartbot`
- official Meta WhatsApp Cloud API connection
- WhatsApp handoff for each hospital/client
- manual WhatsApp message sending
- approved-template scheduling for follow-ups
- inbound WhatsApp webhook logging
- optional AI auto-replies to inbound hospital messages
- SQLite logs for WhatsApp messages and scheduled jobs

The referenced SmartBot repository is a small Streamlit + Gemini application. This project keeps its Gemini 2.5 Flash chatbot concept but changes the UI/backend structure so the assistant can be embedded directly inside the HOSPkart CRM dashboard.

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
GOOGLE_API_KEY=your_google_gemini_api_key
```

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
