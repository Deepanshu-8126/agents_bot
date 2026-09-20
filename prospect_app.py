#!/usr/bin/env python3
"""Quality-first Google Places prospect engine and approval-first local CRM."""
import argparse, base64, csv, io, ipaddress, json, os, re, socket, threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
import httpx
from bs4 import BeautifulSoup
import job_alert as core
DB_PATH = Path(os.getenv("PROSPECT_DB", "prospects.json"))
HTML_PATH = Path(__file__).with_name("prospect_dashboard.html")
DEFAULT_CITIES = "Agra, Uttar Pradesh, India;Mathura, Uttar Pradesh, India;Noida, Uttar Pradesh, India;Gurugram, Haryana, India;Jaipur, Rajasthan, India;Austin, Texas, USA;Dallas, Texas, USA"
DEFAULT_CATEGORIES = "garment stores and boutiques|Retail;online stores and ecommerce brands|Retail;electronics stores|Retail;furniture stores and interior studios|Retail;jewellery stores|Retail;restaurants and cafes|Food;salons and spas|Beauty;dentists and clinics|Health;hotels and guest houses|Hospitality;gyms and fitness studios|Fitness;coaching centres|Education;manufacturers and exporters|B2B"
OFFERS = {
    "Retail":"a mobile product catalogue, e-commerce/WhatsApp ordering and short product videos",
    "Food":"a fast menu website, order/enquiry automation and offer/reel content",
    "Beauty":"online booking, WhatsApp reminders, review follow-ups and transformation reels",
    "Health":"a clear service website, appointment requests and compliant reminder automation",
    "Hospitality":"a direct-booking enquiry page, WhatsApp follow-up and property videos",
    "Fitness":"trial-class lead capture, follow-up automation and short-form video content",
    "Education":"admission landing pages, enquiry tracking and automated follow-ups",
    "B2B":"a professional product catalogue, quotation workflow and lead-tracking automation",
}
CHAIN = re.compile(r"\b(?:mcdonald'?s|domino'?s|kfc|subway|starbucks|croma|reliance digital|tanishq|cult\.fit)\b", re.I)
LOCK = threading.RLock(); LIVE_CACHE={}; LIVE_REFRESH=None; HYDRATED=False
REFRESH = {"running":False,"started":None,"finished":None,"error":None,"result":None}
def now(): return datetime.now(timezone.utc)
def iso(dt=None): return (dt or now()).isoformat()
def load_db():
    with LOCK:
        try: data=json.loads(DB_PATH.read_text())
        except (FileNotFoundError,json.JSONDecodeError): data={}
        data.setdefault("version",1);data.setdefault("query_cursor",0);data.setdefault("last_refresh",None);data.setdefault("prospects",{})
        return data
def save_db(data):
    with LOCK:
        temp=DB_PATH.with_suffix(".tmp");temp.write_text(json.dumps(data,ensure_ascii=False,indent=2));temp.replace(DB_PATH)
def parse_specs():
    direct=os.getenv("PROSPECT_QUERIES","").strip(); specs=[]
    if direct:
        for value in filter(None,map(str.strip,direct.split(";"))):
            parts=value.split("|",2); specs.append({"query":parts[0],"segment":parts[1] if len(parts)>1 else "Retail","city":parts[2] if len(parts)>2 else parts[0]})
        return specs
    cities=list(filter(None,map(str.strip,os.getenv("PROSPECT_CITIES",DEFAULT_CITIES).split(";"))))
    categories=[]
    for value in filter(None,map(str.strip,os.getenv("PROSPECT_CATEGORIES",DEFAULT_CATEGORIES).split(";"))):
        term,segment=(value.split("|",1)+["Retail"])[:2];categories.append((term.strip(),segment.strip()))
    return [{"query":f"{term} in {city}","segment":segment,"city":city} for city in cities for term,segment in categories]
def selected_specs(data):
    specs=parse_specs()
    if not specs:return []
    count=max(1,min(len(specs),int(os.getenv("MAX_PLACE_QUERIES_PER_RUN","12"))));start=int(data.get("query_cursor",0))%len(specs)
    chosen=[specs[(start+i)%len(specs)] for i in range(count)];data["query_cursor"]=(start+count)%len(specs)
    return chosen
