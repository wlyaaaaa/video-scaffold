"""版式一览包含当前登记的每一种元素与卡片主体。"""
import json
import unittest
from pathlib import Path

from pipeline import boards, board_bodies
class AtlasTests(unittest.TestCase):
    def test_registered_names_are_present(self):
        spec = json.loads((Path(__file__).parents[1] / "templates/pages/atlas.json").read_text(encoding="utf-8"))
        def objects(value):
            if isinstance(value, dict):
                yield value
                yield from (item for child in value.values() for item in objects(child))
            elif isinstance(value, list):
                yield from (item for child in value for item in objects(child))
        rows = list(objects(spec))
        self.assertTrue(set(boards.KINDS) <= {key for row in rows for key in row})
        self.assertTrue(set(board_bodies.BODIES) <= {row.get("kind") for row in rows})
