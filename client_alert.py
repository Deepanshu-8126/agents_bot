#!/usr/bin/env python3
"""Daily, deduplicated remote client leads for web, AI and video services."""
import hashlib, json, os, re
from datetime import timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

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

import job_alert as core
NOW, TZ = core.NOW, core.TZ
HOURS = int(os.getenv("CLIENT_HOURS_OLD", "48")); MAX_LEADS = int(os.getenv("MAX_CLIENT_LEADS", "12"))
SEEN = Path(os.getenv("CLIENT_SEEN_FILE", "seen_clients.json"))
DEFAULT_SEARCHES = "Web|website,Web|landing page,Web|wordpress,Web|shopify,Video|video editing,Video|youtube editor,Video|reels editor,AI|AI automation,AI|chatbot,AI|n8n"
SEARCHES = os.getenv("FREELANCER_SEARCHES", DEFAULT_SEARCHES)
SERVICE = {
    "Video": re.compile(r"\b(?:video edit(?:ing|or)?|YouTube editor|reels?|short[- ]form|motion graphics|after effects|premiere pro|promo video|video production)\b", re.I),
    "Web": re.compile(r"\b(?:web(?:site| design| developer| development| app)?|landing page|WordPress|Shopify|Webflow|front[- ]?end|e-?commerce)\b", re.I),
    "AI": re.compile(r"\b(?:AI|artificial intelligence|chatbot|LLM|OpenAI|AI agent|n8n|zapier|make\.com|automation)\b", re.I),
}
BAD = re.compile(
    r"\b(?:"
    r"unpaid test|free sample|commission[- ]only|commission based|"
    r"pay deposit|security deposit|registration fee|pay (?:a |the )?fee|"
    r"pay for training|training fee|upfront fee|"
    r"telegram\s*@|t\.me/|contact (?:me )?on telegram|whatsapp\s*@|"
    r"need 100 projects|100 reviews|gift cards?|crypto investment|recharge task|adult content"
    r")\b",
    re.I
)
OUTSIDE = re.compile(r"\b(?:workshop facilitator|workshop trainer|AI trainer|AI training|AI engineer|AI architect|machine learning engineer|prompt architect|model review|model evaluation|data annotation|data labeling|native speakers?|voice recording|audio recording|transcription|SEO|search engine optimization|meta ads?|google ads?|social media manager|PLC|SCADA|PCB|embedded hardware|electrical schematic|lead generation|salesperson)\b", re.I)
REMOTE = re.compile(r"\b(?:remote|worldwide|anywhere|online|work from home|WFH|United States|USA|India)\b", re.I)
INTENT = re.compile(r"\b(?:I need|we need|looking for|seeking|hiring|want to hire|required?|project)\b", re.I)
def classify(text):
    return next((name for name, pattern in SERVICE.items() if pattern.search(text)), None)
def is_fresh(value):
    posted = core.when(value); return bool(posted and NOW-timedelta(hours=HOURS) <= posted <= NOW+timedelta(hours=1))
def lead_id(source, value):
    return hashlib.sha1(f"{source}|{value}".lower().encode()).hexdigest()[:20]
def money(project):
    cur, budget = project.get("currency", {}), project.get("budget", {})
    low, high = budget.get("minimum"), budget.get("maximum"); sign, code = cur.get("sign", ""), cur.get("code", "")
    if low is None and high is None: return "Not stated", 0
    if low is None: low = high
    fmt = lambda x: f"{float(x):,.2f}".rstrip("0").rstrip(".")
    value = f"{sign}{fmt(low)}" if high in (None, low) else f"{sign}{fmt(low)}–{sign}{fmt(high)}"
    return value+f" {code}"+("/hr" if project.get("type") == "hourly" else " fixed"), (high or low or 0)*float(cur.get("exchange_rate") or 0)
def pitch(service, title):
    offer = {"Web":"a responsive, conversion-focused site with clean handover", "Video":"a polished edit with strong pacing, captions and platform-ready exports", "AI":"a lean AI automation with clear workflow, testing and documentation"}[service]
    portfolio = os.getenv("PORTFOLIO_URL", "")
    return f"Hi, I saw your {title} requirement. I can deliver {offer}. Could you share the exact scope, references and timeline? I can send a short plan"+(f" and relevant work: {portfolio}" if portfolio else " before we start")+"."
