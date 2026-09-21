#!/usr/bin/env python3
"""Daily official-careers-only WhatsApp alert for fresh India data roles."""
# Cron: 30 8 * * * cd /path/to/app && /usr/bin/python3 job_alert.py >> job_alert.log 2>&1
import hashlib, html, json, os, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path; from zoneinfo import ZoneInfo
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
if hasattr(sys.stderr, "reconfigure"):
    try: sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

# Load .env file automatically if present
def _load_env():
    p = Path(".env")
    if p.is_file():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
_load_env()

import httpx; from bs4 import BeautifulSoup; from dateutil.parser import parse
NOW, HOURS = datetime.now(timezone.utc), int(os.getenv("HOURS_OLD", "168")); CUTOFF, TZ = NOW-timedelta(hours=HOURS), ZoneInfo(os.getenv("TIMEZONE", "Asia/Kolkata"))
SEEN = Path(os.getenv("SEEN_FILE", "seen_jobs.json")); MAX_JOBS = int(os.getenv("MAX_JOBS", "25"))
# Add any employer's public board as kind|Company|token; these are original ATS feeds, not aggregators.
DEFAULT_BOARDS = (
 "greenhouse|Razorpay|razorpaysoftwareprivatelimited,greenhouse|Groww|groww,greenhouse|MongoDB|mongodb,greenhouse|Elastic|elastic,greenhouse|Datadog|datadog,greenhouse|Cloudflare|cloudflare,greenhouse|Twilio|twilio,greenhouse|Okta|okta,greenhouse|Airbnb|airbnb,greenhouse|Coursera|coursera,greenhouse|Samsara|samsara,greenhouse|Cockroach Labs|cockroachlabs,greenhouse|Rubrik|rubrik,greenhouse|Sumo Logic|sumologic,greenhouse|Coinbase|coinbase,greenhouse|Fivetran|fivetran,greenhouse|Netskope|netskope,"
 "greenhouse|Deliveroo|deliveroo,greenhouse|GitLab|gitlab,greenhouse|Remote|remotecom,greenhouse|Databricks|databricks,greenhouse|Stripe|stripe,lever|Meesho|meesho,lever|Zeta|zeta,lever|Sophos|sophos,ashby|Atlan|atlan,ashby|Tekion|tekion,ashby|Snowflake|snowflake,ashby|Confluent|confluent,ashby|Navi|navi,ashby|RevenueCat|revenuecat,ashby|Zapier|zapier")
