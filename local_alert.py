#!/usr/bin/env python3
"""Official-careers alert for entry/junior skill matches around Kumaon/SIDCUL."""
import hashlib, json, os, re
from datetime import timedelta
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import job_alert as core
NOW, TZ = core.NOW, core.TZ
HOURS = int(os.getenv("LOCAL_HOURS_OLD", "168")); MAX_JOBS = int(os.getenv("MAX_LOCAL_JOBS", "10"))
SEEN = Path(os.getenv("LOCAL_SEEN_FILE", "seen_local_jobs.json"))
LOCAL = re.compile(r"\b(?:rudrapur|haldwani|pantnagar|sidcul|kichha|sitarganj|kashipur|ramnagar|nainital|udham singh nagar|uttarakhand|uttaranchal)\b", re.I)
RELATED = re.compile(r"\b(?:data|analytics?|MIS|business intelligence|BI|reporting|dashboard|Power BI|Tableau|Python|SQL|advanced Excel|MS Excel|information technology|IT support|software|web(?:site| development| developer)?|WordPress|Shopify|digital marketing|graphic design|content creator|video edit(?:ing|or)?|social media|artificial intelligence|AI|chatbot|automation)\b", re.I)
ENTRY = re.compile(r"\b(?:intern(?:ship)?|fresher|trainee|apprentice|junior|associate|graduate|fixed[- ]term|officer|executive|coordinator|assistant|developer|designer|editor|creator|analyst)\b", re.I)
PLANT = re.compile(r"\b(?:maintenance|production|operator|chemist|quality|electrical|mechanical|instrumentation|manufacturing|safety|warehouse)\b", re.I)
OVER = re.compile(r"\b(?:minimum|at least)?\s*(?:two|three|four|five|six|seven|eight|nine|ten)\+?\s+years?\b", re.I)
DEFAULT_SF = "Tata Motors|https://careers.tatamotors.com|Pantnagar;Mahindra|https://jobs.mahindracareers.com|Rudrapur;Reckitt|https://careers.reckitt.com|Uttarakhand;Perfetti Van Melle|https://jobs.perfettivanmelle.com|Rudrapur"
SF_SITES = DEFAULT_SF+(";"+os.getenv("LOCAL_SF_SITES") if os.getenv("LOCAL_SF_SITES") else "")
def text(node, selector, attr=None):
    found = node.select_one(selector); return (found.get(attr) if attr and found else found.get_text(" ", strip=True) if found else "")
def add(out, company, title, location, url, desc, posted, source, min_exp=None):
    blob = core.clean(title+" "+desc); stamp = core.when(posted)
    if not (LOCAL.search(location+" "+blob) and RELATED.search(blob) and stamp and stamp >= NOW-timedelta(hours=HOURS)): return
    if core.SENIOR.search(title) or (PLANT.search(title) and not RELATED.search(title)) or core.OVER_ONE.search(desc) or OVER.search(desc) or (isinstance(min_exp,(int,float)) and min_exp>1): return
    explicit = bool(core.ENTRY_TITLE.search(title) or core.ENTRY_TEXT.search(desc) or (isinstance(min_exp,(int,float)) and min_exp<=1))
    if not explicit and not ENTRY.search(title) and not RELATED.search(title): return
    matches=[]
    for value in RELATED.findall(blob):
        label=value.strip().title()
        if label.lower() not in [x.lower() for x in matches]: matches.append(label)
    out.append({"id":hashlib.sha1((company+"|"+title+"|"+location).lower().encode()).hexdigest()[:20],"company":company,
                "title":core.clean(title),"location":core.clean(location),"url":url,"desc":core.clean(desc),"posted":posted,
                "source":source,"fit":"Entry-level indicated" if explicit else "Experience unclear—check JD","skills":", ".join(matches[:5])})
# Official SAP SuccessFactors career sites: Tata Motors, Mahindra, Reckitt and Perfetti.
def successfactors_jobs():
    out=[]
    for spec in filter(None,map(str.strip,SF_SITES.split(";"))):
        try:
            company, base, query = spec.split("|",2)
            page=BeautifulSoup(core.HTTP.get(base+"/search/",params={"q":"","locationsearch":query}).text,"html.parser"); done=set()
            for link in page.select("a.jobTitle-link"):
                url=urljoin(base,link.get("href",""))
                if not url or url in done: continue
                done.add(url); row=link.find_parent("tr") or link.find_parent("li") or link.parent
                location=text(row,".jobLocation"); posted=text(row,".jobDate")
                detail=BeautifulSoup(core.HTTP.get(url).text,"html.parser")
                title=text(detail,'[itemprop="title"]') or link.get_text(" ",strip=True)
                desc=text(detail,'[itemprop="description"]') or text(detail,".job")
                posted=posted or text(detail,'[itemprop="datePosted"]',"content")
                locality=text(detail,'[itemprop="addressLocality"]',"content"); region=text(detail,'[itemprop="addressRegion"]',"content")
                location=location or ", ".join(filter(None,[locality,region,query]))
                add(out,company,title,location,url,desc,posted,"Official company SuccessFactors")
        except Exception as exc: print(f"[warn] Local ATS {spec}: {exc}")
    return out
