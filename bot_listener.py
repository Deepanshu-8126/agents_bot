#!/usr/bin/env python3
"""Interactive Telegram Bot Listener.
Allows users/friends to chat with the bot and ask:
- '1 hafte pehle ki jobs batao' or '/jobs' -> Fresh 7-day jobs & internships (Internshala, Unstop, ATS)
- '/clients' or 'client leads' -> Freelance leads from Freelancer, Reddit, Discord
- '/local' or 'local jobs' -> Uttarakhand/SIDCUL jobs
- Or any skill keyword like 'video editing', 'python', 'excel', 'data analyst'
"""
import html, json, os, re, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Load .env
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

HTTP = httpx.Client(http2=True, timeout=35)
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# In-memory cache to answer instantly (< 1 sec)
CACHE = {
    "jobs": {"data": [], "timestamp": 0},
    "clients": {"data": [], "timestamp": 0},
    "local": {"data": [], "timestamp": 0},
}
CACHE_TTL = 1800  # 30 minutes


def send_reply(chat_id, text):
    """Send Telegram message chunked properly."""
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        try:
            HTTP.post(
                f"{API_BASE}/sendMessage",
                json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"},
            )
        except Exception as exc:
            # Fallback to plain text if Markdown parsing fails
            try:
                HTTP.post(
                    f"{API_BASE}/sendMessage",
                    json={"chat_id": chat_id, "text": chunk},
                )
            except Exception as e:
                print(f"[warn] Failed to send message to {chat_id}: {e}")


def get_fresh_jobs(force_refresh=False):
    """Fetch jobs from past 7 days (Internshala, Unstop, ATS, Accenture)."""
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

    best = {}
    for job in all_jobs:
        if jobs_core.qualifies(job):
            key = jobs_core.identity(job)
            if key not in best or jobs_core.when(job["posted"]) > jobs_core.when(best[key]["posted"]):
                best[key] = job

    results = list(best.values())
    results.sort(key=lambda x: jobs_core.when(x["posted"]) or jobs_core.NOW, reverse=True)
    CACHE["jobs"]["data"] = results
    CACHE["jobs"]["timestamp"] = now_ts
    return results


def get_fresh_clients(force_refresh=False):
    """Fetch freelance client leads."""
    now_ts = time.time()
    if not force_refresh and CACHE["clients"]["data"] and (now_ts - CACHE["clients"]["timestamp"] < CACHE_TTL):
        return CACHE["clients"]["data"]

    leads = (
        clients_core.freelancer_leads()
        + clients_core.reddit_leads()
        + clients_core.discord_leads()
        + clients_core.fetch_remote_jobs()
    )
    best = {}
    for row in leads:
        if row["id"] not in best or row["score"] > best[row["id"]]["score"]:
            best[row["id"]] = row

    results = list(best.values())
    results.sort(key=lambda x: -x["score"])
    CACHE["clients"]["data"] = results
    CACHE["clients"]["timestamp"] = now_ts
    return results


