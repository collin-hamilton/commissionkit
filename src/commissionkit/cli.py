from __future__ import annotations

import argparse
from pathlib import Path

from .session import CheckoutSession, SimulatedAdapter, load_points


def main() -> None:
    parser = argparse.ArgumentParser(description="run a guided I/O checkout")
    parser.add_argument("io_list", nargs="?", default="examples/io-list.csv")
    parser.add_argument("--operator", default="demo-operator")
    parser.add_argument("--report", default="commissionkit-report.html")
    args = parser.parse_args()
    points = load_points(args.io_list)
    adapter = SimulatedAdapter()
    session = CheckoutSession(points, operator=args.operator, adapter=adapter, allow_output_writes=True)
    for point in points:
        if point.direction == "input":
            session.observe_input(point.tag, point.off_value, point.on_value, "simulated field observation")
        elif point.safety_related:
            session.skip(point.tag, "safety-related point requires the approved validation procedure")
        else:
            session.exercise_output(point.tag, confirmation=session.confirmation_token, note="simulated loopback")
    target = Path(args.report)
    target.write_text(session.report_html(), encoding="utf-8")
    print(f"report written: {target.resolve()}")
    print(session.summary())


if __name__ == "__main__":
    main()