def add(out, *, ident, kind, title, client, service, budget, location, url, desc, posted, source, score, draft="", skills=None, ptype="Fixed", hourly_rate=None, client_info=""):
    out.append({"id":lead_id(source, ident),"kind":kind,"title":core.clean(title),"client":core.clean(client),"service":service,
                "budget":budget,"location":location,"url":url,"desc":core.clean(desc),"posted":posted,"source":source,"score":score,"draft":draft,
                "skills":skills or [service],"type":ptype,"hourly_rate":hourly_rate,"client_info":client_info})
# High-intent, public projects from Freelancer's official projects API.
def freelancer_leads():
    out, url = [], "https://www.freelancer.com/api/projects/0.1/projects/active/"
    for spec in filter(None, map(str.strip, SEARCHES.split(","))):
        try:
            _, query = spec.split("|", 1)
            data = core.api("GET", url, params={"query":query,"limit":50,"sort_field":"submitdate","full_description":"true","job_details":"true"})
            for row in data.get("result", {}).get("projects", []):
                title = core.clean(row.get("title", "")); text = core.clean(title+" "+row.get("description", "")); service = classify(title)
                shown, usd = money(row); posted = row.get("time_submitted")
                floor = float(os.getenv("MIN_HOURLY_USD", "5") if row.get("type") == "hourly" else os.getenv("MIN_FIXED_USD", "30"))
                # Filter out low budget, fake, or spam gigs
                if not service or not is_fresh(posted) or BAD.search(text) or OUTSIDE.search(title) or row.get("local") or usd < floor or len(text) < 100: continue
                if row.get("type") == "hourly" and usd < 5: continue
                bids = row.get("bid_stats", {}).get("bid_count") or 0
                score = 70+5*bool(INTENT.search(text))+5*(len(text)>300)+8*(bids<=10)+4*bool(row.get("urgent") or row.get("featured"))-5*(bids>50)
                slug = row.get("seo_url") or str(row.get("id")); project_url = f"https://www.freelancer.com/projects/{slug}"
                ptype = "Hourly" if row.get("type") == "hourly" else "Fixed"
                skills = [j.get("name") for j in row.get("jobs", []) if isinstance(j, dict) and j.get("name")]
                clean_desc = core.clean(row.get("description", ""))
                add(out, ident=str(row.get("id")), kind="Client request", title=row.get("title"), client="Public marketplace client",
                    service=service, budget=shown, location="Remote / location not verified", url=project_url, desc=clean_desc,
                    posted=posted, source="Freelancer public API", score=score, skills=skills, ptype=ptype, hourly_rate=usd if ptype=="Hourly" else None)
        except Exception as exc: print(f"[warn] Freelancer {spec}: {exc}")
    return out
# Direct public [HIRING] posts; never auto-message or harvest private contact data.
def reddit_leads():
    out, feed = [], "https://www.reddit.com/r/forhire/new/.rss?limit=100"
    try:
        r = core.HTTP.get(feed, headers={"User-Agent": "web:client-leads:v1.0 (by /u/deepanshu_dev)"})
        root = ET.fromstring(r.content); atom = "{http://www.w3.org/2005/Atom}"
        for entry in root.findall(atom+"entry"):
            title = entry.findtext(atom+"title", ""); content = entry.findtext(atom+"content", "")
            desc, posted = core.clean(content), entry.findtext(atom+"updated", "")
            blob = title+" "+desc; service = classify(blob)
            if not re.match(r"^\s*\[HIRING\]", title, re.I) or not service or not is_fresh(posted) or not REMOTE.search(blob) or BAD.search(blob): continue
            cash = re.search(r"(?i)(?:USD|INR|[$₹])\s?\d[\d,.]*(?:\s*(?:k|lakh|lac|million))?(?:\s*(?:-|–|to)\s*(?:USD|INR|[$₹])?\s?\d[\d,.]*(?:\s*(?:k|lakh|lac|million))?)?(?:\s*(?:/|per)\s*(?:hr|hour|video|reel|month|project))?", blob)
            # Filter: genuine client posts state their budget
            if not cash: continue
            link = next((x.get("href") for x in entry.findall(atom+"link") if x.get("href")), "")
            author = entry.find(atom+"author"); name = author.findtext(atom+"name", "Public poster") if author is not None else "Public poster"
            score = 65+10*bool(cash)+5*bool(INTENT.search(blob))+5*(len(desc)>250)
            ptype = "Hourly" if "/hr" in blob.lower() or "hour" in blob.lower() else "Fixed"
            add(out, ident=link, kind="Direct hiring post", title=title, client=name, service=service,
                budget=cash.group(0), location="Remote (verify eligibility)", url=link,
                desc=desc, posted=posted, source="Reddit r/forhire original post", score=score, skills=[service], ptype=ptype)
    except Exception as exc: print(f"[warn] Reddit: {exc}")
    return out
