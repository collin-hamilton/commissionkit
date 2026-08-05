import tempfile
import unittest
from pathlib import Path

from commissionkit.session import CheckoutSession, Point, SimulatedAdapter, load_points


class SessionTests(unittest.TestCase):
    def test_input_result_compares_both_states(self) -> None:
        point = Point("PE101", "input", "photoeye")
        session = CheckoutSession([point], operator="cjh", adapter=SimulatedAdapter())
        self.assertEqual("pass", session.observe_input("PE101", False, True).status)
        self.assertTrue(session.summary()["complete"])

    def test_output_requires_exact_confirmation(self) -> None:
        point = Point("SOL101", "output", "reject solenoid")
        adapter = SimulatedAdapter()
        session = CheckoutSession([point], operator="cjh", adapter=adapter, allow_output_writes=True)
        with self.assertRaises(PermissionError):
            session.exercise_output("SOL101", confirmation="WRONG")
        result = session.exercise_output("SOL101", confirmation=session.confirmation_token)
        self.assertEqual("pass", result.status)
        self.assertEqual(("SOL101", False), adapter.writes[-1])

    def test_safety_output_is_never_written(self) -> None:
        point = Point("K1", "output", "safety contactor", safety_related=True)
        adapter = SimulatedAdapter()
        session = CheckoutSession([point], operator="cjh", adapter=adapter, allow_output_writes=True)
        with self.assertRaises(PermissionError):
            session.exercise_output("K1", confirmation=session.confirmation_token)
        self.assertEqual([], adapter.writes)

    def test_csv_rejects_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "io.csv"
            path.write_text("tag,direction\nA,input\nA,input\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_points(path)


if __name__ == "__main__":
    unittest.main()