def places_search(key,spec):
    fields="places.id,places.displayName,places.formattedAddress,places.location,places.websiteUri,places.businessStatus,places.googleMapsUri,places.rating,places.userRatingCount,places.primaryType"
    body={"textQuery":spec["query"],"pageSize":max(1,min(20,int(os.getenv("PLACES_PAGE_SIZE","12")))),"languageCode":"en","minRating":3.5,"includePureServiceAreaBusinesses":True}
    return core.api("POST","https://places.googleapis.com/v1/places:searchText",headers={"X-Goog-Api-Key":key,"X-Goog-FieldMask":fields},json=body).get("places",[])
def public_host(url):
    try:
        parsed=urlparse(url)
        if parsed.scheme not in ("http","https") or not parsed.hostname:return False
        for info in socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=="https" else 80)):
            address=ipaddress.ip_address(info[4][0])
            if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:return False
        return True
    except (ValueError,OSError):return False
def audit_site(url):
    if os.getenv("ENABLE_WEBSITE_AUDIT")!="1" or not public_host(url):return {}
    try:
        headers={"User-Agent":"OpportunityResearch/1.0 (+manual-review; one homepage request)","Accept":"text/html"};current=url
        with httpx.Client(timeout=10,follow_redirects=False,headers=headers) as client:
            for _ in range(4):
                response=client.get(current)
                if response.is_redirect:
                    current=str(response.url.join(response.headers["location"]))
                    if not public_host(current):return {"error":"unsafe redirect"}
                    continue
                response.raise_for_status();raw=response.content[:1_000_000];break
            else:return {"error":"redirect loop"}
        soup=BeautifulSoup(raw,"html.parser");body=soup.get_text(" ",strip=True).lower();links=" ".join(a.get("href","") for a in soup.select("a"))
        return {"checked_at":iso(),"https":urlparse(str(response.url)).scheme=="https","mobile":bool(soup.select_one('meta[name="viewport"]')),
                "description":bool(soup.select_one('meta[name="description"]')),"action":bool(re.search(r"\b(?:book|appointment|reserve|order|shop|buy|catalog|enquir|quote|contact)\b",body)),
                "whatsapp":bool(re.search(r"(?:wa\.me|whatsapp)",links,re.I)),"title":soup.title.get_text(" ",strip=True)[:120] if soup.title else ""}
    except Exception as exc:return {"checked_at":iso(),"error":type(exc).__name__}
def score_place(row,segment,audit):
    reviews=int(row.get("userRatingCount") or 0);rating=float(row.get("rating") or 0);website=row.get("websiteUri") or "";signals=[];score=36
    if not website:score+=28;signals.append("No website listed on Google")
    else:
        if audit and not audit.get("error"):
            if not audit.get("mobile"):score+=12;signals.append("No mobile viewport detected")
            if not audit.get("action"):score+=10;signals.append("No clear booking/order/enquiry CTA detected")
            if not audit.get("description"):score+=4;signals.append("No meta description detected")
            if not audit.get("whatsapp"):score+=4;signals.append("No WhatsApp link detected")
            if not audit.get("https"):score+=8;signals.append("Homepage did not finish on HTTPS")
        elif audit.get("error"):signals.append("Website audit inconclusive")
    score+=4 if reviews>=20 else 0;score+=5 if reviews>=75 else 0;score+=5 if reviews>=200 else 0
    score+=5 if rating>=4 else 0;score+=3 if rating>=4.5 else 0;score+=7 if segment in OFFERS else 0
    name=(row.get("displayName") or {}).get("text","")
    if CHAIN.search(name):score-=22;signals.append("Likely chain—lower outreach priority")
    return max(0,min(100,score)),signals
def drafts(name,city,segment,rating,reviews,signals):
    offer=OFFERS.get(segment,OFFERS["Retail"]);fact=f"Google currently shows {rating:g}/5 from {reviews} reviews"
    if "No website listed on Google" in signals:
        observation="I couldn't find a website link on the Google listing"
        observation_hi="Google listing par website link nazar nahi aaya"
    else:
        observation="I noticed a few opportunities in the public website journey"
        observation_hi="public website journey mein kuch improvement opportunities dikhi"
    en=f"Hi {name} team, I found your business while researching {segment.lower()} businesses in {city}. {fact}, and {observation}. I help businesses with {offer}. May I share a free one-page improvement idea tailored to {name}?"
    hi=f"Namaste {name} team, main {city} mein {segment.lower()} businesses research kar raha tha. Aapki Google listing par {rating:g}/5 rating aur {reviews} reviews hain, lekin {observation_hi}. Main {offer} mein help karta hoon. Kya main {name} ke liye ek free one-page improvement idea share kar sakta hoon?"
    return en,hi,offer
