#!/usr/bin/env python3
"""Interactive AI Career & Telegram Bot Listener with Resume Memory.
Features:
1. Resume Upload: Users can send a PDF/TXT resume or list their skills.
   - Extracts skills (Python, SQL, Excel, Video Editing, React, AI, etc.)
   - Saves profile permanently in `user_profiles.json` per chat_id.
2. Smart Time Filter: Understands '1 mahine ki', '1 hafte ki', '2 hafte ki', 'aaj ki' jobs.
3. Personalized Recommendations: Matches jobs against the user's saved resume with % score!
4. Skill & Tag search: e.g. 'data analyst', 'video editing', 'internshala', 'unstop'.
5. Freelance client leads: 'client leads', 'freelance projects'.
"""

import html, json, os, re, sys, time, io
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Load .env automatically
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

import httpx
import job_alert as jobs_core
import client_alert as clients_core
import local_alert as local_core

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    print("[error] TELEGRAM_BOT_TOKEN is missing in .env or environment!")

try:
    HTTP = httpx.Client(http2=True, timeout=35)
except Exception:
    HTTP = httpx.Client(timeout=35)
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
FILE_BASE = f"https://api.telegram.org/file/bot{BOT_TOKEN}"

PROFILES_FILE = Path("user_profiles.json")

# In-memory job cache (refreshed every 30 mins)
CACHE = {
    "jobs": {"data": [], "timestamp": 0},
    "clients": {"data": [], "timestamp": 0},
}
CACHE_TTL = 1800

# High-demand skills list for resume parsing
VOCABULARY_SKILLS = [
    # Data & Analytics
    "python", "sql", "mysql", "postgresql", "advanced excel", "excel", "power bi", "tableau",
    "data analysis", "data analytics", "data scientist", "machine learning", "deep learning",
    "pandas", "numpy", "statistics", "business intelligence", "mis", "etl", "bigquery",
    # AI & Automation
    "ai", "artificial intelligence", "prompt engineering", "nlp", "computer vision",
    "llm", "chatgpt", "langchain", "n8n", "make", "zapier", "automation", "api",
    # Development
    "web development", "full stack", "frontend", "backend", "react", "next.js", "javascript",
    "typescript", "node.js", "html", "css", "tailwind", "wordpress", "shopify", "webflow", "framer",
    # Creative & Content
    "video editing", "premiere pro", "after effects", "davinci resolve", "capcut", "reels",
    "graphic design", "photoshop", "illustrator", "canva", "thumbnail design", "ugc", "content creation",
    # Marketing & Ops
    "digital marketing", "seo", "social media", "copywriting", "lead generation"
]


