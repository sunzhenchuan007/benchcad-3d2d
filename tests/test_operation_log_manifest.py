"""Synthetic protocol tests; no CAD geometry or benchmark-score claims."""

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools.operation_log_manifest import (
    LOG_SCHEMA, Limits, LogError, NormalizedJSONLAdapter, derive, main, sha256_file,
)


INPUT_HASH = "a" * 64
DXF_HASH = "b" * 64


def event(seq, kind, **fields):
    return dict(run_id="run-test", seq=seq, kind=kind, success=True, **fields)


def view(identifier="A"):
    return dict(id=identifier, kind="section",
                section=dict(type="full", plane=dict(point_mm=[0, 0, 0], normal=[1, 0, 0])),
                dxf_evidence=dict(view_handles=["a1"], cutting_line_handles=["a2"],
                                  label_handles=["a3"]))


def fixture():
    return [
        event(0, "run_started", schema_version=LOG_SCHEMA, case_id="synthetic",
              input_sha256=INPUT_HASH, units="mm", frame="input_step"),
        event(1, "drawing_snapshot", document_revision=1, views=[view()]),
        event(2, "dxf_export", document_revision=1, export_id="export-1", dxf_sha256=DXF_HASH),
        event(3, "submission_finalized", export_id="export-1"),
    ]


def run(events, **kwargs):
    return derive(events, run_id="run-test", case_id="synthetic",
                  input_sha256=INPUT_HASH, dxf_sha256=DXF_HASH, **kwargs)


def wire(events):
    return io.BytesIO(b"".join(json.dumps(e).encode() + b"\n" for e in events))


