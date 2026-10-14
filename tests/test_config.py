import unittest

from ouijacnc.config import Coordinate, _coordinates, load_config


class MappingTests(unittest.TestCase):
    def test_real_mapping(self):
        config = load_config()
        self.assertEqual(len(config.characters), 36)
        self.assertEqual(config.characters["A"], Coordinate(5, 135))
        self.assertEqual(config.positions["goodbye"], Coordinate(140, 0))
        self.assertEqual(config.characters["B"], Coordinate(30.2, 143.7))
        self.assertNotIn("start", config.positions)

    def test_numeric_and_string_coordinates(self):
        self.assertEqual(
            _coordinates({"a": {"x": "0", "y": 12}}, "letters", str.upper),
            {"A": Coordinate(0, 12)},
        )

    def test_unmeasured_is_skipped(self):
        self.assertEqual(
            _coordinates({"B": {"x": "", "y": ""}}, "letters", str.upper), {},
        )

    def test_invalid_coordinates_are_rejected(self):
        for value in ({"x": "", "y": "1"}, {"x": "NaN", "y": "1"},
                      {"x": "1", "y": "Infinity"}, {"x": "bad", "y": "1"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _coordinates({"A": value}, "letters", str.upper)


if __name__ == "__main__":
    unittest.main()
