"""Check that the test suite catches deliberate breaks in the label and feature SQL.

Each mutation edits a temporary copy of one SQL file (the checked-in files are never
touched) and runs the suite against it via LABEL_SQL / FEATURES_SQL. A mutation that
leaves the suite passing has "survived", and the command exits 1.

    .venv/bin/python tests/mutation_check.py          # all mutations
    .venv/bin/python tests/mutation_check.py tie      # names containing "tie"
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
FILES = {"label": PROJECT / "sql" / "03_label.sql", "features": PROJECT / "sql" / "04_features.sql"}
ENV = {"label": "LABEL_SQL", "features": "FEATURES_SQL"}

# (name, file, [(original text, replacement), ...])
MUTATIONS = [
    ("label: absent checked before missing follow-up", "label", [(
        "CASE WHEN c2 IS NULL OR c3 IS NULL THEN 'insufficient_followup'\n            WHEN NOT in_c2 AND NOT in_c3 THEN 'absent_confirmed'",
        "CASE WHEN NOT COALESCE(in_c2, false) AND NOT COALESCE(in_c3, false) THEN 'absent_confirmed'\n"
        "            WHEN c2 IS NULL OR c3 IS NULL THEN 'insufficient_followup'")]),
    ("label: ties break to the later date", "label", [
        ("ORDER BY distance, snap) = 1", "ORDER BY distance, snap DESC) = 1")]),
    ("label: C3 not required to follow C2", "label", [
        ("WHERE w.checkpoint = 'c3' AND (c2.snap IS NULL OR w.snap > c2.snap)", "WHERE w.checkpoint = 'c3'")]),
    ("label: suspected contractions unusable", "label", [
        ("status IN ('ok', 'suspected_contraction') AS usable_checkpoint", "status = 'ok' AS usable_checkpoint")]),
    ("label: completeness window looks ahead", "label", [
        ("ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS trailing_median",
         "ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING) AS trailing_median")]),
    ("label: resolution known at the flagged date", "label", [
        ("WHEN status IN ('partial_scrape', 'suspected_contraction') THEN resolver_snap",
         "WHEN status IN ('partial_scrape', 'suspected_contraction') THEN snap")]),
    ("label: newness check dropped", "label", [
        ("(recently_first_observed AND newness_known)", "recently_first_observed")]),
    ("label: flagged snapshots as prediction dates", "label", [
        ("WHERE status = 'ok'\nQUALIFY", "WHERE status <> 'insufficient_history'\nQUALIFY")]),
    ("label: C2 requires a usable C1", "label", [
        ("WHERE checkpoint IN ('c1', 'c2') AND usable_checkpoint\n",
         "WHERE checkpoint IN ('c1', 'c2') AND usable_checkpoint AND EXISTS (SELECT 1 FROM win x "
         "WHERE x.city_id = win.city_id AND x.t = win.t AND x.checkpoint = 'c1' AND x.usable_checkpoint)\n")]),
    ("label: finality from picks only", "label", [(
        """                ELSE greatest(tg.window_closes,
                              COALESCE(pk.status_known_at, tg.window_closes),
                              COALESCE(MAX(b.status_known_at), tg.window_closes)) END AS final_at""",
        "                ELSE pk.status_known_at END AS final_at")]),
    ("label: blockers ignored", "label", [
        ("WHEN COUNT(b.city_id) FILTER (WHERE b.status_known_at IS NULL) > 0 THEN NULL", "WHEN false THEN NULL"),
        ("COALESCE(MAX(b.status_known_at), tg.window_closes)", "tg.window_closes")]),
    ("label: any later snapshot can resolve", "label", [(
        "JOIN flags r ON r.city_id = f.city_id AND r.snap > f.snap AND NOT r.anomaly\n                             AND r.n_prior >= 3",
        "JOIN flags r ON r.city_id = f.city_id AND r.snap > f.snap")]),
    ("label: any earlier snapshot is the reference", "label", [
        ("JOIN flags r ON r.city_id = f.city_id AND r.snap < f.snap AND NOT r.anomaly",
         "JOIN flags r ON r.city_id = f.city_id AND r.snap < f.snap")]),
    ("label: no resolution wait limit", "label", [
        ("AND r.snap <= f.snap + getvariable('resolve_max_days')", "")]),
    ("label: C3 finality independent of C2", "label", [
        ("THEN greatest(f2.final_at, f3.final_at) END AS label_final_at", "THEN f3.final_at END AS label_final_at")]),
    ("label: pending treated as unresolved", "label", [
        ("WHEN as_of >= snap + getvariable('resolve_max_days') THEN 'anomaly_unresolved'",
         "WHEN true THEN 'anomaly_unresolved'")]),
    ("features: history may include t and later", "features", [
        ("JOIN schedule s ON s.city_id = p.city_id AND s.snap < p.t", "JOIN schedule s ON s.city_id = p.city_id")]),
    ("features: history includes partial scrapes", "features", [
        ("WHERE s.status IN ('ok', 'insufficient_history', 'suspected_contraction')",
         "WHERE s.status IN ('ok', 'insufficient_history', 'suspected_contraction', 'partial_scrape')")]),
    ("features: review rate ignores elapsed time", "features", [
        ("30.0 * (c.number_of_reviews - x90.number_of_reviews) / datediff('day', a90.snap, c.snap)",
         "(c.number_of_reviews - x90.number_of_reviews) / 3.0")]),
    ("features: presence window unbounded", "features", [
        ("AND h.snap >= c.t - 365", "")]),
    ("features: market growth vs latest snapshot", "features", [
        ("LEFT JOIN snap_market m365 ON m365.city_id = c.city_id AND m365.snap = a365.snap",
         "LEFT JOIN snap_market m365 ON m365.city_id = c.city_id AND m365.snap = "
         "(SELECT MAX(snap) FROM lf WHERE lf.city_id = c.city_id)")]),
]


def pytest(env):
    cmd = [sys.executable, "-m", "pytest", str(PROJECT / "tests"), "-q", "-x", "-p", "no:cacheprovider", "--tb=no"]
    return subprocess.run(cmd, env={**os.environ, **env}, capture_output=True, text=True, cwd=PROJECT)


def main(selector=""):
    baseline = pytest({})
    if baseline.returncode != 0:
        print("baseline suite fails; fix it before mutation testing\n" + baseline.stdout[-2000:])
        return 1
    survived = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, which, edits in MUTATIONS:
            if selector not in name:
                continue
            sql = FILES[which].read_text()
            for old, new in edits:
                if old not in sql:
                    print(f"STALE   {name}: pattern not found, update this mutation")
                    survived.append(name)
                    break
                sql = sql.replace(old, new)
            else:
                path = Path(tmp) / f"{which}.sql"
                path.write_text(sql)
                result = pytest({ENV[which]: str(path)})
                summary = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
                # an assertion must fail; an error (e.g. invalid mutated SQL) proves nothing
                caught = result.returncode != 0 and " failed" in summary
                label = "caught " if caught else ("INVALID " if result.returncode else "SURVIVED")
                print(f"{label} {name}   [{summary}]")
                if not caught:
                    survived.append(name)
    print(f"\n{len(survived)} survived" + (f": {survived}" if survived else ""))
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