def handle_message(msg):
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    from_user = msg.get("from", {})
    first_name = from_user.get("first_name", "Friend")
    raw_text = msg.get("text", "").strip()
    text = raw_text.lower()

    if not chat_id or not raw_text:
        return

    print(f"[msg] From {first_name} ({chat_id}): {raw_text}")

    # 1. Greetings / Start / Help
    if text in ("/start", "/help", "hi", "hello", "hey", "help", "start"):
        reply = (
            f"👋 *Namaste {first_name}! Main Job & Freelance Bot hoon.*\n\n"
            f"Aap mujhse ye sab poochh sakte ho:\n\n"
            f"📌 *1 Hafte Ki Jobs:*\n"
            f"• Type: `1 hafte pehle ki jobs batao` ya `/jobs`\n"
            f"_(Internshala, Unstop aur Top Companies ki pichhle 7 dino ki fresh jobs/internships)_\n\n"
            f"💼 *Freelance Client Leads:*\n"
            f"• Type: `client leads` ya `/clients`\n"
            f"_(Freelancer, Reddit, Discord ke active projects aur direct client briefs)_\n\n"
            f"🏭 *Local Uttarakhand/SIDCUL Jobs:*\n"
            f"• Type: `local jobs` ya `/local`\n\n"
            f"🔍 *Specific Skill Search:*\n"
            f"• Kisi bhi skill ka naam bhejo, jaise: `python`, `data analyst`, `video editing`, `web dev`, `excel`\n"
        )
        send_reply(chat_id, reply)
        return

    # 2. User asks for 1 week jobs
    if re.search(r"\b(?:1\s*hafte|ek\s*hafte|hafte|week|pichhle|jobs?|naukri|internship)\b", text) or text == "/jobs":
        send_reply(chat_id, "⏳ *Pichhle 1 hafte ki fresh jobs & internships nikaal raha hoon...* (Internshala, Unstop & Top Companies)")
        jobs = get_fresh_jobs()
        if not jobs:
            send_reply(chat_id, "ℹ️ Abhi pichhle 1 hafte me koi nayi open opportunity nahi mili. Thodi der baad try karein!")
            return

        top_jobs = jobs[:12]
        header = f"🚀 *Pichhle 1 Hafte Ki Top Fresh Jobs & Internships* ({len(top_jobs)} matches):\n"
        blocks = []
        for i, j in enumerate(top_jobs, 1):
            posted = jobs_core.when(j["posted"]).astimezone(jobs_core.TZ).strftime("%d %b") if j.get("posted") else "Recent"
            loc = "🏠 Remote / WFH" if j.get("remote") else f"📍 {j.get('location', 'India')[:30]}"
            blocks.append(
                f"\n*{i}. {j['title'][:55]}*\n"
                f"   🏢 {j['company']} | {loc}\n"
                f"   🕒 {posted} | Source: {j['source']}\n"
                f"   🔗 {j['url']}"
            )
        send_reply(chat_id, header + "\n".join(blocks))
        return

    # 3. User asks for Client Leads / Freelance
    if re.search(r"\b(?:client|freelance|lead|gigs?|project|kaam)\b", text) or text == "/clients":
        send_reply(chat_id, "💼 *Fresh freelance client requirements fetch kar raha hoon...* (Freelancer + Reddit + Remote)")
        clients = get_fresh_clients()
        if not clients:
            send_reply(chat_id, "ℹ️ Abhi koi fresh client lead nahi mili. Kuch der baad check karein!")
            return

        top_clients = clients[:6]
        header = f"💼 *Latest Genuine Client Requirements* ({len(top_clients)} leads):\n"
        blocks = []
        for i, c in enumerate(top_clients, 1):
            card = clients_core.format_client_message(c)
            if card:
                blocks.append(card)
        
        send_reply(chat_id, header)
        for b in blocks:
            send_reply(chat_id, b)
        return

    # 4. User asks for Local Jobs
    if re.search(r"\b(?:local|uttarakhand|sidcul|kumaon|rudrapur|haldwani|pantnagar)\b", text) or text == "/local":
        send_reply(chat_id, "🏭 *Local Kumaon / SIDCUL jobs check kar raha hoon...*")
        try:
            local_jobs = local_core.successfactors_jobs() + local_core.britannia_jobs() + local_core.nestle_jobs()
            if not local_jobs:
                send_reply(chat_id, "ℹ️ Uttarakhand / SIDCUL me abhi koi nayi entry-level vacancy nahi hai.")
                return
            batches = local_core.messages(local_jobs[:8])
            for b in batches:
                send_reply(chat_id, b)
        except Exception as e:
            send_reply(chat_id, f"⚠️ Local jobs fetch karne me issue aaya: {e}")
        return

    # 5. Specific Skill Search (e.g. "python", "video editing", "excel", "data")
    words = [w for w in re.split(r"\s+", text) if len(w) > 2]
    if words:
        jobs = get_fresh_jobs()
        matched = []
        pattern = re.compile(rf"\b(?:{'|'.join(re.escape(w) for w in words)})\b", re.I)
        for j in jobs:
            searchable = f"{j['title']} {j.get('desc', '')} {j.get('skills', '')}"
            if pattern.search(searchable):
                matched.append(j)

        if matched:
            top_matched = matched[:8]
            header = f"🎯 *'{raw_text}' se related {len(top_matched)} jobs mili hain:*\n"
            blocks = []
            for i, j in enumerate(top_matched, 1):
                posted = jobs_core.when(j["posted"]).astimezone(jobs_core.TZ).strftime("%d %b") if j.get("posted") else "Recent"
                loc = "🏠 Remote" if j.get("remote") else f"📍 {j.get('location', 'India')[:30]}"
                blocks.append(
                    f"\n*{i}. {j['title'][:55]}*\n"
                    f"   🏢 {j['company']} | {loc}\n"
                    f"   🕒 {posted} | Source: {j['source']}\n"
                    f"   🔗 {j['url']}"
                )
            send_reply(chat_id, header + "\n".join(blocks))
            return

    # 6. Fallback default reply
    send_reply(
        chat_id,
        "🤖 *Command samajh nahi aayi!*\n\n"
        "Aap inme se kuch bhi likhkar bhej sakte ho:\n"
        "• `1 hafte pehle ki jobs batao` ya `/jobs`\n"
        "• `client leads` ya `/clients`\n"
        "• `local jobs` ya `/local`\n"
        "• Ya koi skill likho, jaise: `python`, `data analyst`, `video editing`"
    )


def run_listener():
    """Main long-polling loop."""
    print("=" * 60)
    print("🤖 Interactive Telegram Bot Listener Running...")
    print(f"📡 Bot connected to Telegram API: {API_BASE[:35]}***")
    print("Listening for messages... (Press Ctrl+C to stop)")
    print("=" * 60)

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
                print("[warn] Another instance is polling. Waiting 10s...")
                time.sleep(10)
            else:
                time.sleep(2)
        except httpx.ReadTimeout:
            continue
        except Exception as exc:
            print(f"[error] Polling loop exception: {exc}")
            time.sleep(3)


if __name__ == "__main__":
    run_listener()