def load_profiles():
    if PROFILES_FILE.is_file():
        try:
            return json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_profile(chat_id, profile):
    profiles = load_profiles()
    profiles[str(chat_id)] = profile
    PROFILES_FILE.write_text(json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8")


def get_profile(chat_id):
    return load_profiles().get(str(chat_id))


def extract_skills_from_text(text):
    """Find known technical and creative skills in raw text."""
    found = []
    low = text.lower()
    for skill in VOCABULARY_SKILLS:
        pattern = rf"\b{re.escape(skill)}\b"
        if re.search(pattern, low):
            found.append(skill.title())
    return sorted(list(set(found)))


def send_reply(chat_id, text):
    """Send Telegram message chunked properly."""
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        try:
            HTTP.post(
                f"{API_BASE}/sendMessage",
                json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"},
            )
        except Exception:
            try:
                HTTP.post(
                    f"{API_BASE}/sendMessage",
                    json={"chat_id": chat_id, "text": chunk},
                )
            except Exception as e:
                print(f"[warn] Failed to send to {chat_id}: {e}")


def get_all_jobs(force_refresh=False):
    """Fetch fresh jobs from Internshala, Unstop, ATS, Accenture, IndiGo."""
    now_ts = time.time()
    if not force_refresh and CACHE["jobs"]["data"] and (now_ts - CACHE["jobs"]["timestamp"] < CACHE_TTL):
        return CACHE["jobs"]["data"]

    all_jobs = (
        jobs_core.ats_jobs()
        + jobs_core.accenture_jobs()
        + jobs_core.indigo_jobs()
        + jobs_core.internshala_jobs()
        + jobs_core.unstop_jobs()
    )

    cutoff_45d = datetime.now(timezone.utc) - timedelta(days=45)
    best = {}
    for job in all_jobs:
        if jobs_core.qualifies(job, cutoff=cutoff_45d):
            key = jobs_core.identity(job)
            if key not in best or jobs_core.when(job["posted"]) > jobs_core.when(best[key]["posted"]):
                best[key] = job

    results = list(best.values())
    results.sort(key=lambda x: jobs_core.when(x["posted"]) or jobs_core.NOW, reverse=True)
    CACHE["jobs"]["data"] = results
    CACHE["jobs"]["timestamp"] = now_ts
    return results


def parse_time_window_hours(text):
    """Extract hours from natural language query (e.g. 1 mahine -> 720h, 1 hafte -> 168h)."""
    low = text.lower()
    if re.search(r"\b(?:1\s*mahine|ek\s*mahine|one\s*month|30\s*din|30\s*days|month)\b", low):
        return 720  # 30 days
    if re.search(r"\b(?:2\s*hafte|do\s*hafte|two\s*weeks?|15\s*din|15\s*days)\b", low):
        return 360  # 15 days
    if re.search(r"\b(?:1\s*hafte|ek\s*hafte|one\s*week|7\s*din|7\s*days|week|hafte)\b", low):
        return 168  # 7 days
    if re.search(r"\b(?:aaj|today|24\s*ghante|24\s*hours)\b", low):
        return 24
    return 168  # Default 7 days


def calculate_match_score(job, user_skills):
    """Calculate match score percentage between job and user skills."""
    if not user_skills:
        return 0, []
    job_blob = f"{job.get('title', '')} {job.get('desc', '')} {job.get('skills', '')}".lower()
    matched = [s for s in user_skills if s.lower() in job_blob]
    score = int((len(matched) / max(len(user_skills[:6]), 1)) * 100)
    score = min(score, 99)
    return score, matched


def handle_resume_document(chat_id, doc, user_name):
    """Download and extract skills from uploaded PDF/document."""
    file_id = doc.get("file_id")
    file_name = doc.get("file_name", "resume.pdf")
    mime = doc.get("mime_type", "")

    send_reply(chat_id, f"📥 *Resume mil gaya:* `{file_name}`\nReading & extracting skills...")

    try:
        # 1. Get file path from Telegram
        info_res = HTTP.get(f"{API_BASE}/getFile", params={"file_id": file_id})
        file_path = info_res.json().get("result", {}).get("file_path")
        if not file_path:
            send_reply(chat_id, "❌ Telegram se file download karne me issue aaya. Dobara bhejo.")
            return

        # 2. Download file content
        file_res = HTTP.get(f"{FILE_BASE}/{file_path}")
        raw_bytes = file_res.content

        extracted_text = ""
        # Try PDF parsing
        if file_name.lower().endswith(".pdf") or "pdf" in mime:
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
                for page in reader.pages:
                    extracted_text += page.extract_text() or ""
            except Exception as e:
                # Fallback simple text extraction
                extracted_text = re.sub(r"[^\x20-\x7E]+", " ", raw_bytes.decode("latin1", errors="ignore"))
        else:
            extracted_text = raw_bytes.decode("utf-8", errors="ignore")

        skills = extract_skills_from_text(extracted_text)

        if not skills:
            # Fallback basic prompt
            send_reply(
                chat_id,
                "⚠️ *Resume read ho gaya lekin koi specific skill detect nahi hui.*\n"
                "Aap apni skills text message me bhej sakte ho, jaise:\n"
                "`My skills: Python, SQL, Excel, Power BI`"
            )
            return

        # Save profile
        profile = {
            "name": user_name,
            "skills": skills,
            "file_name": file_name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        save_profile(chat_id, profile)

        skills_list_str = ", ".join([f"`{s}`" for s in skills])
        confirmation = (
            f"🎉 *Resume Successfully Saved & Trained!*\n\n"
            f"👤 *Candidate:* {user_name}\n"
            f"🛠 *Detected Skills:* {skills_list_str}\n\n"
            f"Ab bot aapke profile ke hisab se exact matching jobs recommend karega!\n\n"
            f"👉 Try karke dekho: Type karo *'mere liye jobs batao'* ya *'1 mahine ki jobs'*!"
        )
        send_reply(chat_id, confirmation)

    except Exception as exc:
        print(f"[error] Resume parsing failed: {exc}")
        send_reply(chat_id, f"⚠️ Resume read karne me error: {exc}. Aap text me bhi skills bhej sakte ho!")


def handle_message(msg):
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    from_user = msg.get("from", {})
    first_name = from_user.get("first_name", "Friend")
    raw_text = msg.get("text", "").strip()
    document = msg.get("document")

    if not chat_id:
        return

    # A. Check if user sent a Resume PDF/file
    if document:
        handle_resume_document(chat_id, document, first_name)
        return

    if not raw_text:
        return

    text = raw_text.lower()
    print(f"[msg] From {first_name} ({chat_id}): {raw_text}")

    # B. Check if user sent their skills in text (e.g. "my skills are...", "resume: ...")
    if re.search(r"\b(?:skills?|resume|bio)\s*[:=]\s*", text) or (len(text) > 40 and any(s in text for s in ("python", "excel", "video editing", "sql", "react"))):
        detected = extract_skills_from_text(raw_text)
        if len(detected) >= 2:
            profile = {
                "name": first_name,
                "skills": detected,
                "file_name": "manual_text",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            save_profile(chat_id, profile)
            skills_str = ", ".join([f"`{s}`" for s in detected])
            send_reply(
                chat_id,
                f"✅ *Skills Saved to Memory!*\n\n"
                f"👤 *Profile:* {first_name}\n"
                f"🛠 *Skills:* {skills_str}\n\n"
                f"Ab aap poocho: *'mere liye jobs batao'* ya *'1 mahine ki jobs'*!"
            )
            return

    # C. Greetings / Help / Menu
    if text in ("/start", "/help", "hi", "hello", "hey", "start"):
        profile = get_profile(chat_id)
        profile_status = f"✅ Saved Skills: {', '.join(profile['skills'][:4])}" if profile else "ℹ️ Resume not uploaded yet (send your PDF to train me!)"

        reply = (
            f"👋 *Namaste {first_name}! Main aapka AI Job & Career Assistant hoon.*\n\n"
            f"📊 *Aapka Status:* {profile_status}\n\n"
            f"🔥 *Aap Mujhse Kya Pooch Sakte Ho:*\n\n"
            f"1️⃣ *Personalized (Aapke Resume Ke Hisab Se):*\n"
            f"• `mere liye jobs batao` ya `/myjobs`\n\n"
            f"2️⃣ *Time-Based Queries:*\n"
            f"• `1 mahine ki jobs batao` (Pichhle 30 din)\n"
            f"• `1 hafte pehle ki jobs batao` ya `/jobs` (Pichhle 7 din)\n\n"
            f"3️⃣ *Specific Role / Skill Search:*\n"
            f"• `data analyst jobs`\n"
            f"• `video editing jobs`\n"
            f"• `python developer`\n\n"
            f"4️⃣ *Resume Upload:*\n"
            f"• Apna **Resume (PDF)** directly is chat me attach karke bhej do — bot automatically memory me save kar lega!\n\n"
            f"5️⃣ *Freelance Client Leads:*\n"
            f"• `client leads` ya `/clients`"
        )
        send_reply(chat_id, reply)
        return

    # D. Personalized Query: "mere liye jobs batao" / "my jobs" / "recommend jobs"
    if re.search(r"\b(?:mere\s*liye|recommend|my\s*jobs|matching\s*jobs|meri\s*profile)\b", text) or text == "/myjobs":
        profile = get_profile(chat_id)
        if not profile or not profile.get("skills"):
            send_reply(
                chat_id,
                "📄 *Pehle apna Resume bhejo!*\n\n"
                "Aap apna Resume (PDF) is chat me attach karke send karo, ya text me likho:\n"
                "`My skills: Python, SQL, Excel, Video Editing`\n\n"
                "Fir bot aapke exact skills ke mutabik jobs recommend karega!"
            )
            return

        send_reply(chat_id, f"🎯 *{profile['name']} aapke resume ({', '.join(profile['skills'][:4])}) se matching jobs filter kar raha hoon...*")
        jobs = get_all_jobs()
        scored_jobs = []
        for j in jobs:
            score, matched_skills = calculate_match_score(j, profile["skills"])
            if score > 0 or any(s.lower() in j["title"].lower() for s in profile["skills"]):
                scored_jobs.append((score, matched_skills, j))

        scored_jobs.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored_jobs[:10]

        if not top_matches:
            send_reply(chat_id, f"ℹ️ Abhi aapki skills ({', '.join(profile['skills'][:3])}) ke direct matches nahi mile. 1 mahine ki jobs check karein!")
            return

        header = f"🌟 *Aapke Resume Ke Hisab Se Best Recommended Jobs ({len(top_matches)} matches):*\n"
        blocks = []
        for i, (score, matched_skills, j) in enumerate(top_matches, 1):
            posted = jobs_core.when(j["posted"]).astimezone(jobs_core.TZ).strftime("%d %b") if j.get("posted") else "Recent"
            loc = "🏠 Remote / WFH" if j.get("remote") else f"📍 {j.get('location', 'India')[:25]}"
            match_badge = f"🎯 *{score}% Match*" if score > 0 else "✨ Skill Match"
            matched_tag = f"Skills: {', '.join(matched_skills[:3])}" if matched_skills else ""
            blocks.append(
                f"\n*{i}. {j['title'][:55]}* ({match_badge})\n"
                f"   🏢 {j['company']} | {loc}\n"
                f"   🕒 {posted} | Source: {j['source']}\n"
                f"   🛠 {matched_tag}\n"
                f"   🔗 {j['url']}"
            )
        send_reply(chat_id, header + "\n".join(blocks))
        return

    # E. Jobs by Timeframe: "1 mahine ki jobs", "1 hafte ki jobs", "jobs"
    if re.search(r"\b(?:jobs?|naukri|internship|vacancy|vacancies)\b", text) or text == "/jobs":
        hours = parse_time_window_hours(text)
        time_label = "1 Mahine (30 Days)" if hours >= 720 else "2 Hafte (15 Days)" if hours >= 360 else "1 Hafte (7 Days)"
        send_reply(chat_id, f"⏳ *Pichhle {time_label} ki fresh jobs & internships nikaal raha hoon...* (Internshala, Unstop, Top Companies)")

        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
        all_jobs = get_all_jobs()

        # Check if user also specified a skill in the query (e.g. "1 mahine ki data analyst jobs")
        filter_skills = [w for w in re.split(r"\s+", text) if len(w) > 2 and w not in ("jobs", "job", "batao", "mahine", "hafte", "pehle", "naukri", "chahiye", "deki", "wali", "fresh", "latest")]

        filtered = []
        for j in all_jobs:
            p_date = jobs_core.when(j.get("posted"))
            if p_date and p_date >= cutoff_dt:
                if filter_skills:
                    j_text = f"{j['title']} {j.get('desc', '')} {j.get('skills', '')}".lower()
                    if any(s in j_text for s in filter_skills):
                        filtered.append(j)
                else:
                    filtered.append(j)

        if not filtered:
            filtered = all_jobs[:10]  # Fallback to latest available

        top_jobs = filtered[:12]
        header = f"🚀 *Pichhle {time_label} Ki Top Opportunities* ({len(top_jobs)} matches):\n"
        blocks = []
        for i, j in enumerate(top_jobs, 1):
            posted = jobs_core.when(j["posted"]).astimezone(jobs_core.TZ).strftime("%d %b") if j.get("posted") else "Recent"
            loc = "🏠 Remote / WFH" if j.get("remote") else f"📍 {j.get('location', 'India')[:25]}"
            blocks.append(
                f"\n*{i}. {j['title'][:55]}*\n"
                f"   🏢 {j['company']} | {loc}\n"
                f"   🕒 {posted} | Source: {j['source']}\n"
                f"   🔗 {j['url']}"
            )
        send_reply(chat_id, header + "\n".join(blocks))
        return

    # F. Freelance Client Leads
    if re.search(r"\b(?:client|freelance|lead|gigs?|project|kaam)\b", text) or text == "/clients":
        send_reply(chat_id, "💼 *Freelance client requirements fetch kar raha hoon...* (Freelancer, Reddit, Discord)")
        clients = (
            clients_core.freelancer_leads()
            + clients_core.reddit_leads()
            + clients_core.discord_leads()
            + clients_core.fetch_remote_jobs()
        )
        if not clients:
            send_reply(chat_id, "ℹ️ Abhi koi fresh client lead nahi mili. Kuch der baad check karein!")
            return

        top_clients = clients[:5]
        header = f"💼 *Latest Genuine Client Requirements* ({len(top_clients)} leads):\n"
        send_reply(chat_id, header)
        for c in top_clients:
            card = clients_core.format_client_message(c)
            if card:
                send_reply(chat_id, card)
        return

    # G. Fallback: Search any keyword in jobs
    words = [w for w in re.split(r"\s+", text) if len(w) > 2]
    if words:
        jobs = get_all_jobs()
        matched = []
        pattern = re.compile(rf"\b(?:{'|'.join(re.escape(w) for w in words)})\b", re.I)
        for j in jobs:
            searchable = f"{j['title']} {j.get('desc', '')} {j.get('skills', '')}"
            if pattern.search(searchable):
                matched.append(j)

        if matched:
            top_matched = matched[:8]
            header = f"🎯 *'{raw_text}' ke mutabik {len(top_matched)} jobs mili hain:*\n"
            blocks = []
            for i, j in enumerate(top_matched, 1):
                posted = jobs_core.when(j["posted"]).astimezone(jobs_core.TZ).strftime("%d %b") if j.get("posted") else "Recent"
                loc = "🏠 Remote" if j.get("remote") else f"📍 {j.get('location', 'India')[:25]}"
                blocks.append(
                    f"\n*{i}. {j['title'][:55]}*\n"
                    f"   🏢 {j['company']} | {loc}\n"
                    f"   🕒 {posted} | Source: {j['source']}\n"
                    f"   🔗 {j['url']}"
                )
            send_reply(chat_id, header + "\n".join(blocks))
            return

    # Broadcast command: User triggers instant channel broadcast
    if text in ("/broadcast", "/send_now", "send alerts now", "broadcast", "channel me bhejo", "bhejo"):
        send_reply(chat_id, "📢 *Channel (@dkx_jobs) me automatic daily alerts bhejna shuru kar raha hoon...*")
        import threading
        threading.Thread(target=run_automatic_daily_alerts, daemon=True).start()
        send_reply(chat_id, "✅ Alerts channel (@dkx_jobs) me dispatch ho rahe hain!")
        return

    send_reply(
        chat_id,
        "🤖 *Command samajh nahi aayi!*\n\n"
        "Aap pooch sakte ho:\n"
        "• `mere liye jobs batao` (Aapke resume ke hisab se)\n"
        "• `1 mahine ki jobs batao`\n"
        "• `1 hafte ki jobs`\n"
        "• `data analyst jobs` ya `video editing`\n"
        "• `/broadcast` (Channel me automatic alert bhejne ke liye)\n"
        "• Ya apna **Resume PDF** attach karke bhej do!"
    )


def run_automatic_daily_alerts():
    """Run full alert pipeline automatically and send to channel/users."""
    print("[auto-alert] ⏰ Starting automatic daily alerts broadcast...")
    try:
        # 1. Local jobs
        print("[auto-alert] Running local alerts...")
        local_core.main()
    except Exception as e:
        print(f"[warn] Local alerts error: {e}")

    try:
        # 2. National jobs (Internshala, Unstop, ATS)
        print("[auto-alert] Running national jobs alert...")
        jobs_core.main()
    except Exception as e:
        print(f"[warn] Jobs alert error: {e}")

    try:
        # 3. Client leads (Freelancer, Reddit, Discord)
        print("[auto-alert] Running client leads alert...")
        clients_core.main()
    except Exception as e:
        print(f"[warn] Client leads error: {e}")

    print("[auto-alert] ✅ Automatic daily alerts broadcast completed!")


def scheduler_loop():
    """Checks every minute to automatically send alerts at scheduled times (e.g. 8:30 AM IST and 6:30 PM IST)."""
    print("⏰ Automatic Alert Scheduler started in background (Times: 8:30 AM IST & 6:30 PM IST)")
    last_sent_slot = None
    while True:
        try:
            # Current time in IST (UTC + 5:30)
            now_ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
            today_str = now_ist.strftime("%Y-%m-%d")
            hour, minute = now_ist.hour, now_ist.minute

            # Morning slot: 8:30 AM IST | Evening slot: 6:30 PM IST
            is_morning = (hour == 8 and minute >= 30 and minute <= 35)
            is_evening = (hour == 18 and minute >= 30 and minute <= 35)

            slot_key = f"{today_str}_{'morning' if is_morning else 'evening'}"
            if (is_morning or is_evening) and last_sent_slot != slot_key:
                last_sent_slot = slot_key
                print(f"[auto-alert] 🔔 Triggering scheduled broadcast for {slot_key}...")
                run_automatic_daily_alerts()

            time.sleep(30)
        except Exception as exc:
            print(f"[warn] Scheduler exception: {exc}")
            time.sleep(60)


def run_listener():
    """Main long-polling loop with exception recovery and automatic scheduler."""
    print("=" * 60)
    print("🤖 Interactive AI Career & Telegram Bot Running...")
    print(f"📡 Connected to Telegram API")
    print("⚡ Modes: 1) Automatic Daily Channel Alerts  2) Interactive User Chat & Resumes")
    print("Listening for messages & resumes... (Press Ctrl+C to stop)")
    print("=" * 60)

    # Start background daily automatic scheduler thread!
    import threading
    threading.Thread(target=scheduler_loop, daemon=True).start()

    offset = None
    while True:
        try:
            params = {"timeout": 25}
            if offset:
                params["offset"] = offset

            resp = HTTP.get(f"{API_BASE}/getUpdates", params=params, timeout=35)
            if resp.status_code == 200:
                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    if "message" in update:
                        handle_message(update["message"])
                    elif "channel_post" in update:
                        handle_message(update["channel_post"])
            elif resp.status_code == 409:
                print("[warn] Conflict with another listener instance. Sleeping 10s...")
                time.sleep(10)
            else:
                time.sleep(2)
        except httpx.ReadTimeout:
            continue
        except Exception as exc:
            print(f"[error] Polling exception: {exc}")
            time.sleep(3)


if __name__ == "__main__":
    run_listener()