DISCORD_KEYWORDS = re.compile(
    r"\b(?:"
    r"need|hiring|looking for|budget|pay|"
    r"editor|website|ugc|framer|webflow|n8n|automation|video"
    r")\b",
    re.I
)

# 100% FREE Discord hidden leads from server channels via Discord Bot API (No paid APIs)
def fetch_discord_leads():
    token = os.getenv("DISCORD_TOKEN", "").strip()
    channels_raw = os.getenv("DISCORD_CHANNELS", "").strip()
    if not token or not channels_raw:
        return []

    auth_header = token if token.startswith("Bot ") else f"Bot {token}"
    headers = {
        "Authorization": auth_header,
        "User-Agent": "DiscordBot (https://github.com/Deepanshu-8126/agents_bot, v1.0)"
    }
    
    out = []
    hours_window = int(os.getenv("DISCORD_HOURS", "3"))
    cutoff = NOW - timedelta(hours=hours_window)

    for item in filter(None, [c.strip() for c in channels_raw.split(",")]):
        if ":" in item:
            guild_id, cid = item.split(":", 1)
        elif "/" in item:
            guild_id, cid = item.split("/", 1)
        else:
            guild_id, cid = "@me", item

        try:
            url = f"https://discord.com/api/v10/channels/{cid}/messages"
            res = core.HTTP.get(url, headers=headers, params={"limit": 20})
            if res.status_code == 401 and not token.startswith("Bot "):
                # Fallback if user passed direct token
                res = core.HTTP.get(url, headers={"Authorization": token, "User-Agent": headers["User-Agent"]}, params={"limit": 20})

            if res.status_code != 200:
                print(f"[warn] Discord channel {cid}: HTTP {res.status_code}")
                continue
            
            messages = res.json()
            if not isinstance(messages, list):
                continue

            for msg in messages:
                author = msg.get("author", {})
                if author.get("bot"):
                    continue

                content = core.clean(msg.get("content", ""))
                msg_id = str(msg.get("id", ""))
                posted_str = msg.get("timestamp", "")
                posted_dt = core.when(posted_str)

                if not posted_dt or posted_dt < cutoff:
                    continue

                # Filter by required keywords: need, hiring, looking for, budget, pay
                if not DISCORD_KEYWORDS.search(content) or BAD.search(content):
                    continue

                service = classify(content) or "Freelance"

                cash = re.search(
                    r"(?i)(?:USD|INR|EUR|GBP|CAD|AUD|[$₹€£])\s?\d[\d,.]*(?:\s*(?:k|lakh|million))?(?:\s*(?:-|–|to)\s*(?:USD|INR|EUR|GBP|CAD|AUD|[$₹€£])?\s?\d[\d,.]*)?(?:\s*(?:/|per)\s*(?:hr|hour|video|reel|month|project|page))?",
                    content
                )
                if cash:
                    budget = cash.group(0).strip()
                elif "budget" in content.lower():
                    m = re.search(r"(?i)budget\s*[:=-]?\s*([^\n,.]+)", content)
                    budget = f"Budget: {m.group(1).strip()}" if m else "Discuss on Discord"
                else:
                    budget = "Discuss on Discord"

                ptype = "Hourly" if "/hr" in content.lower() or "hour" in content.lower() else "Fixed"

                lines = [line.strip() for line in content.splitlines() if line.strip()]
                first_line = lines[0] if lines else content
                title = first_line[:65] + ("..." if len(first_line) > 65 else "")

                client_name = author.get("global_name") or author.get("username") or "Discord Client"
                msg_url = f"https://discord.com/channels/{guild_id}/{cid}/{msg_id}"
                score = 75 + 10 * bool(cash) + 5 * (len(content) > 150)

                add(
                    out,
                    ident=f"discord_{cid}_{msg_id}",
                    kind="Discord Client Request",
                    title=f"Discord: {title}",
                    client=client_name,
                    service=service,
                    budget=budget,
                    location="Remote / Discord",
                    url=msg_url,
                    desc=content,
                    posted=posted_dt,
                    source="Discord Channel",
                    score=score,
                    skills=[service, "Discord"],
                    ptype=ptype,
                )
        except Exception as exc:
            print(f"[warn] Discord {item}: {exc}")

    return out

