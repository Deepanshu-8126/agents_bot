from typing import List
from .base import JobSource
from .ats_source import CompanyATSSource
from .internshala_source import InternshalaSource
from .unstop_source import UnstopSource
from .naukri_source import NaukriSource
from .indeed_source import IndeedSource
from .foundit_source import FounditSource
from .wellfound_source import WellfoundSource
from .glassdoor_source import GlassdoorSource
from .timesjobs_source import TimesJobsSource
from .freshersworld_source import FreshersworldSource
from .linkedin_source import LinkedInSource

def get_registered_sources() -> List[JobSource]:
    """Returns initialized instances of all active job source adapters."""
    return [
        CompanyATSSource(),
        InternshalaSource(),
        UnstopSource(),
        NaukriSource(),
        IndeedSource(),
        FounditSource(),
        WellfoundSource(),
        GlassdoorSource(),
        TimesJobsSource(),
        FreshersworldSource(),
        LinkedInSource(),
    ]
