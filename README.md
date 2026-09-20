# Official Jobs + Advanced Client Prospecting → WhatsApp

The project now has two alert pipelines plus an approval-first local sales CRM:

- `job_alert.py` (150 lines): fresher/0–1-year official India data jobs.
- `local_alert.py`: matching digital/data openings around Kumaon/SIDCUL.
- `client_alert.py`: remote Web/AI/video client requests plus top new CRM prospects.
- `prospect_app.py` + `prospect_dashboard.html`: multi-city Google Places discovery, scoring, map, pitches and outreach tracking.

Keep all files together. Shared HTTP and WhatsApp helpers come from `job_alert.py`.

## 1. Install and dry-run

Python 3.10+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install -U 'httpx[http2]' beautifulsoup4 python-dateutil
cp .env.example .env                       # fill keys, then chmod 600 .env
set -a; source .env; set +a

DRY_RUN=1 python job_alert.py
DRY_RUN=1 python local_alert.py
DRY_RUN=1 python client_alert.py
python prospect_app.py summary
```

Dry-runs send nothing and do not modify any seen/CRM state. `prospects.json` stores only cache-exempt Google Place IDs plus your own pipeline stages, dates and notes; Google listing content stays in process memory and is requested live.

## 2. WhatsApp

### Whapi.Cloud (default)

Create and link a channel at `https://whapi.cloud`, then set:

```bash
export WHATSAPP_PROVIDER=whapi
export WHATSAPP_TOKEN='your-channel-token'
export WHATSAPP_GROUP_ID='1203...@g.us'
```

List Whapi groups with:

```bash
curl -H "Authorization: Bearer $WHATSAPP_TOKEN" https://gate.whapi.cloud/groups
```

For Wassenger, use the same variables with `WHATSAPP_PROVIDER=wassenger`; set the group WID as `WHATSAPP_GROUP_ID`.

## 3. Official job-alert settings

The job script includes Accenture Workday, IndiGo’s HTTP/2 careers API, and 32 named employer Greenhouse/Lever/Ashby boards. It accepts India onsite/hybrid and India/APAC/global-eligible remote work, requires Python plus explicit entry-level suitability, and rejects senior/2+-year, fee-based and aggregator listings. Results are ordered: Kumaon/SIDCUL first, Delhi-NCR second, remote third, then other India.

```bash
export HOURS_OLD=36
export MAX_JOBS=20
export TIMEZONE='Asia/Kolkata'
export WORKDAY_PAGES=5
export ATS_BOARDS='greenhouse|Company A|token,lever|Company B|token,ashby|Company C|token'
```

`ATS_BOARDS` appends original employer boards to the defaults. Only add a token reached from that employer’s official careers site. Accio is not queried because its supplied route requires login; never store an Accio password here.

## 4. Kumaon/SIDCUL official-careers monitor

`local_alert.py` checks the official career systems of Tata Motors, Mahindra, Reckitt, Perfetti Van Melle, Britannia, Roquette and Nestlé. It recognizes Rudrapur, Haldwani, Pantnagar, SIDCUL, Kichha, Sitarganj, Kashipur, Ramnagar, Nainital, Udham Singh Nagar and Uttarakhand aliases. Only fresh digital/data/MIS/web/AI/video skill matches survive; senior and stated 2+-year roles are rejected. If an otherwise relevant JD does not state experience, the alert honestly says **Experience unclear—check JD**.

```bash
export LOCAL_HOURS_OLD=168
export MAX_LOCAL_JOBS=10
# Optional extra official SuccessFactors search: Company|base URL|location
export LOCAL_SF_SITES='Company|https://careers.company.com|Rudrapur'
```

This separate monitor uses `seen_local_jobs.json`, so it cannot suppress or be suppressed by the national job pipeline.

## 5. Client-lead settings

Without extra API keys, `client_alert.py` checks:

- Freelancer’s public projects API for fresh, remote, minimum-budget client requests;
- original public `[HIRING]` posts from Reddit `r/forhire`;
- web, landing-page, WordPress/Shopify, AI/chatbot/automation, YouTube/reels and video-editing requirements.