discord_leads = fetch_discord_leads

# 100% FREE Remotive API + We Work Remotely (WWR) RSS Leads
def fetch_remote_jobs():
    out = []
    hours_window = int(os.getenv("REMOTE_JOBS_HOURS", "24"))
    cutoff = NOW - timedelta(hours=hours_window)

    REMOTE_KEYWORDS = re.compile(
        r"\b(?:"
        r"video edit(?:ing|or)?|reels?|ugc|webflow|framer|n8n|automation|excel|"
        r"landing page|shopify|wordpress|chatbot|ai automation|dashboard"
        r")\b",
        re.I
    )

    # 1. Remotive Free Public API (software-dev, design)
    try:
        url = "https://remotive.com/api/remote-jobs?category=software-dev,design"
        res = core.HTTP.get(url, timeout=20)
        if res.status_code == 200:
            for job in res.json().get("jobs", []):
                title = core.clean(job.get("title", ""))
                company = core.clean(job.get("company_name", "Remote Company"))
                desc = core.clean(job.get("description", ""))
                blob = f"{title} {desc}"
                posted_dt = core.when(job.get("publication_date"))

                if not posted_dt or posted_dt < cutoff:
                    continue

                if not REMOTE_KEYWORDS.search(blob) or BAD.search(blob):
                    continue

                salary = job.get("salary")
                if not salary:
                    cash = re.search(
                        r"(?i)(?:USD|INR|EUR|GBP|CAD|AUD|[$₹€£])\s?\d[\d,.]*(?:\s*(?:k|lakh|million))?(?:\s*(?:-|–|to)\s*(?:USD|INR|EUR|GBP|CAD|AUD|[$₹€£])?\s?\d[\d,.]*)?(?:\s*(?:/|per)\s*(?:hr|hour|video|reel|month|yr|year|project))?",
                        blob
                    )
                    salary = cash.group(0).strip() if cash else None

                if not salary:
                    continue

                service = classify(blob) or "Web"
                tags = job.get("tags") or []
                skills = [service] + [t for t in tags if isinstance(t, str)][:3]

                add(
                    out,
                    ident=f"remotive_{job.get('id', '')}",
                    kind="Verified Remote Job",
                    title=f"{company}: {title}",
                    client=company,
                    service=service,
                    budget=salary,
                    location=job.get("candidate_required_location") or "Remote",
                    url=job.get("url", ""),
                    desc=desc,
                    posted=posted_dt,
                    source="Remotive Official",
                    score=85,
                    skills=skills,
                    ptype="Remote Contract" if "contract" in str(job.get("job_type", "")).lower() else "Remote",
                )
    except Exception as exc:
        print(f"[warn] Remotive API: {exc}")

    # 2. We Work Remotely (WWR) Free RSS Feeds
    wwr_feeds = [
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/remote-design-jobs.rss",
    ]
    for feed in wwr_feeds:
        try:
            r = core.HTTP.get(feed, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=20)
            if r.status_code != 200:
                continue
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                soup = core.BeautifulSoup(r.content, "html.parser")
            for item in soup.find_all("item"):
                title_node = item.find("title")
                title = core.clean(title_node.text) if title_node else ""
                desc_node = item.find("description")
                desc = core.clean(desc_node.text) if desc_node else ""
                blob = f"{title} {desc}"

                pub_node = item.find("pubdate")
                posted_dt = core.when(pub_node.text) if pub_node else None

                if not posted_dt or posted_dt < cutoff:
                    continue

                if not REMOTE_KEYWORDS.search(blob) or BAD.search(blob):
                    continue

                cash = re.search(
                    r"(?i)(?:USD|INR|EUR|GBP|CAD|AUD|[$₹€£])\s?\d[\d,.]*(?:\s*(?:k|lakh|million))?(?:\s*(?:-|–|to)\s*(?:USD|INR|EUR|GBP|CAD|AUD|[$₹€£])?\s?\d[\d,.]*)?(?:\s*(?:/|per)\s*(?:hr|hour|video|reel|month|yr|year|project))?",
                    blob
                )
                salary = cash.group(0).strip() if cash else None

                link_node = item.find("link")
                link = link_node.text.strip() if link_node else ""

                service = classify(blob) or "Web"
                add(
                    out,
                    ident=link or title,
                    kind="Verified Remote Job",
                    title=f"WWR: {title}",
                    client="Verified Employer",
                    service=service,
                    budget=salary or "Competitive / Disclosed in post",
                    location="Remote",
                    url=link,
                    desc=desc,
                    posted=posted_dt,
                    source="WeWorkRemotely",
                    score=85,
                    skills=[service, "Remote"],
                    ptype="Remote",
                )
        except Exception as exc:
            print(f"[warn] WWR {feed}: {exc}")

    return out