def crm_meta(pid,spec,old=None):
    old=old or {};keep=("stage","notes","follow_up","contacted_at","updated_at")
    return {"id":pid,"city":spec["city"],"segment":spec["segment"],"first_seen":old.get("first_seen") or iso(),"last_seen":iso(),**{k:old.get(k,"") for k in keep},"stage":old.get("stage") or "New"}
def live_record(row,meta,audit=None):
    display=row.get("displayName") or {};name=display.get("text") if isinstance(display,dict) else str(display);name=name or "Business"
    reviews=int(row.get("userRatingCount") or 0);rating=float(row.get("rating") or 0);audit=audit or {};score,signals=score_place(row,meta["segment"],audit)
    pitch_en,pitch_hi,offer=drafts(name,meta["city"],meta["segment"],rating,reviews,signals);location=row.get("location") or {};pid=meta["id"]
    return {**meta,"name":name,"primary_type":row.get("primaryType") or "","address":row.get("formattedAddress") or meta["city"],"lat":location.get("latitude"),"lng":location.get("longitude"),
            "website":row.get("websiteUri") or "","maps_url":row.get("googleMapsUri") or f"https://www.google.com/maps/search/?api=1&query_place_id={quote(pid)}","rating":rating,"reviews":reviews,
            "score":score,"signals":signals,"offer":offer,"pitch_en":pitch_en,"pitch_hi":pitch_hi,"audit":audit,"provider":"Google Maps"}
def place_details(pid):
    key=os.getenv("GOOGLE_PLACES_API_KEY")
    if not key:raise RuntimeError("GOOGLE_PLACES_API_KEY is not set")
    fields="id,displayName,formattedAddress,location,websiteUri,businessStatus,googleMapsUri,rating,userRatingCount,primaryType"
    return core.api("GET",f"https://places.googleapis.com/v1/places/{quote(pid,safe='')}",headers={"X-Goog-Api-Key":key,"X-Goog-FieldMask":fields})
def hydrate(pid,meta):
    row=place_details(pid)
    if row.get("businessStatus") not in (None,"OPERATIONAL"):return None
    audit=audit_site(row.get("websiteUri") or "") if row.get("websiteUri") else {}
    record=live_record(row,meta,audit);LIVE_CACHE[pid]=record;return record
def refresh_prospects(persist=True):
    global LIVE_REFRESH
    key=os.getenv("GOOGLE_PLACES_API_KEY")
    if not key:raise RuntimeError("GOOGLE_PLACES_API_KEY is not set")
    data=load_db();chosen=selected_specs(data);minimum_reviews=int(os.getenv("MIN_PROSPECT_REVIEWS","15"));minimum_score=int(os.getenv("MIN_PROSPECT_SCORE","65"));audit_left=int(os.getenv("MAX_WEBSITE_AUDITS","6"));seen_run=set();added=updated=0;errors=[]
    for spec in chosen:
        try:rows=places_search(key,spec)
        except Exception as exc:errors.append(f"{spec['query']}: {exc}");continue
        for row in rows:
            pid=row.get("id");reviews=int(row.get("userRatingCount") or 0);rating=float(row.get("rating") or 0)
            if not pid or pid in seen_run or row.get("businessStatus")!="OPERATIONAL" or reviews<minimum_reviews or rating<3.5:continue
            seen_run.add(pid);old=data["prospects"].get(pid,{});meta=crm_meta(pid,spec,old);audit={}
            if row.get("websiteUri") and audit_left>0:audit=audit_site(row["websiteUri"]);audit_left-=1
            record=live_record(row,meta,audit)
            if record["score"]<minimum_score and not old:continue
            # Persist only the Google Place ID plus our own query/CRM metadata; Places content stays in memory.
            data["prospects"][pid]=meta;LIVE_CACHE[pid]=record
            if old:updated+=1
            else:added+=1
    ttl=now()-timedelta(days=int(os.getenv("PROSPECT_ID_RETENTION_DAYS","180")))
    data["prospects"]={k:v for k,v in data["prospects"].items() if v.get("stage") not in ("New","Skip") or (core.when(v.get("last_seen")) and core.when(v["last_seen"])>=ttl)}
    for pid in list(LIVE_CACHE):
        if pid not in data["prospects"]:LIVE_CACHE.pop(pid,None)
    data["last_refresh"]=iso();data["last_queries"]=[x["query"] for x in chosen];data["last_errors"]=errors[:20]
    if persist:save_db(data)
    LIVE_REFRESH=now()
    return {"queries":len(chosen),"new":added,"updated":updated,"retained_ids":len(data["prospects"]),"visible":len(LIVE_CACHE),"errors":errors[:5]}
