#!/usr/bin/env python3
"""Daily, deduplicated remote client leads for web, AI and video services."""
import hashlib, json, os, re
from datetime import timedelta
from pathlib import Path
from xml.etree import ElementTree as ET
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
BAD = re.compile(r"\b(?:registration fee|security deposit|pay (?:a |the )?fee|gift cards?|crypto investment|recharge task|commission[- ]only|commission based|unpaid (?:test|trial)|equity[- ]only|adult content)\b", re.I)
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
def add(out, *, ident, kind, title, client, service, budget, location, url, desc, posted, source, score, draft=""):
    out.append({"id":lead_id(source, ident),"kind":kind,"title":core.clean(title),"client":core.clean(client),"service":service,
                "budget":budget,"location":location,"url":url,"desc":core.clean(desc),"posted":posted,"source":source,"score":score,"draft":draft})
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
                floor = float(os.getenv("MIN_HOURLY_USD", "5") if row.get("type") == "hourly" else os.getenv("MIN_FIXED_USD", "40"))
                if not service or not is_fresh(posted) or BAD.search(text) or OUTSIDE.search(title) or row.get("local") or usd < floor or len(text) < 100: continue
                bids = row.get("bid_stats", {}).get("bid_count") or 0
                score = 70+5*bool(INTENT.search(text))+5*(len(text)>300)+8*(bids<=10)+4*bool(row.get("urgent") or row.get("featured"))-5*(bids>50)
                slug = row.get("seo_url") or str(row.get("id")); project_url = f"https://www.freelancer.com/projects/{slug}"
                add(out, ident=str(row.get("id")), kind="Client request", title=row.get("title"), client="Public marketplace client",
                    service=service, budget=shown, location="Remote / location not verified", url=project_url, desc=text,
                    posted=posted, source="Freelancer public API", score=score)
        except Exception as exc: print(f"[warn] Freelancer {spec}: {exc}")
    return out
# Direct public [HIRING] posts; never auto-message or harvest private contact data.
def reddit_leads():
    out, feed = [], "https://www.reddit.com/r/forhire/new/.rss?limit=100"
    try:
        root = ET.fromstring(core.HTTP.get(feed).content); atom = "{http://www.w3.org/2005/Atom}"
        for entry in root.findall(atom+"entry"):
            title = entry.findtext(atom+"title", ""); content = entry.findtext(atom+"content", "")
            desc, posted = core.clean(content), entry.findtext(atom+"updated", "")
            blob = title+" "+desc; service = classify(blob)
            if not re.match(r"^\s*\[HIRING\]", title, re.I) or not service or not is_fresh(posted) or not REMOTE.search(blob) or BAD.search(blob): continue
            link = next((x.get("href") for x in entry.findall(atom+"link") if x.get("href")), "")
            author = entry.find(atom+"author"); name = author.findtext(atom+"name", "Public poster") if author is not None else "Public poster"
            cash = re.search(r"(?i)(?:USD|INR|[$₹])\s?\d[\d,.]*(?:\s*(?:k|lakh|lac|million))?(?:\s*(?:-|–|to)\s*(?:USD|INR|[$₹])?\s?\d[\d,.]*(?:\s*(?:k|lakh|lac|million))?)?(?:\s*(?:/|per)\s*(?:hr|hour|video|reel|month|project))?", blob)
            score = 65+10*bool(cash)+5*bool(INTENT.search(blob))+5*(len(desc)>250)
            add(out, ident=link, kind="Direct hiring post", title=title, client=name, service=service,
                budget=cash.group(0) if cash else "Not stated—confirm first", location="Remote (verify eligibility)", url=link,
                desc=desc, posted=posted, source="Reddit r/forhire original post", score=score)
    except Exception as exc: print(f"[warn] Reddit: {exc}")
    return out
