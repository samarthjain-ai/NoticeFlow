import tempfile
import unittest
from pathlib import Path

from noticeflow.core.models import Action, ActionStatus, Notice
from noticeflow.services.storage_service import StorageService


class StorageServiceTests(unittest.TestCase):
    def test_notice_and_action_survive_a_new_service_instance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "noticeflow.db"
            notice = Notice(
                title="Scholarship",
                summary="Submit the scholarship form.",
                actions=[Action(title="Submit form", reasoning="Required by the notice.")],
            )
            StorageService(database_path).save_notice(notice)

            restored = StorageService(database_path).get_notice(notice.id)

            self.assertIsNotNone(restored)
            self.assertEqual(restored.actions[0].title, "Submit form")

    def test_action_status_update_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "noticeflow.db"
            notice = Notice(
                title="Assignment",
                summary="Submit the assignment.",
                actions=[Action(title="Submit assignment", reasoning="Required by the notice.")],
            )
            storage = StorageService(database_path)
            storage.save_notice(notice)

            updated = storage.update_action_status(notice.actions[0].id, ActionStatus.COMPLETED)

            self.assertEqual(updated.actions[0].status, ActionStatus.COMPLETED)
            restored = StorageService(database_path).get_notice(notice.id)
            self.assertEqual(restored.actions[0].status, ActionStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()