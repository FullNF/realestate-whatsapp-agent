# Real Estate WhatsApp AI Agent

A WhatsApp sales agent that runs 24/7 on **free hosting only**, replies to
customers the moment they message your WhatsApp Business number, qualifies
them (name, area, BHK, furnishing), and pushes serious leads toward a site
visit — without ever inventing a price or unit number.

**Cost: ₹0/month** for the core flow. Customers messaging you first and you
replying inside the 24-hour service window is completely free on WhatsApp
(since Nov 2024) — that's the only path this bot uses. The one thing that
costs money is *you* proactively messaging someone outside that window
(template messages) — not built yet, and when it is, it'll cost a few
paise per message, clearly called out.

## Why this stack

| Layer | Choice | Why |
|---|---|---|
| WhatsApp | **Meta Cloud API** (official) | Zero ban risk — no unofficial library |
| Hosting | **Render** free web service | 750 free hours/month = full-time coverage |
| Database | **Neon** free Postgres | Never expires (unlike Render's own free DB, which auto-deletes after 30 days) |
| LLM | **Groq** free tier (Llama 3.3 70B) | Genuinely free, no card, fast enough for real-time chat |
| Admin panel | Plain HTML page, served by the same backend | No separate hosting needed |

The agent makes **two LLM calls per incoming message**: one to extract
structured info (name/area/BHK/etc.) from the conversation, one to write
the actual reply. The *decision* of whether a lead is in-area, how many
times to try redirecting an out-of-area lead, and when to give up — all of
that happens in plain Python code, not the LLM. This is deliberate: it
means the model can never hallucinate its way into ghosting a good lead or
chasing a dead one forever.

## Setup — from absolute scratch

### 1. Meta WhatsApp Cloud API

**1a. Business Portfolio (if you don't have one)**
1. Go to [business.facebook.com](https://business.facebook.com) → top-right **Create Account**.
2. Enter business name, your name, work email → verify the email.

**1b. Developer account**
1. Go to [developers.facebook.com](https://developers.facebook.com) → **Get Started**.
2. Log in with your Facebook account. First time, you'll be asked to
   register as a developer (accept policies, verify by phone OTP).

**1c. Create the app**
1. **My Apps → Create App**.
2. Choose the app type that supports business messaging (commonly
   labeled "Business" — Meta's exact wording shifts over time, look for
   whichever option mentions WhatsApp/business messaging).
3. Enter an app name, link the Business Portfolio from 1a, confirm the
   email → **Create App**.

**1d. Add the WhatsApp product**
1. In the app dashboard, find **Add Product → WhatsApp → Set Up**.
2. Meta automatically creates a WhatsApp Business Account (WABA) and
   gives you a **free test phone number** instantly — no verification
   needed yet.

**1e. Copy your first credentials**
On the Quickstart/API Setup screen:
- **Phone number ID** (long numeric string under the test number) →
  this is `META_PHONE_NUMBER_ID`.
- **Temporary access token** → valid 24h, fine for the first test only.

**1f. Add yourself as a test recipient and send the first message**
1. Next to the "To" field, click **Manage phone number list** / "+".
2. Add your own WhatsApp number (with country code). You can add up to
   5 numbers before business verification.
3. Meta sends an OTP to that number on WhatsApp — enter the code to
   verify it.
4. Click **Send message** — Meta sends a pre-approved "hello_world"
   template to your phone.
5. **Reply to that message from your phone.** This step matters: your
   reply opens the 24-hour free-form service window — exactly the
   mechanism this whole bot relies on to stay free.

**1g. App Secret**
1. Left sidebar → **App settings → Basic**.
2. Next to **App Secret**, click **Show** (confirm your password) →
   copy → this is `META_APP_SECRET`.

**1h. Permanent access token (System User method)**
The temporary token expires in 24h — you need one that doesn't, for the
live bot.
1. business.facebook.com → **Business Settings → System Users**.
2. **Add** → name it (e.g. "whatsapp-agent-bot") → role Admin → Create.
3. **Assign assets** → select your App → "Full control". Also assign the
   WhatsApp Business Account asset → "Full control".
4. On this system user, **Generate new token** → select your App → tick
   permissions `whatsapp_business_messaging` and
   `whatsapp_business_management` → expiration "Never" → Generate.
5. **Copy the token immediately — it's shown only once.** This is
   `META_ACCESS_TOKEN`.

**1i. Pick your own verify token**
Meta doesn't generate this — you make up any random string yourself
(e.g. from a password generator). It goes in two places: your `.env`
(`META_VERIFY_TOKEN`) now, and Meta's webhook config screen later (step
5 below) — both must match exactly.

**1j. Business verification (for real customers, not just testing)**
1. Business Settings → **Business Verification** → start → upload
   documents (GST/incorporation certificate, address proof).
2. Takes 2-10 business days — start this early, it can run in parallel
   with everything else below.
3. Once verified: **WhatsApp → API Setup → Add phone number** → add your
   real business number, verify by OTP/call.
4. Update `META_PHONE_NUMBER_ID` in Render's env vars to the new number's
   ID and redeploy.

Without verification you're capped at 250 conversations/24h and 5
manually-added test recipients — perfectly fine for building and testing
everything below, not for real customers yet.

### 2. Neon Postgres (free, persistent)

1. Sign up at [neon.tech](https://neon.tech) (no card needed).
2. Create a project. Copy the connection string shown — it looks like
   `postgresql://user:pass@ep-xxx.neon.tech/dbname?sslmode=require`.
3. In `.env`, set `DATABASE_URL` to that string but with
   `postgresql+psycopg2://` instead of `postgresql://` at the start
   (SQLAlchemy needs the `+psycopg2` driver suffix).
4. You don't need to create any tables manually — the app creates them on
   first startup.

### 3. Groq (free LLM)

1. Sign up at [console.groq.com](https://console.groq.com) (no card).
2. Generate an API key under **API Keys**. Put it in `GROQ_API_KEY`.

### 4. Deploy to Render

1. Push this folder to a GitHub repo.
2. On [render.com](https://render.com), **New → Blueprint**, point it at
   your repo — it'll read `render.yaml` and set up the service.
3. Render will prompt you for the env vars marked `sync: false` in
   `render.yaml` (your real secrets) — fill them in there, not in the
   repo.
4. Once deployed, your webhook URL is:
   `https://<your-service-name>.onrender.com/webhook`

### 5. Connect the webhook in Meta

1. Back in the Meta app dashboard → **WhatsApp → Configuration**.
2. Set **Callback URL** to your Render URL from step 4.
3. Set **Verify token** to the same string you put in `META_VERIFY_TOKEN`.
4. Click **Verify and save** — this triggers the GET handshake this app
   already handles.
5. Subscribe to the **messages** webhook field.
6. Send a WhatsApp message to your test/business number from your own
   phone — you should get an AI reply within a few seconds.

### 6. Keep the free Render service warm (avoid cold-start delay)

Render's free tier sleeps after 15 minutes idle and takes 30-60s to wake
up. Since you get 750 free hours/month (a full month is ~730 hours), you
can safely keep it always-warm for free:

1. Sign up at [cron-job.org](https://cron-job.org) (free).
2. Create a job that does a GET request to
   `https://<your-service-name>.onrender.com/health` every 10 minutes.

That's it — no cold starts, still $0.

### 7. Add your inventory data

1. Open `area_inventory_template.csv`, replace the sample rows with your
   real sectors/projects/BHK types/prices.
2. Go to `https://<your-service-name>.onrender.com/admin-ui/admin.html`,
   enter your `ADMIN_API_KEY`, click Connect.
3. Under **Area inventory**, upload your CSV. This **replaces** the whole
   table — re-upload the full file whenever prices change.

### 8. Local testing (optional)

```bash
cp .env.example .env   # fill in your real values
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Meta can't reach `localhost` directly — use a tool like `ngrok` to expose
it temporarily if you want to test the real webhook locally before
deploying.

## Using the admin panel

`https://<your-service-name>.onrender.com/admin-ui/admin.html`

- **Leads** — every lead, their captured info, and current status.
- **Exception list** — type a phone number (with country code, no `+`,
  e.g. `919876543210`) and click **Pause agent** to take over a
  conversation yourself. The AI goes silent for that number until you
  click **Resume**. If `ADMIN_NOTIFY_PHONE` is set, you'll get a WhatsApp
  ping whenever a paused lead messages in, so you don't miss it.
- **Area inventory** — upload/replace your pricing sheet.

## Configuration reference

| Variable | What it controls |
|---|---|
| `SERVICE_AREAS` | Comma-separated sectors you actually serve. Matching is fuzzy (handles "Sector 70", "Sec 70", "70") |
| `OUT_OF_AREA_MAX_ATTEMPTS` | How many redirect attempts before politely closing an out-of-area lead |
| `BUSINESS_NAME`, `AGENT_NAME` | What the AI calls itself and the business |
| `DISCLOSE_AI` | Whether the AI can mention it's AI-assisted if directly asked. Some regions legally require disclosure — recommended to keep `true`, but it's your call |
| `ADMIN_NOTIFY_PHONE` | Your number, for paused-lead and hot-lead pings |

## A compliance note

Since 15 Jan 2026, Meta prohibits general-purpose open-ended chatbots on
WhatsApp — only task-specific agents (support, consultation, etc.) are
allowed. This agent is scoped tightly to real-estate consultation for your
configured service areas, which fits that requirement. Keep it that way —
don't widen the system prompt into a general chit-chat bot.

## What's not built yet

- **Automated multi-day follow-ups** (24h/48h/7d/etc. nudges) — needs a
  scheduled job; the same free cron-job.org trick can trigger it once
  added.
- **Booking/calendar integration** for site visits.
- **FAQ knowledge base** beyond the structured inventory table (e.g.
  general project amenities, possession dates) — would use pgvector on
  the same Neon DB, no new service needed.
- **Full CRM dashboard** beyond the lead list (conversion funnel,
  analytics) — would be a Vercel-hosted frontend talking to this backend.
- **Media messages** (images/voice notes from customers) — currently
  acknowledged but not processed.