# Britannia's employer-linked TurboHire public API, including its Rudrapur plant.
def britannia_jobs():
    out=[]; api="https://thapi-stage2.azurewebsites.net"; org="c143932d-0df7-4856-9dc5-0a9f1ca26dc5"
    origin={"Origin":"https://britannia.turbohire.co","Referer":"https://britannia.turbohire.co/"}
    try:
        token=core.api("GET",api+"/api/token/noauth",headers=origin)["access_token"]
        rows=core.api("POST",api+f"/api/careerpagev2/filteredjobs?orgId={org}&pageType=0",headers={**origin,"Authorization":"Bearer "+token},json={}).get("Result",[])
        for row in rows:
            try: location=", ".join(x.get("Address","") for x in json.loads(row.get("Location") or "[]"))
            except (json.JSONDecodeError,TypeError): location=str(row.get("Location") or "")
            exp=row.get("Experience") or {}; desc=(row.get("JobDescV2") or "")+" "+" ".join(row.get("Skills") or [])
            url="https://britannia.turbohire.co/job/publicjobs/"+row.get("JobIdObfuscated","")
            add(out,"Britannia Industries",row.get("JobTitle",""),location,url,desc,row.get("PublishedDate"),"Britannia official TurboHire",exp.get("MinExp"))
    except Exception as exc: print(f"[warn] Britannia local feed: {exc}")
    return out
# Roquette's official structured job pages for its Pantnagar food-ingredients plant.
def roquette_jobs():
    out=[]; base="https://www.roquette.com/careers/job-opportunities"
    try:
        page=BeautifulSoup(core.HTTP.get(base,params={"q":"Pantnagar"}).text,"html.parser"); done=set()
        for link in page.select('a[href*="/careers/job-opportunities/"]'):
            url=urljoin(base,link.get("href",""))
            if url==base or url in done: continue
            done.add(url); detail=BeautifulSoup(core.HTTP.get(url).text,"html.parser"); job=None
            for script in detail.select('script[type="application/ld+json"]'):
                try:
                    value=json.loads(script.string or "{}"); job=value if value.get("@type")=="JobPosting" else job
                except (json.JSONDecodeError,AttributeError): pass
            if not job: continue
            address=(job.get("jobLocation") or {}).get("address") or {}; location=", ".join(filter(None,[address.get("addressLocality"),address.get("addressRegion"),address.get("addressCountry")]))
            add(out,"Roquette",job.get("title",""),location,url,job.get("description",""),job.get("datePosted"),"Roquette official careers")
    except Exception as exc: print(f"[warn] Roquette: {exc}")
    return out
# Nestlé's official India search is queried by each local hub; no aggregator copies.
def nestle_jobs():
    out=[]; base="https://www.nestle.in/jobs/search-jobs"
    for place in ("Pantnagar","Rudrapur","Haldwani"):
        try:
            page=BeautifulSoup(core.HTTP.get(base,params={"country":"India","location":place,"sort":"recent"}).text,"html.parser"); done=set()
            for link in page.select('a[href*="jobdetails.nestle.com/job/"]'):
                url=link.get("href","")
                if not url or url in done: continue
                done.add(url); detail=BeautifulSoup(core.HTTP.get(url).text,"html.parser")
                add(out,"Nestlé",text(detail,'[itemprop="title"]') or link.get_text(" ",strip=True),place+", Uttarakhand",url,
                    text(detail,'[itemprop="description"]'),text(detail,'[itemprop="datePosted"]',"content"),"Nestlé official careers")
        except Exception as exc: print(f"[warn] Nestlé {place}: {exc}")
    return out
def messages(jobs):
    header=f"🏭 *Kumaon/SIDCUL Skill-Match Jobs — {NOW.astimezone(TZ):%d %b %Y}*\nRudrapur • Haldwani • Pantnagar • nearby hubs\n✅ Original company career pages only\n"
    batches,current=[],header
    for row in jobs:
        posted=core.when(row["posted"]).astimezone(TZ).strftime("%d %b %Y")
        summary=(row["desc"][:240].rstrip()+"…") if len(row["desc"])>240 else row["desc"]
        block=f"\n• *{row['title']}* — {row['company']}\n  📍 {row['location']} | 🧭 {row['fit']}\n  🛠 {row['skills'] or 'See official JD'}\n  🕒 {posted} | {row['source']}\n  🔗 {row['url']}\n  📝 {summary}\n"
        if len(current)+len(block)>3500: batches.append(current);current=header+"_(continued)_\n"
        current+=block
    if current!=header:batches.append(current)
    return batches
def main():
    best={}
    for row in successfactors_jobs()+britannia_jobs()+roquette_jobs()+nestle_jobs(): best[row["id"]]=row
    try: seen=json.loads(SEEN.read_text())
    except (FileNotFoundError,json.JSONDecodeError):seen={}
    expiry=(NOW-timedelta(days=120)).isoformat();seen={k:v for k,v in seen.items() if isinstance(v,str) and v>=expiry}
    jobs=[x for x in best.values() if x["id"] not in seen];jobs.sort(key=lambda x:core.when(x["posted"]),reverse=True);jobs=jobs[:MAX_JOBS]
    if not jobs:print("No new Kumaon/SIDCUL skill-match jobs.");return
    batches=messages(jobs)
    for batch in batches:core.send(batch)
    if os.getenv("DRY_RUN")!="1":
        seen.update({x["id"]:NOW.isoformat() for x in jobs});temp=SEEN.with_suffix(".tmp");temp.write_text(json.dumps(seen,indent=2));temp.replace(SEEN)
    print(f"{'Found' if os.getenv('DRY_RUN')=='1' else 'Sent'} {len(jobs)} local skill-match job(s) in {len(batches)} message(s).")
if __name__=="__main__":main()
