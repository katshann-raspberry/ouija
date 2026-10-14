import unittest
from unittest.mock import patch

from ouijacnc.controller import Controller


class TextMotionTests(unittest.TestCase):
    def setUp(self):
        self.controller = Controller()
        self.controller.dry_run = True
        config_patch = patch("ouijacnc.controller.load_config", return_value=self.controller.config)
        config_patch.start()
        self.addCleanup(config_patch.stop)

    def commands(self, text):
        self.controller._run_text(text)
        return [line.split("> ", 1)[1] for line in self.controller.log if "> " in line]

    def test_upper_row_repeat_moves_up_and_back(self):
        self.assertEqual(self.commands("ll"), [
            "G0 X245.000 Y158.000", "G0 X245.000 Y178.000",
            "G0 X245.000 Y158.000", "G0 X140.000 Y0.000",
        ])

    def test_lower_row_repeat_moves_down_and_back(self):
        self.assertEqual(self.commands("OO"), [
            "G0 X0.000 Y100.000", "G0 X0.000 Y80.000",
            "G0 X0.000 Y100.000", "G0 X140.000 Y0.000",
        ])

    def test_triple_letter_has_two_gestures(self):
        commands = self.commands("LLL")
        self.assertEqual(commands.count("G0 X245.000 Y178.000"), 2)
        self.assertEqual(commands.count("G0 X245.000 Y158.000"), 3)

    def test_word_boundary_pauses_without_repeat_gesture(self):
        self.assertEqual(self.commands("O \n O"), [
            "G0 X0.000 Y100.000", "G4 P1.500",
            "G0 X0.000 Y100.000", "G0 X140.000 Y0.000",
        ])

    def test_goodbye_occurs_only_once_after_message(self):
        commands = self.commands("HELLO WORLD")
        self.assertEqual(commands.count("G0 X140.000 Y0.000"), 1)
        self.assertEqual(commands[-1], "G0 X140.000 Y0.000")
        self.assertEqual(commands.count("G4 P1.500"), 1)

    def test_empty_message_does_not_move(self):
        self.assertEqual(self.commands(" \n "), [])

    def test_numbers_keep_plain_moves(self):
        self.assertEqual(self.commands("00"), [
            "G0 X60.000 Y47.000", "G0 X60.000 Y47.000", "G0 X140.000 Y0.000",
        ])

    def test_distance_can_be_changed_or_disabled(self):
        gesture = self.controller.config.settings["gcode"]["repeat_gesture"]
        gesture["distance_mm"] = 30
        self.assertIn("G0 X245.000 Y188.000", self.commands("LL"))
        self.controller.log.clear()
        gesture["distance_mm"] = 0
        self.assertEqual(len(self.commands("LL")), 3)

    def test_out_of_bounds_late_gesture_fails_before_any_motion(self):
        self.controller.config.settings["safety"]["bounds"]["y_max"] = 170
        with self.assertRaisesRegex(ValueError, "repeat excursion"):
            self.commands("A HH")
        self.assertEqual(list(self.controller.log), [])

    def test_invalid_distances_fail_before_motion(self):
        for distance in (-1, float("nan"), float("inf")):
            with self.subTest(distance=distance):
                self.controller.config.settings["gcode"]["repeat_gesture"]["distance_mm"] = distance
                with self.assertRaises(ValueError):
                    self.commands("LL")
                self.assertEqual(list(self.controller.log), [])

    def test_every_letter_repeat_fits_current_bounds(self):
        for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            with self.subTest(char=char):
                self.controller.log.clear()
                self.assertEqual(len(self.commands(char * 2)), 4)


if __name__ == "__main__":
    unittest.main()
