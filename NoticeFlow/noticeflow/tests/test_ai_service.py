import unittest
from types import SimpleNamespace
from unittest.mock import patch

from datetime import date

from pydantic import ValidationError

from noticeflow.core.ai_service import (
    AIServiceError,
    DemoAIService,
    ExtractionResult,
    OpenAIService,
    build_ai_service,
    materialize_notice,
    prepare_notice_text,
)
from noticeflow.core.models import Confidence, ImportantDate, NoticeCategory, Requirement, SourceEvidence


class DemoAIServiceTests(unittest.TestCase):
    def test_demo_service_extracts_action_and_uncertain_deadline(self) -> None:
        notice = DemoAIService().analyze_notice(
            "University Hackathon\nEligibility: second year students.\nSubmit your abstract by Friday.\nRegister using the form."
        )

        self.assertEqual(notice.category, NoticeCategory.HACKATHON)
        self.assertEqual(notice.deadlines[0].confidence, Confidence.UNCERTAIN)
        self.assertEqual(len(notice.actions), 2)
        self.assertTrue(notice.source_evidence)
        self.assertIn("second year", notice.eligibility)

    def test_demo_scenarios_produce_actionable_notices(self) -> None:
        from noticeflow.core.demo_scenarios import DEMO_SCENARIOS

        for scenario in DEMO_SCENARIOS:
            with self.subTest(scenario=scenario.name):
                notice = DemoAIService().analyze_notice(scenario.notice_text)

                self.assertIn("Fictional", scenario.name)
                self.assertIn("FICTIONAL DEMO NOTICE", scenario.notice_text)
                self.assertTrue(notice.title)
                self.assertTrue(notice.actions)
                self.assertTrue(notice.deadlines)
                self.assertTrue(notice.source_evidence)

    def test_hackathon_demo_is_the_strongest_risk_story(self) -> None:
        from noticeflow.core.demo_scenarios import DEMO_SCENARIOS

        notice = DemoAIService().analyze_notice(DEMO_SCENARIOS[0].notice_text)

        self.assertEqual(notice.priority, "high")
        self.assertEqual(notice.risks[0].severity, "high")
        self.assertGreaterEqual(len(notice.actions), 3)
        self.assertIsNotNone(notice.eligibility)
        self.assertEqual(notice.deadlines[0].label, "Registration deadline")
        self.assertEqual(notice.deadlines[1].label, "Submission deadline")

    def test_demo_service_rejects_empty_text(self) -> None:
        with self.assertRaises(ValueError):
            DemoAIService().analyze_notice("  ")

    def test_demo_service_normalizes_only_year_bearing_dates(self) -> None:
        notice = DemoAIService().analyze_notice(
            "Assignment submission\nSubmit by September 14, 2026.\nExam on October 2."
        )

        self.assertEqual(notice.deadlines[0].normalized_date, date(2026, 9, 14))
        self.assertEqual(notice.deadlines[0].label, "Submission deadline")
        self.assertIsNone(notice.deadlines[1].normalized_date)
        self.assertEqual(notice.deadlines[1].confidence, Confidence.APPROXIMATE)

    def test_structured_result_materializes_deterministic_actions_and_priority(self) -> None:
        extraction = ExtractionResult(
            title="Power BI submission",
            category=NoticeCategory.ASSIGNMENT,
            summary="Submit the project before the deadline.",
            deadlines=[
                ImportantDate(
                    label="Submission deadline",
                    original_text="September 14, 2026",
                    normalized_date=date(2026, 9, 14),
                    source_evidence=SourceEvidence(
                        quote="Submit by September 14, 2026",
                        field_name="deadlines",
                    ),
                )
            ],
            requirements=[
                Requirement(
                    title="Upload the completed Power BI project",
                    source_evidence=SourceEvidence(
                        quote="Upload the completed Power BI project",
                        field_name="requirements",
                    ),
                )
            ],
            source_evidence=[
                SourceEvidence(quote="Submit by September 14, 2026", field_name="deadlines"),
                SourceEvidence(quote="Not present in source", field_name="organizer"),
            ],
        )

        notice = materialize_notice(
            extraction,
            "Submit by September 14, 2026. Upload the completed Power BI project.",
        )

        self.assertEqual(notice.priority.value, "urgent")
        self.assertEqual(notice.actions[0].title, "Upload the completed Power BI project")
        self.assertEqual(len(notice.source_evidence), 2)
        self.assertEqual(notice.deadlines[0].source_evidence.quote, "Submit by September 14, 2026")

    def test_unknown_structured_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ExtractionResult(title="Notice", summary="Summary", fabricated_fact="no")

    def test_factory_uses_demo_mode_without_credentials(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            service, mode = build_ai_service()

        self.assertIsInstance(service, DemoAIService)
        self.assertEqual(mode, "DEMO MODE")

    def test_openai_service_requires_a_key(self) -> None:
        with self.assertRaisesRegex(AIServiceError, "OPENAI_API_KEY"):
            OpenAIService("")

    def test_forced_openai_without_a_key_keeps_app_available(self) -> None:
        with patch.dict("os.environ", {"AI_PROVIDER": "openai", "OPENAI_API_KEY": ""}, clear=True):
            service, mode = build_ai_service()

        self.assertEqual(mode, "AI MODE · unavailable")
        with self.assertRaisesRegex(AIServiceError, "OPENAI_API_KEY"):
            service.analyze_notice("A notice")

    def test_openai_service_materializes_mocked_structured_response(self) -> None:
        parsed = ExtractionResult(
            title="Scholarship application",
            summary="Apply for the scholarship.",
            requirements=[Requirement(title="Submit the application")],
        )
        fake_client = SimpleNamespace(
            beta=SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(
                        parse=lambda **_: SimpleNamespace(
                            choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))]
                        )
                    )
                )
            )
        )
        service = OpenAIService.__new__(OpenAIService)
        service.client = fake_client
        service.model = "test-model"

        notice = service.analyze_notice("Submit the application.")

        self.assertEqual(notice.title, "Scholarship application")
        self.assertEqual(notice.actions[0].title, "Submit the application")

    def test_openai_service_hides_provider_failure_details(self) -> None:
        service = OpenAIService.__new__(OpenAIService)
        service.model = "test-model"
        service.client = SimpleNamespace(
            beta=SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(
                        parse=lambda **_: (_ for _ in ()).throw(RuntimeError("secret provider detail"))
                    )
                )
            )
        )

        with self.assertRaisesRegex(AIServiceError, "could not reach") as context:
            service.analyze_notice("A notice")

        self.assertNotIn("secret provider detail", str(context.exception))

    def test_long_input_is_normalized_and_bounded(self) -> None:
        prepared = prepare_notice_text("  deadline   Friday  \n" + ("details " * 100), max_characters=80)

        self.assertLessEqual(len(prepared), 80)
        self.assertIn("deadline Friday", prepared)


if __name__ == "__main__":
    unittest.main()