def hydrate_tracked():
    global HYDRATED
    if HYDRATED or not os.getenv("GOOGLE_PLACES_API_KEY"):return
    HYDRATED=True;data=load_db();limit=int(os.getenv("MAX_TRACKED_HYDRATIONS","20"));count=0
    for pid,meta in data["prospects"].items():
        if meta.get("stage") in ("New","Skip") or pid in LIVE_CACHE:continue
        try:hydrate(pid,meta);count+=1
        except Exception as exc:print(f"[warn] Place details {pid}: {exc}")
        if count>=limit:break
def api_prospects(hydrate_saved=True):
    if hydrate_saved:hydrate_tracked()
    data=load_db();today=now().astimezone(core.TZ).date();rows=[]
    for pid,value in list(LIVE_CACHE.items()):
        meta=data["prospects"].get(pid) or {k:value.get(k,"") for k in ("id","city","segment","first_seen","last_seen","stage","notes","follow_up","contacted_at","updated_at")}
        row={**value,**meta};first=core.when(row.get("first_seen"));row["is_new"]=bool(first and first.astimezone(core.TZ).date()==today);rows.append(row)
    rows.sort(key=lambda x:(x.get("stage")!="New",-int(x.get("score",0)),-int(x.get("reviews",0))))
    return {"last_refresh":data.get("last_refresh"),"last_queries":data.get("last_queries",[]),"last_errors":data.get("last_errors",[]),"attribution":"Google Maps","prospects":rows}
def leads_for_alert():
    if os.getenv("GOOGLE_PLACES_API_KEY") and LIVE_REFRESH is None:refresh_prospects(persist=os.getenv("DRY_RUN")!="1")
    days=int(os.getenv("PROSPECT_ALERT_DAYS","3"));cutoff=now()-timedelta(days=days);rows=[]
    for row in api_prospects(False)["prospects"]:
        first=core.when(row.get("first_seen"))
        if row.get("stage")=="New" and first and first>=cutoff and int(row.get("score",0))>=int(os.getenv("MIN_PROSPECT_SCORE","65")):rows.append(row)
    return rows[:int(os.getenv("MAX_PROSPECT_ALERTS","6"))]
def followups_for_alert():
    today=now().astimezone(core.TZ).date().isoformat();data=load_db();rows=[]
    for pid,meta in data["prospects"].items():
        if not meta.get("follow_up") or meta["follow_up"]>today or meta.get("stage") in ("New","Won","Lost","Skip"):continue
        try:row=LIVE_CACHE.get(pid) or hydrate(pid,meta)
        except Exception as exc:print(f"[warn] Follow-up details {pid}: {exc}");continue
        if row:
            item={**row,**meta};item["followup_pitch"]=f"Hi {item['name']} team, just following up on the improvement idea I shared. If useful, I can send a concise one-page plan with scope, timeline and a practical starting option—no obligation.";rows.append(item)
    return sorted(rows,key=lambda x:(x.get("follow_up",""),-int(x.get("score",0))))
def place_contact(pid):
    key=os.getenv("GOOGLE_PLACES_API_KEY")
    if not key:raise RuntimeError("GOOGLE_PLACES_API_KEY is not set")
    fields="id,displayName,websiteUri,nationalPhoneNumber,internationalPhoneNumber,googleMapsUri"
    return core.api("GET",f"https://places.googleapis.com/v1/places/{quote(pid,safe='')}",headers={"X-Goog-Api-Key":key,"X-Goog-FieldMask":fields})
def update_prospect(pid,payload):
    allowed_stages={"New","Shortlisted","Approved","Contacted","Replied","Meeting","Proposal","Won","Lost","Skip"};data=load_db()
    if pid not in data["prospects"]:raise KeyError(pid)
    meta=data["prospects"][pid]
    if "stage" in payload:
        if payload["stage"] not in allowed_stages:raise ValueError("Invalid stage")
        meta["stage"]=payload["stage"]
        if payload["stage"]=="Contacted" and not meta.get("contacted_at"):meta["contacted_at"]=iso()
    if "notes" in payload:meta["notes"]=str(payload["notes"])[:2000]
    if "follow_up" in payload:meta["follow_up"]=str(payload["follow_up"])[:20]
    meta["updated_at"]=iso();save_db(data)
    if pid in LIVE_CACHE:LIVE_CACHE[pid].update(meta);return LIVE_CACHE[pid]
    return meta