# Quality-scored local prospects from the approval-first Places CRM; it never auto-sends.
def prospect_leads():
    out=[]
    try:
        from prospect_app import followups_for_alert, leads_for_alert
        for row in leads_for_alert():
            signals=", ".join(row.get("signals") or ["manual review required"])
            service="AI" if row.get("website") and "CTA" in signals else "Web"
            desc=f"Google listing: {row.get('rating',0):g}/5 from {row.get('reviews',0)} reviews. Signals: {signals}. Suggested offer: {row.get('offer','')}"
            add(out,ident=row["id"],kind="Local prospect—manual approval required",title=f"Digital growth opportunity: {row['name']}",client=row["name"],
                service=service,budget="Not a posted project",location=row.get("address") or row.get("city",""),url=row.get("maps_url",""),desc=desc,
                posted=row.get("first_seen"),source="Google Maps • Prospect CRM",score=int(row.get("score",0)),draft=row.get("pitch_en",""))
        for row in followups_for_alert():
            add(out,ident=row["id"]+"|"+row["follow_up"],kind="CRM follow-up due—manual action",title=f"Follow up: {row['name']}",client=row["name"],service="Web",
                budget="Existing conversation",location=row.get("address") or row.get("city",""),url=row.get("maps_url",""),desc=f"Pipeline stage: {row['stage']}. Follow-up was scheduled for {row['follow_up']}.",
                posted=NOW,source="Google Maps • CRM follow-up",score=max(90,int(row.get("score",0))),draft=row.get("followup_pitch",""))
    except Exception as exc: print(f"[warn] Prospect CRM: {exc}")
    return out
def excerpt(text):
    text = re.sub(r"\s+", " ", text); return text[:240].rstrip()+("…" if len(text)>240 else "")
def messages(leads):
    header = f"💼 *Client Leads — {NOW.astimezone(TZ):%d %b %Y}*\n"
    batches, current = [], header
    for row in leads:
        score_emoji = "🔥" if row["score"] >= 83 else "✅" if row["score"] >= 70 else "👀"
        posted = core.when(row["posted"]).astimezone(TZ).strftime("%d %b %I:%M %p")
        src = "Freelancer" if "freelancer" in row["source"].lower() else "Reddit r/forhire"
        block = (
            f"\n{score_emoji} *{row['title'][:55]}*\n"
            f"   {row['service']} • {row['budget']} • {row['score']}/100\n"
            f"   🕒 {posted} | {src}\n"
            f"   🔗 {row['url']}\n"
        )
        if len(current)+len(block) > 3500: batches.append(current); current = header+"_(continued)_\n"
        current += block
    if current != header: batches.append(current)
    return batches
def main():
    best = {}
    for row in freelancer_leads()+reddit_leads()+prospect_leads():
        if row["id"] not in best or row["score"] > best[row["id"]]["score"]: best[row["id"]] = row
    try: seen = json.loads(SEEN.read_text())
    except (FileNotFoundError, json.JSONDecodeError): seen = {}
    expiry = (NOW-timedelta(days=90)).isoformat(); seen = {k:v for k,v in seen.items() if isinstance(v,str) and v>=expiry}
    leads = [x for x in best.values() if x["id"] not in seen]
    leads.sort(key=lambda x:("prospect" in x["kind"].lower(), -x["score"], -core.when(x["posted"]).timestamp())); leads=leads[:MAX_LEADS]
    if not leads: print("No new client leads."); return
    batches = messages(leads)
    for batch in batches: core.send(batch)
    if os.getenv("DRY_RUN") != "1":
        seen.update({x["id"]:NOW.isoformat() for x in leads}); temp=SEEN.with_suffix(".tmp")
        temp.write_text(json.dumps(seen, indent=2)); temp.replace(SEEN)
    print(f"{'Found' if os.getenv('DRY_RUN')=='1' else 'Sent'} {len(leads)} client lead(s) in {len(batches)} message(s).")
if __name__ == "__main__": main()