BOARDS = DEFAULT_BOARDS + ((","+os.getenv("ATS_BOARDS")) if os.getenv("ATS_BOARDS") else "")
HTTP = httpx.Client(http2=True, follow_redirects=True, timeout=30, headers={"Accept":"application/json,text/html"})
ROLE = re.compile(
    r"\b(?:"
    r"data|analytics?|business intelligence|bi|mis|sql|excel|dashboard|power bi|tableau|"
    r"web|frontend|front[- ]end|backend|back[- ]end|full[- ]stack|fullstack|software|developer|engineer|"
    r"python|react|javascript|wordpress|shopify|framer|webflow|"
    r"ai|machine learning|artificial intelligence|prompt|chatbot|automation|n8n|"
    r"video edit(?:ing|or)?|content creator|graphic design|digital marketing"
    r")\b",
    re.I
)
ENTRY_TITLE = re.compile(r"\b(?:intern(?:ship)?|fresher|entry[- ]level|junior|associate|trainee|graduate|apprentice|(?:analyst|scientist)\s+i)\b", re.I)
ENTRY_TEXT = re.compile(r"\b(?:fresher|fresh graduate|recent graduate|new grad(?:uate)?|entry[- ]level|no (?:prior )?experience|0\s*(?:years?|yrs?)(?:\s+of)?\s+experience|0\s*(?:-|–|to)\s*12\s*months|0\s*(?:-|–|to)\s*1\s*(?:year|yr)|(?:up to|less than) (?:one|1) year|(?:minimum |at least )?(?:one|1)\+?\s*(?:year|yr)(?:s)?(?:\s+of)?\s+(?:relevant |professional |work |industry )?experience)\b", re.I)
SENIOR = re.compile(r"\b(?:senior|sr\.?|lead|principal|staff|manager|director|head|architect)\b", re.I)
OVER_ONE = re.compile(r"\b(?:minimum|min\.?|at least)\s*(?:of\s*)?(?:[2-9]|\d{2,})\+?\s*(?:years?|yrs?)|\b(?:[2-9]|\d{2,})\+\s*(?:years?|yrs?)|\b\d+\s*(?:-|–|to)\s*(?:[2-9]|\d{2,})\s*(?:years?|yrs?)|\b(?:[2-9]|\d{2,})\s*(?:years?|yrs?)(?:['’])?\s+(?:experience|in\b|with\b|working\b|of\s+(?:relevant\s+|professional\s+|work\s+|industry\s+|hands-on\s+)?experience)", re.I)
INDIA = re.compile(r"\b(?:india|pan[- ]india|bengaluru|bangalore|gurugram|gurgaon|hyderabad|pune|mumbai|chennai|noida|delhi|ncr|kolkata|ahmedabad|jaipur|kochi|cochin|trivandrum|thiruvananthapuram|lucknow|chandigarh|indore|bhubaneswar|coimbatore|mysuru|mysore|vadodara|baroda|surat|nagpur|visakhapatnam|vizag|vijayawada|mohali|thane|goa|guwahati|patna|ranchi|dehradun|rudrapur|haldwani|pantnagar|sidcul|kichha|sitarganj|kashipur|ramnagar|nainital|udham singh nagar|uttarakhand|uttaranchal|kanpur|madurai|mangalore|mangaluru|ghaziabad|faridabad|kerala|karnataka|maharashtra|tamil nadu|telangana|uttar pradesh|haryana|rajasthan|gujarat|west bengal)\b", re.I)
GLOBAL = re.compile(r"\b(?:worldwide|anywhere|global|apac|asia|work from anywhere)\b", re.I)
REMOTE = re.compile(r"\b(?:remote|work[- ]from[- ]home|wfh|work from anywhere)\b", re.I)
HYBRID = re.compile(r"\bhybrid\b", re.I)
BLOCKED = re.compile(r"(?:linkedin|indeed|glassdoor|wellfound)\.", re.I)
FEE = re.compile(r"\b(?:pay|deposit|transfer)\s+(?:a\s+)?(?:fee|money)|(?:registration|application) fee (?:required|mandatory)\b", re.I)
def api(method, url, **kwargs):
    for attempt in range(3):
        try:
            response = HTTP.request(method, url, **kwargs); response.raise_for_status(); return response.json()
        except httpx.TransportError:
            if attempt == 2: raise
def clean(value):
    raw = html.unescape(str(value or "")); return " ".join(BeautifulSoup(raw, "html.parser").get_text(" ").split())
def when(value):
    if value in (None, ""): return None
    if isinstance(value, (int, float)): return datetime.fromtimestamp(value/(1000 if value > 10**11 else 1), timezone.utc)
    text = str(value).strip(); low = text.lower()
    if match := re.search(r"/Date\((\d+)\)/", text): return datetime.fromtimestamp(int(match.group(1))/1000, timezone.utc)
    if "today" in low: return NOW
    if "yesterday" in low: return NOW-timedelta(days=1)
    if match := re.search(r"posted\s+(\d+)\+?\s+days?\s+ago", low): return NOW-timedelta(days=int(match.group(1)))
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text): return parse(text).replace(hour=23, minute=59, second=59, tzinfo=TZ).astimezone(timezone.utc)
        result = parse(text); return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError): return None
def add(out, title, company, location, url, desc, posted, source, remote=False):
    out.append({"title":clean(title),"company":clean(company),"location":clean(location),"url":str(url or ""),"desc":clean(desc),"posted":posted,"source":source,"remote":bool(remote)})
