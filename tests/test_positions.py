import unittest
from unittest.mock import patch

from ouijacnc.controller import Controller


class PositionTests(unittest.TestCase):
    def setUp(self):
        self.controller = Controller()
        self.controller.dry_run = True

    def test_buttons_move_once_to_named_coordinates(self):
        for name, expected in (
            ("yes", "G0 X20.000 Y220.000"),
            ("no", "G0 X290.000 Y220.000"),
            ("goodbye", "G0 X140.000 Y0.000"),
        ):
            with self.subTest(name=name):
                self.controller.log.clear()
                self.controller._run_position(name)
                commands = [line.split("> ", 1)[1] for line in self.controller.log if "> " in line]
                self.assertEqual(commands, [expected])

    def test_position_jobs_keep_submission_order(self):
        self.controller.submit_text("HI")
        self.controller.submit_position("Yes")
        self.controller.submit_position("no")
        jobs = [self.controller.jobs.get_nowait() for _ in range(3)]
        self.assertEqual([job.kind for job in jobs], ["text", "position", "position"])
        self.assertEqual([job.position for job in jobs[1:]], ["yes", "no"])

    def test_unknown_and_unmapped_positions_are_rejected(self):
        for name in ("start", "G0 X0 Y0", "missing"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.controller.submit_position(name)
        del self.controller.config.positions["yes"]
        with self.assertRaises(ValueError):
            self.controller.submit_position("yes")
        self.assertTrue(self.controller.jobs.empty())

    def test_routes_queue_positions_and_render_buttons(self):
        with patch.object(Controller, "start"):
            from ouijacnc import web
        with patch.object(web, "controller", self.controller):
            client = web.app.test_client()
            page = client.get("/")
            for name in ("yes", "no", "goodbye"):
                self.assertIn(f'/position/{name}'.encode(), page.data)
                self.assertEqual(client.post(f"/position/{name}").status_code, 302)
                self.assertEqual(self.controller.jobs.get_nowait().position, name)
            self.assertEqual(client.post("/position/unknown").status_code, 400)
            self.assertEqual(client.get("/position/yes").status_code, 405)
            self.assertTrue(self.controller.jobs.empty())


if __name__ == "__main__":
    unittest.main()
