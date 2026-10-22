import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('solidworks_entry', Path(__file__).resolve().parents[1] / 'tools/solidworks.py')
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


class EntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'prepared pilot'
        self.root.mkdir()
        self.python = Path(sys.executable)

    def write(self, name, value):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value), encoding='utf-8')

    def test_init_roundtrip_spaces_and_no_overwrite(self):
        (self.root / 'runner.py').write_text('')
        config = self.root / 'entry.toml'
        args = ['init', '--pilot-root', str(self.root), '--python', str(self.python), '--config', str(config)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(entry.main(args), 0)
            before = config.read_bytes()
            self.assertEqual(entry.main(args), 2)
        self.assertEqual(config.read_bytes(), before)
        root, python = entry.load_config(config)
        self.assertEqual(root, self.root.resolve())
        self.assertEqual(python, self.python.resolve())

    def test_relative_config_and_secret_fields_rejected(self):
        config = self.root / 'entry.toml'
        config.write_text('[pilot]\nroot = "."\npython = ' + json.dumps(self.python.as_posix()))
        self.assertEqual(entry.load_config(config)[0], self.root.resolve())
        config.write_text(config.read_text() + '\napi_key = "not-an-actual-key"')
        with self.assertRaises(entry.EntryError):
            entry.load_config(config)

    def test_readonly_summary_distinguishes_counters_and_missing_scores(self):
        self.write('controller/state.json', {'stage': 'evaluation', 'status': 'partial_metrics_completed'})
        self.write('controller/drawing-attempts.json', [{'classification': 'submission_requested',
            'elapsed_seconds': 10, 'event_counts': {'completed_command_execution': 42},
            'token_usage': {'input_tokens': 100}}])
        self.write('results.json', {'metrics': {'reconstruction_iou': 0.99, 'section_requirements': None,
                                               'private_note': 'must not enter summary'},
                                   'episodes': [{'stage': 'drawing', 'cad_requests': 9}]})
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = entry.snapshot(self.root)
        self.assertEqual(result['stages']['drawing']['cli_launches'], 1)
        self.assertEqual(result['stages']['drawing']['last_command_executions'], 42)
        self.assertEqual(result['stages']['drawing']['reported_cad_requests'], 9)
        self.assertIsNone(result['model_rounds'])
        self.assertIsNone(result['metrics']['section_requirements'])
        self.assertNotIn('private_note', result['metrics'])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_submission_cannot_advertise_outside_file(self):
        self.write('reconstruction/output/SUBMIT.json', {'step': '../../../outside.step'})
        (self.root.parent / 'outside.step').write_text('private')
        self.assertNotIn('reconstruction_step', entry.snapshot(self.root)['artifacts'])

    def test_doctor_does_not_spawn_anything_and_missing_preflights_block(self):
        self.write('config.json', {'model': 'test-model'})
        with patch.object(entry.subprocess, 'Popen', side_effect=AssertionError('Unexpected execution')):
            result = entry.doctor(self.root, self.python)
        self.assertFalse(result['ready_for_existing_runtime'])
        self.assertEqual(result['api_requests'], 0)
        self.assertTrue(any(c['check'] == 'cad-preflight' and not c['passed'] for c in result['checks']))

    def ready(self):
        return patch.object(entry, 'doctor', return_value={
            'ready_for_existing_runtime': True, 'model': 'test-model', 'budgets': {}})

    def test_run_requires_explicit_resume_and_blocks_completed_or_locked(self):
        self.write('controller/state.json', {'stage': 'drawing', 'status': 'running'})
        with self.ready():
            with self.assertRaises(entry.EntryError):
                entry.launch(self.root, self.python, dry_run=True)
            self.assertFalse(entry.launch(self.root, self.python, resume=True, dry_run=True)['executed'])
            self.write('controller/runner.lock', 123)
            with self.assertRaises(entry.EntryError):
                entry.launch(self.root, self.python, resume=True)
            (self.root / 'controller/runner.lock').unlink()
            self.write('controller/state.json', {'status': 'partial_metrics_completed'})
            with self.assertRaises(entry.EntryError):
                entry.launch(self.root, self.python, resume=True)
        self.assertFalse((self.root / '.launcher').exists())

    def test_real_child_failure_is_recorded_without_echoing_raw_output(self):
        (self.root / 'runner.py').write_text('print("raw-private-fixture")\nraise SystemExit(7)\n')
        out = io.StringIO()
        with self.ready(), contextlib.redirect_stdout(out):
            result = entry.launch(self.root, self.python)
        record = result['launcher']
        self.assertEqual(record['exit_code'], 7)
        self.assertEqual(record['status'], 'exited')
        self.assertNotIn('raw-private-fixture', out.getvalue())
        self.assertIn('raw-private-fixture', (self.root / record['stdout']).read_text())
        self.assertFalse((self.root / '.launcher/entry.lock').exists())
        self.assertEqual(entry.snapshot(self.root)['launcher']['id'], record['id'])

    def test_spawn_failure_has_record_and_releases_entry_lock(self):
        with self.ready(), patch.object(entry.subprocess, 'Popen', side_effect=OSError('fixture spawn failure')):
            with self.assertRaises(OSError):
                entry.launch(self.root, self.python)
        self.assertEqual(entry.snapshot(self.root)['launcher']['status'], 'entry_failed')
        self.assertFalse((self.root / '.launcher/entry.lock').exists())


if __name__ == '__main__':
    unittest.main()