def possible(title, location, posted):
    return bool(ROLE.search(str(title)) and when(posted) and when(posted) >= CUTOFF and (INDIA.search(str(location)) or REMOTE.search(str(location)) or GLOBAL.search(str(location))))
# Official Greenhouse, Lever and Ashby employer feeds.
def ats_jobs():
    out = []
    for spec in filter(None, map(str.strip, BOARDS.split(","))):
        try:
            kind, company, board = spec.split("|", 2)
            if kind == "greenhouse":
                base = f"https://boards-api.greenhouse.io/v1/boards/{board}"
                for row in api("GET", base+"/jobs").get("jobs", []):
                    if possible(row.get("title", ""), (loc := row.get("location", {}).get("name", "")), row.get("first_published")):
                        job = api("GET", f"{base}/jobs/{row['id']}")
                        add(out, job.get("title"), job.get("company_name") or company, job.get("location", {}).get("name"), job.get("absolute_url"), job.get("content"), job.get("first_published"), "Official Greenhouse")
            elif kind == "lever":
                for job in api("GET", f"https://api.lever.co/v0/postings/{board}", params={"mode":"json"}):
                    desc = " ".join([job.get("descriptionPlain", ""), job.get("additionalPlain", "")] + [x.get("content", "") for x in job.get("lists", [])])
                    add(out, job.get("text"), company, job.get("categories", {}).get("location"), job.get("hostedUrl"), desc, job.get("createdAt"), "Official Lever")
            elif kind == "ashby":
                for job in api("GET", f"https://api.ashbyhq.com/posting-api/job-board/{board}").get("jobs", []):
                    add(out, job.get("title"), company, job.get("location"), job.get("jobUrl"), job.get("descriptionPlain") or job.get("descriptionHtml"), job.get("publishedAt"), "Official Ashby", job.get("isRemote"))
        except Exception as exc: print(f"[warn] ATS {spec}: {exc}")
    return out
# Accenture's official Workday feed, restricted to India and newest postings.
def accenture_jobs():
    out, base = [], "https://accenture.wd103.myworkdayjobs.com/wday/cxs/accenture/AccentureCareers"
    try:
        for offset in range(0, int(os.getenv("WORKDAY_PAGES", "5"))*20, 20):
            payload = {"appliedFacets":{"locationCountry":["c4f78be1a8f14da0ab49ce1162348a5e"]},"limit":20,"offset":offset,"searchText":""}
            rows = api("POST", base+"/jobs", json=payload).get("jobPostings", []); fresh = False
            for row in rows:
                posted = when(row.get("postedOn")); fresh |= bool(posted and posted >= CUTOFF)
                if posted and posted >= CUTOFF and ROLE.search(row.get("title", "")):
                    job = api("GET", base+row["externalPath"]).get("jobPostingInfo", {})
                    add(out, job.get("title"), "Accenture", job.get("location"), job.get("externalUrl"), job.get("jobDescription"), job.get("startDate") or row.get("postedOn"), "Official Workday")
            if not fresh: break
    except Exception as exc: print(f"[warn] Accenture: {exc}")
    return out
# IndiGo's official public SuccessFactors-backed careers API (the key is browser-public).
def indigo_jobs():
    out, base = [], "https://ms-careers-prod.goindigo.in"
    headers = {"user_key":os.getenv("INDIGO_USER_KEY", "03ba3c0795ce04ed48e7fe3854155a1f"),"Origin":"https://www.goindigo.in","Referer":"https://www.goindigo.in/"}
    try:
        for row in api("GET", base+"/career-job-list", headers=headers).get("result", []):
            locale, postings = (row.get("jobReqLocale", {}).get("results") or [{}])[0], (row.get("jobReqPostings", {}).get("results") or [{}])[0]
            locations = ", ".join(x.get("name", "") for x in row.get("location_obj", {}).get("results", []))
            title, job_id = locale.get("externalTitle", ""), row.get("jobReqId", ""); slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-") or "job"
            add(out, title, "IndiGo", locations, f"https://www.goindigo.in/careers/job-details/{slug}/{job_id}.html", locale.get("externalJobDescription") or locale.get("extJobDescHeader"), postings.get("postStartDate"), "Official IndiGo")
    except Exception as exc: print(f"[warn] IndiGo: {exc}")
    return out
