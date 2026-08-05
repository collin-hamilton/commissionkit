from __future__ import annotations

import csv
import hashlib
import html
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Protocol


@dataclass(frozen=True)
class Point:
    tag: str
    direction: str
    description: str
    off_value: object = False
    on_value: object = True
    safety_related: bool = False

    def __post_init__(self) -> None:
        if self.direction not in {"input", "output"}:
            raise ValueError(f"invalid direction for {self.tag}: {self.direction}")


@dataclass(frozen=True)
class Result:
    tag: str
    direction: str
    status: str
    observed_off: object
    observed_on: object
    operator: str
    recorded_at: str
    note: str = ""


class IOAdapter(Protocol):
    def read(self, tag: str) -> object: ...
    def write(self, tag: str, value: object) -> None: ...


class SimulatedAdapter:
    def __init__(self, values: Mapping[str, object] | None = None) -> None:
        self.values = dict(values or {})
        self.writes: list[tuple[str, object]] = []

    def read(self, tag: str) -> object:
        return self.values.get(tag)

    def write(self, tag: str, value: object) -> None:
        self.values[tag] = value
        self.writes.append((tag, value))


def _parse_value(value: str) -> object:
    value = value.strip()
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def load_points(path: str | Path) -> list[Point]:
    points: list[Point] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            points.append(
                Point(
                    tag=row["tag"].strip(),
                    direction=row["direction"].strip().lower(),
                    description=row.get("description", "").strip(),
                    off_value=_parse_value(row.get("off_value", "false")),
                    on_value=_parse_value(row.get("on_value", "true")),
                    safety_related=row.get("safety_related", "false").strip().lower() == "true",
                )
            )
    if not points:
        raise ValueError("I/O list is empty")
    if len({point.tag for point in points}) != len(points):
        raise ValueError("I/O list contains duplicate tags")
    return points


class CheckoutSession:
    def __init__(
        self,
        points: Iterable[Point],
        *,
        operator: str,
        adapter: IOAdapter,
        allow_output_writes: bool = False,
    ) -> None:
        self.points = {point.tag: point for point in points}
        self.operator = operator.strip()
        if not self.operator:
            raise ValueError("operator is required")
        self.adapter = adapter
        self.allow_output_writes = allow_output_writes
        material = "|".join(sorted(self.points)) + ":" + self.operator
        self.confirmation_token = hashlib.sha256(material.encode()).hexdigest()[:8].upper()
        self.results: list[Result] = []

    def observe_input(self, tag: str, observed_off: object, observed_on: object, note: str = "") -> Result:
        point = self._point(tag, "input")
        status = "pass" if observed_off == point.off_value and observed_on == point.on_value else "fail"
        return self._record(point, status, observed_off, observed_on, note)

    def exercise_output(self, tag: str, *, confirmation: str, note: str = "") -> Result:
        point = self._point(tag, "output")
        if point.safety_related:
            raise PermissionError("safety-related outputs cannot be exercised by commissionkit")
        if not self.allow_output_writes:
            raise PermissionError("output writes were not enabled for this session")
        if confirmation != self.confirmation_token:
            raise PermissionError("confirmation token does not match this session")
        self.adapter.write(tag, point.off_value)
        observed_off = self.adapter.read(tag)
        self.adapter.write(tag, point.on_value)
        observed_on = self.adapter.read(tag)
        self.adapter.write(tag, point.off_value)
        status = "pass" if observed_off == point.off_value and observed_on == point.on_value else "fail"
        return self._record(point, status, observed_off, observed_on, note)

    def skip(self, tag: str, note: str) -> Result:
        if not note.strip():
            raise ValueError("a skipped point requires a note")
        point = self.points[tag]
        return self._record(point, "skipped", None, None, note)

    def _point(self, tag: str, direction: str) -> Point:
        point = self.points[tag]
        if point.direction != direction:
            raise ValueError(f"{tag} is configured as {point.direction}")
        return point

    def _record(self, point: Point, status: str, observed_off: object, observed_on: object, note: str) -> Result:
        result = Result(
            tag=point.tag,
            direction=point.direction,
            status=status,
            observed_off=observed_off,
            observed_on=observed_on,
            operator=self.operator,
            recorded_at=datetime.now(timezone.utc).isoformat(),
            note=note,
        )
        self.results.append(result)
        return result

    def summary(self) -> dict[str, object]:
        counts = {status: sum(result.status == status for result in self.results) for status in ("pass", "fail", "skipped")}
        return {
            "operator": self.operator,
            "point_count": len(self.points),
            "tested_count": len(self.results),
            "counts": counts,
            "complete": len({result.tag for result in self.results}) == len(self.points),
        }

    def report_html(self) -> str:
        rows = "".join(
            "<tr>"
            f"<td>{html.escape(result.tag)}</td><td>{result.direction}</td>"
            f"<td class='{result.status}'>{result.status}</td>"
            f"<td>{html.escape(json.dumps(result.observed_off))}</td>"
            f"<td>{html.escape(json.dumps(result.observed_on))}</td>"
            f"<td>{html.escape(result.note)}</td><td>{html.escape(result.recorded_at)}</td>"
            "</tr>"
            for result in self.results
        )
        summary = self.summary()
        payload = json.dumps([asdict(result) for result in self.results], sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode()).hexdigest()
        return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><title>commissionkit report</title>
<style>body{{font:14px ui-monospace,monospace;margin:36px;color:#17201b}}h1{{font-size:34px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccd4ce;padding:8px;text-align:left}}.pass{{color:#08783b}}.fail{{color:#c21c1c}}.skipped{{color:#9a6500}}small{{overflow-wrap:anywhere}}</style></head>
<body><h1>commissionkit checkout report</h1><p>operator: {html.escape(self.operator)}<br>tested: {summary['tested_count']} / {summary['point_count']}<br>complete: {str(summary['complete']).lower()}</p>
<table><thead><tr><th>tag</th><th>direction</th><th>status</th><th>off</th><th>on</th><th>note</th><th>utc</th></tr></thead><tbody>{rows}</tbody></table>
<p><small>evidence sha-256: {digest}</small></p></body></html>"""

