import tempfile
import unittest
from pathlib import Path

import kanban


class KanbanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "kanban.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def test_default_columns_are_seeded_once(self):
        kanban.initialize(self.database)
        kanban.initialize(self.database)
        self.assertEqual(len(kanban.board(self.database)["columns"]), 11)

    def test_move_records_history_without_confirmation_state(self):
        board = kanban.board(self.database)
        first, second = board["columns"][:2]
        proposal = kanban.save_proposal(self.database, {
            "column_id": first["id"], "title": "Teste", "priority": "normal"
        })
        moved = kanban.move_proposal(self.database, proposal["id"], second["id"])
        self.assertEqual(moved["column_id"], second["id"])
        self.assertEqual(kanban.history(self.database, proposal["id"])[0]["from_column"], first["name"])

    def test_non_empty_column_cannot_be_deleted(self):
        column = kanban.board(self.database)["columns"][0]
        kanban.save_proposal(self.database, {"column_id": column["id"], "title": "Teste", "priority": "normal"})
        with self.assertRaisesRegex(ValueError, "Mova os cartões"):
            kanban.delete_column(self.database, column["id"])

    def test_duplicate_and_invalid_link_are_rejected(self):
        column = kanban.board(self.database)["columns"][0]
        payload = {"column_id": column["id"], "title": "Teste", "priority": "normal", "notice_number": "1", "uasg": "2"}
        kanban.save_proposal(self.database, payload)
        with self.assertRaisesRegex(ValueError, "Já existe"):
            kanban.save_proposal(self.database, payload)
        with self.assertRaisesRegex(ValueError, "http"):
            kanban.save_proposal(self.database, {"column_id": column["id"], "title": "Outro", "priority": "normal", "source_link": "arquivo.txt"})


if __name__ == "__main__":
    unittest.main()
