import unittest
import os
import tempfile
from app.database.db import init_db
from app.database.repository import JobRepository
from app.bot.commands import BotCommandHandler

class TestTelegramCommands(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.temp_db_path)
        self.repo = JobRepository(self.temp_db_path)
        # Register a test source so /sources test passes
        self.repo.register_source("naukri", "Naukri India")
        self.repo.register_source("internshala", "Internshala Freshers")
        self.handler = BotCommandHandler(self.repo)
        self.chat_id = "user_cmd_test"

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_start_and_help(self):
        response_start = self.handler.handle_command(self.chat_id, "/start")
        self.assertIn("Personal AI Job Hunter Agent", response_start)

        response_help = self.handler.handle_command(self.chat_id, "/help")
        self.assertIn("Available Commands", response_help)
        self.assertIn("/setlocation", response_help)
        self.assertIn("/radius", response_help)

    def test_location_and_radius_commands(self):
        # Default location check
        loc_resp = self.handler.handle_command(self.chat_id, "/location")
        self.assertIn("Haldwani", loc_resp)

        # Set location
        set_loc_resp = self.handler.handle_command(self.chat_id, "/setlocation Noida")
        self.assertIn("Location updated to:* Noida", set_loc_resp)

        # Verify location updated
        loc_check = self.handler.handle_command(self.chat_id, "/location")
        self.assertIn("Noida", loc_check)

        # Radius command without args
        rad_resp = self.handler.handle_command(self.chat_id, "/radius")
        self.assertIn("Current Search Radius:* 100 km", rad_resp)

        # Update radius
        rad_set_resp = self.handler.handle_command(self.chat_id, "/radius 150")
        self.assertIn("Search radius updated to:* 150 km", rad_set_resp)

        # Invalid radius input
        rad_err = self.handler.handle_command(self.chat_id, "/radius abc")
        self.assertIn("Please specify a valid positive number for radius in km", rad_err)

    def test_keywords_commands(self):
        # Add keyword
        add_kw_resp = self.handler.handle_command(self.chat_id, "/addkeyword fastapi")
        self.assertIn("Keyword added: `fastapi`", add_kw_resp)

        # Check in list
        kw_list = self.handler.handle_command(self.chat_id, "/keywords")
        self.assertIn("fastapi", kw_list)

        # Remove keyword
        rem_kw_resp = self.handler.handle_command(self.chat_id, "/removekeyword fastapi")
        self.assertIn("Keyword removed: `fastapi`", rem_kw_resp)

    def test_exclusions_commands(self):
        # Check initial exclusions
        ex_resp = self.handler.handle_command(self.chat_id, "/excludes")
        self.assertIn("Exclusion Filters", ex_resp)

        # Add exclusion
        add_ex_resp = self.handler.handle_command(self.chat_id, "/addexclude telecaller")
        self.assertIn("Exclusion added: `telecaller`", add_ex_resp)

        # Check in list
        ex_list = self.handler.handle_command(self.chat_id, "/exclude")
        self.assertIn("telecaller", ex_list)

        # Remove exclusion
        rem_ex_resp = self.handler.handle_command(self.chat_id, "/removeexclude telecaller")
        self.assertIn("Exclusion removed: `telecaller`", rem_ex_resp)

    def test_sources_command(self):
        sources_resp = self.handler.handle_command(self.chat_id, "/sources")
        self.assertIn("Registered Job Source Adapters", sources_resp)
        self.assertIn("Naukri India", sources_resp)
        self.assertIn("Internshala Freshers", sources_resp)

if __name__ == "__main__":
    unittest.main()