def format_client_message(job):
    budget = job.get("budget", "")
    if not budget or budget == "Not stated":
        return None
    # Validate currency exists in budget or is Discord / WWR disclosure
    if not any(curr in str(budget) for curr in ["$", "₹", "USD", "INR", "EUR", "GBP", "AUD", "CAD", "Discuss", "Competitive", "Disclosed"]):
        return None

    title = job.get("title", "")
    desc = job.get("desc", "")
    # Clean and readable description summary
    summary = desc[:260].strip() + ("..." if len(desc) > 260 else "")
    ptype = job.get("type", "Remote")
    
    posted_dt = core.when(job.get("posted"))
    if posted_dt:
        diff_hours = max(1, int((NOW - posted_dt).total_seconds() // 3600))
        hours_ago = f"{diff_hours}h ago"
    else:
        hours_ago = "recently"
        
    source = job.get("source", "").replace(" public API", "").replace(" original post", "")
    skills = job.get("skills", [])
    skills_str = ", ".join(skills[:4]) if skills else job.get("service", "Web/AI")
    url = job.get("url", "")
    draft_pitch = job.get("draft") or pitch(job.get("service", "Web"), title)

    return (
        f"💼 *New Client Requirement*\n\n"
        f"*What client needs:*\n"
        f"{title}\n\n"
        f"*Details:*\n"
        f"{summary}\n\n"
        f"*Budget:* {budget} | *Type:* {ptype}\n"
        f"*Posted:* {hours_ago} | *Source:* {source}\n\n"
        f"*Skills:* {skills_str}\n\n"
        f"*Original Link:* {url}\n\n"
        f"---\n"
        f"💡 *Quick pitch:* {draft_pitch}"
    )
def main():
    best = {}
    all_leads = freelancer_leads() + reddit_leads() + discord_leads() + fetch_remote_jobs()
    for row in all_leads:
        if row["id"] not in best or row["score"] > best[row["id"]]["score"]: best[row["id"]] = row
    try: seen = json.loads(SEEN.read_text())
    except (FileNotFoundError, json.JSONDecodeError): seen = {}
    expiry = (NOW-timedelta(days=90)).isoformat(); seen = {k:v for k,v in seen.items() if isinstance(v,str) and v>=expiry}
    force = os.getenv("FORCE_SEND") == "1"
    leads = [x for x in best.values() if force or x["id"] not in seen]
    leads.sort(key=lambda x:("prospect" in x["kind"].lower(), -x["score"], -core.when(x["posted"]).timestamp()))
    
    cards = []
    processed = []
    for lead in leads:
        card = format_client_message(lead)
        if card:
            cards.append(card)
            processed.append(lead)
            if len(cards) >= MAX_LEADS:
                break

    if not cards:
        print("No new genuine client leads.")
        return
        
    import time
    for card in cards:
        core.send(card)
        time.sleep(0.5)
        
    if os.getenv("DRY_RUN") != "1":
        seen.update({x["id"]:NOW.isoformat() for x in processed}); temp=SEEN.with_suffix(".tmp")
        temp.write_text(json.dumps(seen, indent=2)); temp.replace(SEEN)
    print(f"{'Found' if os.getenv('DRY_RUN')=='1' else 'Sent'} {len(cards)} genuine client lead(s).")
if __name__ == "__main__": main()