def export_csv():
    # Export only cache-exempt Place IDs plus our own CRM/config data—not Google Places content.
    rows=load_db()["prospects"].values();stream=io.StringIO();fields=["id","stage","segment","city","follow_up","notes","first_seen","last_seen","contacted_at","updated_at"]
    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
    for row in rows:writer.writerow({k:row.get(k,"") for k in fields})
    return stream.getvalue().encode()
def refresh_background():
    with LOCK:
        if REFRESH["running"]:return False
        REFRESH.update({"running":True,"started":iso(),"finished":None,"error":None,"result":None})
    def work():
        try:result=refresh_prospects();error=None
        except Exception as exc:result=None;error=str(exc)
        with LOCK:REFRESH.update({"running":False,"finished":iso(),"error":error,"result":result})
    threading.Thread(target=work,daemon=True).start();return True
class Handler(BaseHTTPRequestHandler):
    server_version="ProspectCRM/1.0"
    def authorised(self):
        password=os.getenv("DASHBOARD_PASSWORD","")
        if not password:return True
        expected="Basic "+base64.b64encode(f"{os.getenv('DASHBOARD_USER','admin')}:{password}".encode()).decode()
        if self.headers.get("Authorization")==expected:return True
        self.send_response(401);self.send_header("WWW-Authenticate",'Basic realm="Prospect Dashboard"');self.end_headers();return False
    def send_json(self,value,status=200):
        raw=json.dumps(value,ensure_ascii=False).encode();self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def body(self):
        size=min(int(self.headers.get("Content-Length","0") or 0),65536);return json.loads(self.rfile.read(size) or b"{}")
    def do_GET(self):
        if not self.authorised():return
        path=self.path.split("?",1)[0]
        if path=="/":
            raw=HTML_PATH.read_text().replace("__MAPS_KEY__",json.dumps(os.getenv("GOOGLE_MAPS_BROWSER_KEY",""))).encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
        elif path=="/api/prospects":self.send_json(api_prospects())
        elif path=="/api/status":self.send_json({**REFRESH,"places_configured":bool(os.getenv("GOOGLE_PLACES_API_KEY")),"maps_configured":bool(os.getenv("GOOGLE_MAPS_BROWSER_KEY"))})
        elif path=="/api/export.csv":
            raw=export_csv();self.send_response(200);self.send_header("Content-Type","text/csv; charset=utf-8");self.send_header("Content-Disposition",'attachment; filename="prospects.csv"');self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
        else:self.send_json({"error":"Not found"},404)
    def do_POST(self):
        if not self.authorised():return
        path=self.path.split("?",1)[0]
        try:
            if path=="/api/refresh":self.send_json({"started":refresh_background()},202)
            elif path.startswith("/api/contact/"):self.send_json(place_contact(unquote(path.removeprefix("/api/contact/"))))
            else:self.send_json({"error":"Not found"},404)
        except Exception as exc:self.send_json({"error":str(exc)},400)
    def do_PATCH(self):
        if not self.authorised():return
        path=self.path.split("?",1)[0]
        try:
            if path.startswith("/api/prospect/"):self.send_json(update_prospect(unquote(path.removeprefix("/api/prospect/")),self.body()))
            else:self.send_json({"error":"Not found"},404)
        except KeyError:self.send_json({"error":"Prospect not found"},404)
        except Exception as exc:self.send_json({"error":str(exc)},400)
    def log_message(self,fmt,*args):print(f"[dashboard] {self.address_string()} {fmt%args}")
def serve(host,port):
    print(f"Prospect dashboard: http://{host}:{port}");ThreadingHTTPServer((host,port),Handler).serve_forever()
def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("refresh");sub.add_parser("summary");web=sub.add_parser("serve");web.add_argument("--host",default="0.0.0.0");web.add_argument("--port",type=int,default=int(os.getenv("PORT","8000")));args=parser.parse_args()
    if args.command=="refresh":print(json.dumps(refresh_prospects(),indent=2))
    elif args.command=="summary":print(json.dumps(api_prospects(),indent=2))
    else:serve(args.host,args.port)
if __name__=="__main__":main()