class DerivationTests(unittest.TestCase):
    def test_reference_adapter_and_manifest_are_unscored(self):
        result = run(NormalizedJSONLAdapter().events(wire(fixture()), Limits()))
        self.assertEqual(result["status"], "derived")
        self.assertEqual(result["evidence_status"], "not_checked")
        self.assertEqual(result["scoring_status"], "not_scored")
        self.assertEqual(result["views"][0]["dxf_evidence"]["view_handles"], ["A1"])

    def test_updates_deletions_failures_and_final_snapshot(self):
        events = fixture()[:1] + [
            event(1, "view_upsert", document_revision=1, view=view("deleted")),
            event(2, "view_delete", document_revision=2, view_id="deleted"),
            event(3, "view_upsert", document_revision=3, view=view("updated")),
            event(4, "view_upsert", document_revision=4, view=view("updated")),
        ]
        events[4]["view"]["section"]["plane"]["point_mm"] = [30, 0, 0]
        failed = event(5, "view_delete", document_revision=5, view_id="updated")
        failed["success"] = False
        events += [failed,
                   event(6, "drawing_snapshot", document_revision=4, views=[events[4]["view"]]),
                   event(7, "dxf_export", document_revision=4, export_id="e", dxf_sha256=DXF_HASH),
                   event(8, "submission_finalized", export_id="e")]
        result = run(events)
        self.assertEqual([v["id"] for v in result["views"]], ["updated"])
        self.assertEqual(result["views"][0]["section"]["plane"]["point_mm"], [30, 0, 0])

    def test_export_state_is_frozen_even_after_later_edit(self):
        events = fixture()
        events.insert(3, event(3, "view_delete", document_revision=2, view_id="A"))
        events[-1]["seq"] = 4
        self.assertEqual(len(run(events)["views"]), 1)

    def test_undo_redo_are_represented_by_authoritative_snapshots(self):
        events = fixture()
        events[1:1] = [event(1, "drawing_snapshot", document_revision=1, views=[view("old")]),
                       event(2, "drawing_snapshot", document_revision=2, views=[])]
        for seq, e in enumerate(events):
            e["seq"] = seq
        events[3]["document_revision"] = 3
        events[4]["document_revision"] = 3
        self.assertEqual(run(events)["views"][0]["id"], "A")

    def test_missing_snapshot_or_evidence_is_incomplete(self):
        for mode in ("snapshot", "evidence", "empty"):
            with self.subTest(mode=mode):
                events = fixture()
                if mode == "snapshot":
                    events[1] = event(1, "view_upsert", document_revision=1, view=view())
                elif mode == "evidence":
                    del events[1]["views"][0]["dxf_evidence"]
                else:
                    events[1]["views"] = []
                self.assertEqual(run(events)["status"], "incomplete")

    def test_unbound_edit_requires_new_snapshot(self):
        events = fixture()
        events.insert(2, event(2, "view_upsert", document_revision=2, view=view("B")))
        events[3]["seq"] = 3
        events[3]["document_revision"] = 2
        events[4]["seq"] = 4
        self.assertIn("missing_final_snapshot", run(events)["issues"])

    def test_wrong_export_hash_stale_revision_and_missing_finalization_reject(self):
        for mutation in ("hash", "revision", "finalization", "export_id"):
            with self.subTest(mutation=mutation):
                events = fixture()
                if mutation == "hash":
                    events[2]["dxf_sha256"] = "c" * 64
                elif mutation == "revision":
                    events[2]["document_revision"] = 2
                elif mutation == "export_id":
                    events[3]["export_id"] = "unknown"
                else:
                    events.pop()
                with self.assertRaises(LogError):
                    run(events)

    def test_mixed_runs_bad_order_and_unknown_operations_reject(self):
        for field, value in (("run_id", "other"), ("seq", 0), ("kind", "raw_chat"),
                             ("success", "true"), ("seq", True)):
            with self.subTest(field=field):
                events = fixture()
                events[1][field] = value
                with self.assertRaises(LogError):
                    run(events)

    def test_wrong_header_rejects(self):
        for field, value in (("schema_version", "old"), ("case_id", "other"),
                             ("input_sha256", "c" * 64), ("units", "inch"),
                             ("frame", "world"), ("success", False)):
            with self.subTest(field=field):
                events = fixture()
                events[0][field] = value
                with self.assertRaises(LogError):
                    run(events)

    def test_invalid_geometry_and_unsupported_sections_reject(self):
        for value in ([0, 0, 0], [2, 0, 0], [float("nan"), 0, 0], [1, 0],
                      [True, 0, 0], [10 ** 500, 0, 0]):
            events = fixture()
            events[1]["views"][0]["section"]["plane"]["normal"] = value
            with self.subTest(value=str(value)[:30]), self.assertRaises(LogError):
                run(events)
        events = fixture()
        events[1]["views"][0]["section"]["type"] = "half"
        with self.assertRaises(LogError):
            run(events)

    def test_projection_view_without_section_is_valid(self):
        events = fixture()
        events[1]["views"] = [dict(id="front", kind="projection",
                                   dxf_evidence=dict(view_handles=["1A"]))]
        self.assertEqual(run(events)["status"], "derived")

    def test_snapshot_duplicate_delete_unknown_and_backwards_revision_reject(self):
        for mode in ("duplicate", "delete", "revision", "post_submit"):
            events = fixture()
            if mode == "duplicate":
                events[1]["views"] *= 2
            elif mode == "delete":
                events[1] = event(1, "view_delete", document_revision=1, view_id="unknown")
            elif mode == "revision":
                events.insert(2, event(2, "view_upsert", document_revision=0, view=view()))
            else:
                events.append(event(4, "drawing_snapshot", document_revision=2, views=[]))
            with self.subTest(mode=mode), self.assertRaises(LogError):
                run(events)

    def test_failed_export_does_not_replace_successful_export(self):
        events = fixture()
        failed = event(3, "dxf_export", export_id="bad")
        failed["success"] = False
        events.insert(3, failed)
        events[-1]["seq"] = 4
        self.assertEqual(run(events)["source"]["export_id"], "export-1")

    def test_older_export_cannot_be_selected(self):
        events = fixture()
        events.insert(3, event(3, "dxf_export", document_revision=1,
                               export_id="export-2", dxf_sha256=DXF_HASH))
        events[-1]["seq"] = 4
        with self.assertRaises(LogError):
            run(events)

    def test_limits_and_json_fail_closed(self):
        cases = [(b"x" * 11, Limits(max_line_bytes=10)),
                 (b"{}\n{}\n", Limits(max_total_bytes=5)),
                 (b"{}\n{}\n", Limits(max_events=1)),
                 (b'{"seq":1,"seq":2}\n', Limits()),
                 (b'{"x":NaN}\n', Limits()), (b"\xff\n", Limits()),
                 (b"\n", Limits()), (b"[]\n", Limits())]
        for data, limits in cases:
            with self.subTest(data=data[:20]), self.assertRaises(LogError):
                list(NormalizedJSONLAdapter().events(io.BytesIO(data), limits))
        with self.assertRaises(LogError):
            run(fixture(), limits=Limits(max_events=2))
        events = fixture()
        events[1]["views"].append(view("B"))
        with self.assertRaises(LogError):
            run(events, limits=Limits(max_views=1))
        with self.assertRaises(LogError):
            Limits(max_views=0)

    def test_custom_streaming_adapter(self):
        class FakeBackendAdapter:
            def events(self, stream, limits):
                yield from copy.deepcopy(fixture())
        self.assertEqual(run(FakeBackendAdapter().events(None, Limits()))["status"], "derived")

    def test_same_revision_cannot_change_snapshot_state(self):
        events = fixture()
        events.insert(2, event(2, "drawing_snapshot", document_revision=1, views=[]))
        events[3]["seq"] = 3
        events[4]["seq"] = 4
        with self.assertRaises(LogError):
            run(events)

    def test_adapter_hashes_exact_wire_bytes(self):
        adapter = NormalizedJSONLAdapter()
        stream = wire(fixture())
        import hashlib
        expected = hashlib.sha256(stream.getvalue()).hexdigest()
        run(adapter.events(stream, Limits()))
        self.assertEqual(adapter.sha256, expected)

    def test_adapter_reuse_cannot_mutate_exported_geometry(self):
        events = fixture()
        def generator():
            yield from events[:3]
            events[1]["views"][0]["section"]["plane"]["point_mm"][0] = 999
            yield events[3]
        self.assertEqual(run(generator())["views"][0]["section"]["plane"]["point_mm"],
                         [0, 0, 0])

    def test_cli_hash_binding_and_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dxf = root / "drawing.dxf"
            # Opaque synthetic bytes test hash binding only, not DXF validity.
            dxf.write_bytes(b"synthetic-export-not-a-real-drawing")
            events = fixture()
            events[2]["dxf_sha256"] = sha256_file(dxf)
            log = root / "events.jsonl"
            log.write_bytes(wire(events).getvalue())
            output = root / "actual.json"
            args = [str(log), "--dxf", str(dxf), "--output", str(output),
                    "--run-id", "run-test", "--case-id", "synthetic",
                    "--input-sha256", INPUT_HASH]
            self.assertEqual(main(args), 0)
            self.assertEqual(json.loads(output.read_text())["status"], "derived")
            self.assertEqual(json.loads(output.read_text())["source"]["operation_log_sha256"],
                             sha256_file(log))
            original = output.read_bytes()
            self.assertEqual(main(args), 1)
            self.assertEqual(output.read_bytes(), original)
            dxf.write_bytes(b"edited-outside-logged-export")
            output.unlink()
            self.assertEqual(main(args), 1)
            self.assertFalse(output.exists())
            events[1]["views"][0]["dxf_evidence"] = {}
            events[2]["dxf_sha256"] = sha256_file(dxf)
            log.write_bytes(wire(events).getvalue())
            self.assertEqual(main(args), 2)
            self.assertEqual(json.loads(output.read_text())["status"], "incomplete")


if __name__ == "__main__":
    unittest.main()
