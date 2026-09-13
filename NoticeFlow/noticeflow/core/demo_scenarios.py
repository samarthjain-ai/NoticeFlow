from dataclasses import dataclass


@dataclass(frozen=True)
class DemoScenario:
    name: str
    description: str
    notice_text: str


DEMO_SCENARIOS = (
    DemoScenario(
        name="Fictional Hackathon — Innovation Sprint",
        description="Fictional demo: team registration, eligibility, and submission stages.",
        notice_text=(
            "FICTIONAL DEMO NOTICE — Northbridge University Innovation Sprint 2026\n"
            "The annual student hackathon invites teams to build a working prototype for campus life.\n"
            "Registration closes September 16, 2026 at 11:59 PM.\n"
            "Project submissions close October 2, 2026.\n"
            "Eligibility: currently enrolled second- or third-year students from any branch. Teams must have 2 to 4 members.\n"
            "Register your team.\n"
            "Upload the student ID list.\n"
            "Submit a 2-page project brief as a PDF."
        ),
    ),
    DemoScenario(
        name="Fictional Scholarship — Merit Award",
        description="Fictional demo: application deadline, eligibility, and required documents.",
        notice_text=(
            "FICTIONAL DEMO NOTICE — Northbridge University Merit Scholarship 2026\n"
            "Applications are open for students with demonstrated academic performance and financial need.\n"
            "Applications close September 25, 2026.\n"
            "Eligibility: undergraduate students with a minimum 8.0 CGPA and no active disciplinary action.\n"
            "Complete the online application, upload the latest marksheet, income certificate, and one-page statement."
        ),
    ),
    DemoScenario(
        name="Fictional Assignment — BI Capstone",
        description="Fictional demo: submission format, deadline, and late-submission risk.",
        notice_text=(
            "FICTIONAL DEMO NOTICE — Business Intelligence Capstone Assignment\n"
            "Submit the completed Power BI project by September 16, 2026. Late submissions will not be graded.\n"
            "Upload one .pbix file and a 2-page PDF reflection to the course portal.\n"
            "The project must include data cleaning, three visual insights, and a written conclusion."
        ),
    ),
    DemoScenario(
        name="Fictional Internship — Product Lab",
        description="Fictional demo: eligibility, application deadline, and application materials.",
        notice_text=(
            "FICTIONAL DEMO NOTICE — Campus Product Lab Internship\n"
            "The Product Lab is accepting applications for a six-week student internship.\n"
            "Applications close October 5, 2026.\n"
            "Eligibility: final-year students from Computer Science, Information Systems, or Design.\n"
            "Apply through the careers form and upload a resume, portfolio link, and a short statement of interest."
        ),
    ),
)