It rejects common fee/deposit, commission-only, unpaid-test and unrelated-project signals. Listings are scored for fit, not presented as identity-verified clients. No message, bid or application is sent automatically.

```bash
export CLIENT_HOURS_OLD=48
export MAX_CLIENT_LEADS=12
export MIN_FIXED_USD=40
export MIN_HOURLY_USD=5
export PORTFOLIO_URL='https://your-portfolio.example'
```

Advanced search override (`Service|query`, comma-separated):

```bash
export FREELANCER_SEARCHES='Web|website,Web|landing page,Video|video editing,AI|AI automation,AI|chatbot'
```

### Advanced multi-city Google Places CRM

Enable **Places API (New)**. For the optional dashboard map, also enable **Maps JavaScript API** and use a separate browser key restricted by HTTP referrer. Never expose the server Places key in browser code.

```bash
export GOOGLE_PLACES_API_KEY='server-restricted-key'
export GOOGLE_MAPS_BROWSER_KEY='browser-referrer-restricted-key'   # optional map
export DASHBOARD_PASSWORD='choose-a-strong-password'

export PROSPECT_CITIES='Agra, Uttar Pradesh, India;Noida, Uttar Pradesh, India;Gurugram, Haryana, India;Austin, Texas, USA;Dallas, Texas, USA'
export PROSPECT_CATEGORIES='garment stores and boutiques|Retail;online stores and ecommerce brands|Retail;electronics stores|Retail;restaurants and cafes|Food;salons and spas|Beauty;dentists and clinics|Health;manufacturers and exporters|B2B'
export MAX_PLACE_QUERIES_PER_RUN=12       # rotates through city/category pairs to control cost
export PLACES_PAGE_SIZE=12
export MIN_PROSPECT_REVIEWS=15
export MIN_PROSPECT_SCORE=65
export MAX_WEBSITE_AUDITS=6
# Change to 1 only if one respectful public-homepage check per selected site is wanted:
export ENABLE_WEBSITE_AUDIT=0
```

Open the CRM, then click **Find new prospects**:

```bash
python prospect_app.py serve --host 0.0.0.0 --port 8000
```

`client_alert.py` performs its own rotating Places refresh before the daily alert. With the supplied 12-category defaults, `MAX_PLACE_QUERIES_PER_RUN=12` checks one complete city mix per day and cycles through all seven cities weekly. `python prospect_app.py refresh` is available as a command-line API/configuration check, but intentionally does not persist Google listing content.

The dashboard provides filters, opportunity scores, Google Maps links/map markers, English and Hinglish pitches, cache-safe CRM export, notes, follow-up dates, and stages from **New → Won/Lost**. Due follow-ups enter the daily client alert once, and contact details are fetched from Google only when you click **Get public contact**.

The recommended workflow is **review → shortlist → personalize → one respectful contact → track response**. The WhatsApp button opens a prepared message for your review; it does not send automatically. A public phone number is not consent for bulk promotional messaging. Fully automatic WhatsApp messages should only use an official Business account, approved templates and valid opt-in contacts.

The dashboard displays required **Google Maps** attribution and deliberately avoids warehousing Places content. Review the current Google Maps Platform terms and control API spending with field masks, query rotation and Cloud billing quotas.

## 6. Daily schedule at 8:30 AM IST

Save variables as `KEY=value` in `/path/to/app/.env`, run `chmod 600 .env`, and add:

```cron
CRON_TZ=Asia/Kolkata
30 8 * * * cd /path/to/app && /bin/bash -lc 'set -a; source .env; set +a; .venv/bin/python local_alert.py; .venv/bin/python job_alert.py; .venv/bin/python client_alert.py' >> alerts.log 2>&1
```

For faster—not real-time—discovery, `0 */3 * * *` checks every three hours, but it also increases paid Places requests; keep the client pipeline daily unless the Cloud quota/budget is configured. Deduplication prevents repeat alerts.

Review `[warn]` log lines periodically. Always verify scope, identity, payment method and the original link; never pay a recruitment, registration or security fee.