# Internshala official internship and fresher job listings
def internshala_jobs():
    out = []
    urls = [
        "https://internshala.com/internships/data-science,web-development,python-django,video-making-editing-internship/",
        "https://internshala.com/jobs/data-science,web-development,python-django,video-making-editing-jobs/"
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    for target in urls:
        try:
            resp = HTTP.get(target, headers=headers, timeout=20)
            if resp.status_code != 200: continue
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("div.individual_internship")
            for card in cards:
                title_elem = card.select_one("a.job-title-href") or card.select_one("h2.job-internship-name a")
                if not title_elem: continue
                title = clean(title_elem.get_text())
                href = title_elem.get("href", "")
                full_url = f"https://internshala.com{href}" if href.startswith("/") else href
                
                comp_elem = card.select_one(".company-name") or card.select_one(".company_name")
                company = clean(comp_elem.get_text()) if comp_elem else "Internshala Employer"
                
                loc_elem = card.select_one(".locations")
                location = clean(loc_elem.get_text()) if loc_elem else "India"
                is_remote = "work from home" in location.lower() or "remote" in location.lower()
                
                date_elem = card.select_one(".status-success span") or card.select_one(".color-labels span")
                date_str = date_elem.get_text().strip() if date_elem else "Today"
                posted = when(date_str) or NOW
                
                desc_elem = card.select_one(".about_job .text")
                desc = clean(desc_elem.get_text()) if desc_elem else title
                
                stipend_elem = card.select_one(".stipend")
                if stipend_elem:
                    desc += " | Stipend: " + clean(stipend_elem.get_text())
                
                add(out, title, company, location, full_url, desc, posted, "Internshala", remote=is_remote)
        except Exception as exc:
            print(f"[warn] Internshala {target}: {exc}")
    return out

# Unstop official opportunities (jobs & internships)
def unstop_jobs():
    out = []
    endpoints = [
        "https://unstop.com/api/public/opportunity/search-result?opportunity=jobs&sort=recent&per_page=25",
        "https://unstop.com/api/public/opportunity/search-result?opportunity=internships&sort=recent&per_page=25",
        "https://unstop.com/api/public/opportunity/search-result?opportunity=jobs&searchTerm=data&sort=recent&per_page=15",
        "https://unstop.com/api/public/opportunity/search-result?opportunity=internships&searchTerm=data&sort=recent&per_page=15"
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
    seen_ids = set()
    for endpoint in endpoints:
        try:
            res = HTTP.get(endpoint, headers=headers, timeout=20)
            if res.status_code != 200: continue
            data = res.json().get("data", {}).get("data", [])
            for item in data:
                oid = item.get("id")
                if not oid or oid in seen_ids: continue
                seen_ids.add(oid)
                
                title = clean(item.get("title", ""))
                org = item.get("organisation", {}) or {}
                company = clean(org.get("name") or "Unstop Partner")
                job_detail = item.get("jobDetail", {}) or {}
                locs = job_detail.get("locations", [])
                location = ", ".join(locs) if locs else "India"
                is_remote = job_detail.get("type") == "work_from_home" or "remote" in location.lower()
                
                url = item.get("seo_url") or item.get("short_url") or f"https://unstop.com/jobs/{oid}"
                desc = title
                
                posted_str = item.get("approved_date") or (item.get("regnRequirements", {}) or {}).get("start_regn_dt")
                posted = when(posted_str) or NOW
                
                add(out, title, company, location, url, desc, posted, "Unstop", remote=is_remote)
        except Exception as exc:
            print(f"[warn] Unstop {endpoint}: {exc}")
    return out

def mode(job):
    location, desc = job["location"], job["desc"]
    if job["remote"] or REMOTE.search(location): return "Remote"
    if HYBRID.search(location+" "+desc): return "Hybrid"
    return "Remote" if re.search(r"\b(?:fully remote|remote (?:role|position)|work[- ]from[- ]home)\b", desc, re.I) else "Onsite"
def qualifies(job, cutoff=None):
    title, desc, posted = job["title"], job["desc"], when(job["posted"])
    blob, work = title+" "+desc, mode(job)
    eff_cutoff = CUTOFF if cutoff is None else cutoff
    if not (posted and posted >= eff_cutoff): return False
    if not job["company"] or not job["url"].startswith("http"): return False
    if FEE.search(blob) or SENIOR.search(title) or OVER_ONE.search(desc) or BLOCKED.search(job["url"]): return False
    
    if job["source"] in ("Internshala", "Unstop"):
        return bool(ROLE.search(title) or ROLE.search(desc))
        
    india_ok = bool(INDIA.search(job["location"]) or (work == "Remote" and (INDIA.search(blob) or GLOBAL.search(job["location"]+" "+desc))))
    entry = bool(ENTRY_TITLE.search(title) or ENTRY_TEXT.search(desc))
    return bool(ROLE.search(title) and entry and india_ok)
def identity(job):
    key = re.sub(r"\W+", "", (job["company"]+"|"+job["title"]).lower()); return hashlib.sha1(key.encode()).hexdigest()[:20]
def excerpt(text):
    parts = re.split(r"(?<=[.!?])\s+", text); useful = [x for x in parts if re.search(r"\b(?:python|experience|fresher|intern)\b", x, re.I)]
    value = " ".join((useful or parts)[:2]); return value[:220].rstrip()+("…" if len(value) > 220 else "")
def messages(jobs):
    header = f"🚀 *Jobs & Internships — {NOW.astimezone(TZ):%d %b %Y}* (Last 7 Days | Freshers & Entry-Level)\n"
    batches, current = [], header
    for job in jobs:
        posted = when(job["posted"]).astimezone(TZ).strftime("%d %b")
        loc_tag = "🏠 Remote" if job["remote"] else f"📍 {job['location'][:30]}" if job['location'] else "🇮🇳 India"
        block = (
            f"\n✅ *{job['title'][:50]}*\n"
            f"   🏢 {job['company']} | {loc_tag}\n"
            f"   🕒 {posted} | {job['source']}\n"
            f"   🔗 {job['url']}\n"
        )
        if len(current)+len(block) > 3500: batches.append(current); current = header+"_(continued)_\n"
        current += block
    if current != header: batches.append(current)
    return batches
def send(message):
    """Send alert via messaging provider.
    Providers (set WHATSAPP_PROVIDER env var):
      telegram   — FREE forever, unlimited. Needs TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID  ← RECOMMENDED
      callmebot  — FREE unlimited, personal WhatsApp. Needs CALLMEBOT_PHONE + CALLMEBOT_APIKEY
      whapi      — Free 150 msg trial then paid. Needs WHATSAPP_TOKEN + WHATSAPP_GROUP_ID
      wassenger  — Paid. Needs WHATSAPP_TOKEN + WHATSAPP_GROUP_ID
    DRY_RUN=1 prints instead of sending.
    """
    if os.getenv("DRY_RUN") == "1":
        print(message)
        return
    raw_provider = (os.getenv("WHATSAPP_PROVIDER") or "telegram").strip().lower()
    provider = raw_provider if raw_provider in ("telegram", "callmebot", "wassenger", "whapi") else "telegram"

    if provider == "telegram":
        # ✅ Best free option — unlimited, forever, no trial
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        raw_chats = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        chat_ids  = [c.strip() for c in raw_chats.split(",") if c.strip()]
        if not bot_token or not chat_ids:
            print("::error title=Missing Telegram Credentials::TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing! Set them in GitHub Secrets (Settings -> Secrets and variables -> Actions).")
            return
        for cid in chat_ids:
            for chunk in [message[i:i+4000] for i in range(0, len(message), 4000)]:
                try:
                    r = HTTP.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json={"chat_id": cid, "text": chunk},
                    )
                    r.raise_for_status()
                    print(f"[info] Telegram message delivered successfully to chat/channel {cid}! (HTTP {r.status_code})")
                except Exception as exc:
                    print(f"[warn] Telegram send failed for {cid}: {exc}")
        return

    elif provider == "callmebot":
        phone = os.getenv("CALLMEBOT_PHONE", "").strip()
        apikey = os.getenv("CALLMEBOT_APIKEY", "").strip()
        if not phone or not apikey:
            print("[warn] CALLMEBOT_PHONE or CALLMEBOT_APIKEY is missing.")
            return
        try:
            response = HTTP.get(
                "https://api.callmebot.com/whatsapp.php",
                params={"phone": phone, "text": message, "apikey": apikey},
            )
            response.raise_for_status()
        except Exception as exc:
            print(f"[warn] Callmebot send failed: {exc}")

    elif provider in ("wassenger", "whapi"):
        token = os.getenv("WHATSAPP_TOKEN", "").strip()
        group = os.getenv("WHATSAPP_GROUP_ID", "").strip()
        if not token or not group:
            print(f"[warn] WHATSAPP_TOKEN or WHATSAPP_GROUP_ID is missing for {provider}.")
            return
        endpoint = "https://api.wassenger.com/v1/messages" if provider == "wassenger" else "https://gate.whapi.cloud/messages/text"
        headers = {"Token": token} if provider == "wassenger" else {"Authorization": f"Bearer {token}"}
        payload = {"group": group, "message": message} if provider == "wassenger" else {"to": group, "body": message}
        try:
            response = HTTP.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
        except Exception as exc:
            print(f"[warn] {provider} send failed: {exc}")
def main():
    best = {}
    all_jobs = ats_jobs() + accenture_jobs() + indigo_jobs() + internshala_jobs() + unstop_jobs()
    for job in all_jobs:
        key = identity(job)
        if qualifies(job) and (key not in best or when(job["posted"]) > when(best[key]["posted"])): best[key] = job
    try: seen = json.loads(SEEN.read_text())
    except (FileNotFoundError, json.JSONDecodeError): seen = {}
    expiry = (NOW-timedelta(days=120)).isoformat(); seen = {k:v for k,v in seen.items() if isinstance(v, str) and v >= expiry}
    force = os.getenv("FORCE_SEND") == "1"
    jobs = [x for x in best.values() if force or identity(x) not in seen]
    jobs.sort(key=lambda x:(bool(re.search(r"\b(?:rudrapur|haldwani|pantnagar|sidcul|kichha|sitarganj|kashipur|ramnagar|nainital|udham singh nagar|uttarakhand|uttaranchal)\b", x["location"], re.I)), bool(re.search(r"\b(?:delhi|ncr|noida|gurugram|gurgaon|ghaziabad|faridabad)\b", x["location"], re.I)), mode(x)=="Remote", when(x["posted"])), reverse=True); jobs = jobs[:MAX_JOBS]
    if not jobs: print("No new matching jobs."); return
    batches = messages(jobs)
    for batch in batches: send(batch)
    if os.getenv("DRY_RUN") != "1":
        seen.update({identity(x):NOW.isoformat() for x in jobs}); temp = SEEN.with_suffix(".tmp")
        temp.write_text(json.dumps(seen, indent=2)); temp.replace(SEEN)
    print(f"{'Found' if os.getenv('DRY_RUN') == '1' else 'Sent'} {len(jobs)} new job(s) in {len(batches)} message(s).")
if __name__ == "__main__": main()
