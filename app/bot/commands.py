import re
from typing import Tuple, Optional
from app.database.repository import JobRepository
from app.location.distance import get_coordinates, normalize_city_name

class BotCommandHandler:
    def __init__(self, repo: JobRepository = None):
        self.repo = repo or JobRepository()

    def handle_command(self, chat_id: str, raw_text: str) -> Optional[str]:
        """Parse and execute Telegram command. Returns reply text or None if not a command."""
        text = raw_text.strip()
        if not text.startswith("/") and not any(text.lower().startswith(p) for p in ("set location", "add keyword", "my keywords")):
            return None

        lower = text.lower()

        # 1. /start & /help
        if lower in ("/start", "/help"):
            pref = self.repo.get_user_preference(chat_id)
            kws = self.repo.get_keywords(chat_id)
            kws_str = ", ".join(kws) if kws else "None (matches all fresh jobs)"
            return (
                "🎯 *Personal AI Job Hunter Agent*\n\n"
                "I actively hunt jobs across Naukri, Indeed, Internshala, Unstop, Company ATS & more.\n\n"
                f"📍 *Your Location:* {pref['city']} (Radius: {round(pref['radius_km'])} km)\n"
                f"🔍 *Your Keywords:* {kws_str}\n\n"
                "📌 *Available Commands:*\n"
                "• `/jobs` — Hunt for jobs right now matching your preferences\n"
                "• `/location` — View current location & search radius\n"
                "• `/setlocation <city>` — Change your city (e.g. `/setlocation Haldwani`)\n"
                "• `/radius <km>` — Set distance radius (e.g. `/radius 150`)\n"
                "• `/keywords` — View your active search keywords\n"
                "• `/addkeyword <keyword>` — Add job keyword (e.g. `/addkeyword data analyst`)\n"
                "• `/removekeyword <keyword>` — Remove a keyword\n"
                "• `/excludes` — View negative keywords (e.g. senior, manager)\n"
                "• `/addexclude <keyword>` — Add custom exclusion\n"
                "• `/removeexclude <keyword>` — Remove custom exclusion\n"
                "• `/sources` — View all 10+ connected job platforms\n"
            )

        # 2. Location commands: /location, /setlocation <city>, /radius <km>
        if lower == "/location":
            pref = self.repo.get_user_preference(chat_id)
            coord = get_coordinates(pref["city"])
            coord_str = f"({coord[0]}, {coord[1]})" if coord else "Coordinates pending"
            return (
                f"📍 *Current Location Settings:*\n\n"
                f"• *City:* {pref['city']}\n"
                f"• *Coordinates:* {coord_str}\n"
                f"• *Search Radius:* {round(pref['radius_km'])} km\n\n"
                "To change: `/setlocation <city>` or `/radius <km>`"
            )

        if lower.startswith("/setlocation"):
            city_arg = text[len("/setlocation"):].strip()
            if not city_arg:
                return "⚠️ Please provide a city name. Example:\n`/setlocation Haldwani` or `/setlocation Noida`"
            self.repo.set_user_location(chat_id, city_arg)
            coord = get_coordinates(city_arg)
            dist_note = "Coordinates recognized for exact distance calculation." if coord else "Custom city saved."
            return f"✅ *Location updated to:* {city_arg.title()}\n{dist_note}"

        if lower.startswith("/radius"):
            rad_arg = text[len("/radius"):].strip()
            if not rad_arg:
                pref = self.repo.get_user_preference(chat_id)
                return f"📍 *Current Search Radius:* {round(pref['radius_km'])} km\nTo change: `/radius <km>` (e.g. `/radius 150`)"
            try:
                km = float(re.sub(r"[^\d.]", "", rad_arg))
                if km <= 0:
                    raise ValueError
                self.repo.set_user_radius(chat_id, km)
                return f"✅ *Search radius updated to:* {round(km)} km"
            except Exception:
                return "⚠️ Please specify a valid positive number for radius in km. Example:\n`/radius 100`"

        # 3. Keyword commands: /keywords, /addkeyword <kw>, /removekeyword <kw>
        if lower in ("/keywords", "/mykeywords"):
            kws = self.repo.get_keywords(chat_id)
            if not kws:
                return "ℹ️ *No custom keywords set yet.*\nUse `/addkeyword <keyword>` (e.g. `/addkeyword data analyst`)"
            kws_formatted = "\n".join([f"• `{k}`" for k in kws])
            return f"🔍 *Your Active Job Keywords:*\n\n{kws_formatted}\n\nAdd more: `/addkeyword <keyword>`\nRemove: `/removekeyword <keyword>`"

        if lower.startswith("/addkeyword"):
            kw_arg = text[len("/addkeyword"):].strip()
            if not kw_arg:
                return "⚠️ Please specify a keyword. Example:\n`/addkeyword data analyst`"
            success = self.repo.add_keyword(chat_id, kw_arg)
            return f"✅ Keyword added: `{kw_arg.lower()}`" if success else f"ℹ️ Keyword `{kw_arg.lower()}` already exists."

        if lower.startswith("/removekeyword"):
            kw_arg = text[len("/removekeyword"):].strip()
            if not kw_arg:
                return "⚠️ Please specify keyword to remove. Example:\n`/removekeyword python`"
            removed = self.repo.remove_keyword(chat_id, kw_arg)
            return f"🗑️ Keyword removed: `{kw_arg.lower()}`" if removed else f"⚠️ Keyword `{kw_arg.lower()}` was not found."

        # 4. Exclusion commands: /exclude, /excludes, /addexclude <kw>, /removeexclude <kw>
        if lower in ("/exclude", "/excludes"):
            user_exc = self.repo.get_excludes(chat_id)
            default_str = "senior, manager, lead, principal, director, 10+ years, 5+ years"
            user_str = ", ".join([f"`{e}`" for e in user_exc]) if user_exc else "None"
            return (
                f"🛡️ *Exclusion Filters (Fresher Protected):*\n\n"
                f"• *Default Excluded:* `{default_str}`\n"
                f"• *Custom User Excluded:* {user_str}\n\n"
                "Add custom: `/addexclude <word>`\nRemove custom: `/removeexclude <word>`"
            )

        if lower.startswith(("/addexclude", "/exclude ")):
            prefix = "/addexclude" if lower.startswith("/addexclude") else "/exclude "
            exc_arg = text[len(prefix):].strip()
            if not exc_arg:
                return "⚠️ Please specify exclusion keyword. Example:\n`/addexclude sales`"
            self.repo.add_exclude(chat_id, exc_arg)
            return f"✅ Exclusion added: `{exc_arg.lower()}`"

        if lower.startswith("/removeexclude"):
            exc_arg = text[len("/removeexclude"):].strip()
            if not exc_arg:
                return "⚠️ Please specify exclusion to remove. Example:\n`/removeexclude sales`"
            removed = self.repo.remove_exclude(chat_id, exc_arg)
            return f"🗑️ Exclusion removed: `{exc_arg.lower()}`" if removed else f"⚠️ Exclusion `{exc_arg.lower()}` was not found."

        # 5. Sources command: /sources
        if lower == "/sources":
            sources = self.repo.get_all_sources()
            if not sources:
                return "ℹ️ No sources registered yet."
            lines = ["📡 *Registered Job Source Adapters:*\n"]
            for s in sources:
                status = "🟢 Active" if s["is_enabled"] else "⚪ Inactive"
                last_run = s["last_fetched_at"] or "Pending"
                lines.append(f"• *{s['name']}* ({status}) — Last fetched: {last_run}")
            return "\n".join(lines)

        return None
