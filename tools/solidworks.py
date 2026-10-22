"""Operator CLI for a prepared, trusted Windows SolidWorks pilot.

No import of pilot modules, implicit model requests, or credential discovery.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import tomllib
import uuid

SCHEMA = 'benchcad-solidworks-entry/1'
PREFLIGHTS = ('geometry-preflight', 'cad-preflight', 'sandbox-preflight',
             'sandbox-cad-preflight', 'cad-bridge-preflight')
ARTIFACTS = {
    'drawing_native': 'drawing/output/frozen/drawing.SLDDRW',
    'drawing_dxf': 'drawing/output/frozen/drawing.dxf',
    'drawing_state': 'drawing/output/frozen/drawing.json',
    'drawing_preview': 'drawing/output/frozen/preview.png',
    'reconstruction_step': 'reconstruction/output/model.step',
    'results_json': 'results.json', 'results_csv': 'results.csv',
}


class EntryError(Exception):
    pass


def read_json(path):
    try:
        if path.stat().st_size > 8 * 1024 * 1024:
            raise EntryError('JSON record exceeds the 8 MiB read limit.')
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except FileNotFoundError:
        return None
    except (ValueError, OSError) as exc:
        raise EntryError('Cannot read a JSON record; inspect the local runtime files.') from exc


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def load_config(path):
    try:
        doc = tomllib.loads(path.read_text(encoding='utf-8-sig'))
        cfg = doc['pilot']
        if not {'pilot'} <= set(doc) <= {'pilot', 'metrics'} or set(cfg) != {'root', 'python'}:
            raise ValueError('Unexpected configuration keys')
        if 'metrics' in doc and (not isinstance(doc['metrics'],dict) or set(doc['metrics']) != {'root'}
                                or not isinstance(doc['metrics']['root'],str)
                                or not doc['metrics']['root'].strip()):
            raise ValueError('Expected only a shared local metrics root')
        if not all(isinstance(v, str) and v.strip() for v in cfg.values()):
            raise ValueError('Expected nonempty paths')
        paths = [Path(cfg[k]).expanduser() for k in ('root', 'python')]
        root, python = [(p if p.is_absolute() else path.parent / p).resolve() for p in paths]
        if not root.is_dir() or not python.is_file():
            raise ValueError('Missing runtime or interpreter')
        return root, python
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise EntryError('Invalid entry config. Set [pilot] root and python to existing local paths; no secrets belong here.') from exc


def runtime_config(root):
    cfg = read_json(root / 'config.json')
    if not isinstance(cfg, dict):
        raise EntryError('Prepared runtime config.json is missing or invalid.')
    return cfg


def snapshot(root):
    state = read_json(root / 'controller/state.json') or {}
    results = read_json(root / 'results.json') or {}
    if not isinstance(state, dict) or not isinstance(results, dict):
        raise EntryError('Invalid state or results object.')
    stages = {}
    for stage in ('drawing', 'reconstruction'):
        attempts = read_json(root / 'controller' / (stage + '-attempts.json')) or []
        if not isinstance(attempts, list) or any(not isinstance(a, dict) for a in attempts):
            raise EntryError('Invalid episode attempt records.')
        last = attempts[-1] if attempts else {}
        counts = last.get('event_counts') or {}
        usage = last.get('token_usage') or {}
        if not isinstance(counts, dict) or not isinstance(usage, dict):
            raise EntryError('Invalid event-count or usage records.')
        stages[stage] = {
            'cli_launches': len(attempts),
            'last_classification': last.get('classification'),
            'last_elapsed_seconds': number(last.get('elapsed_seconds')),
            'last_command_executions': number(counts.get('completed_command_execution')),
            'last_usage': {k: number(usage.get(k)) for k in
                           ('input_tokens', 'cached_input_tokens', 'output_tokens')},
            'submission_requested': (root / stage / 'output/SUBMIT.json').is_file(),
        }
    metrics = results.get('metrics') or {}
    if not isinstance(metrics, dict):
        raise EntryError('Invalid metrics object.')
    metrics = {k: v for k, v in metrics.items() if k in (
        'reconstruction_iou', 'reconstruction_iou24', 'reconstruction_iou24_reflected',
        'reflection_used', 'section_requirements', 'annotation_collision')
        and (v is None or type(v) is bool or number(v) is not None)}
    artifacts = {k: v for k, v in ARTIFACTS.items() if (root / v).is_file()}
    # The reconstruction submit filename is configurable in the original protocol.
    submission = read_json(root / 'reconstruction/output/SUBMIT.json')
    if isinstance(submission, dict) and isinstance(submission.get('step'), str):
        candidate = (root / 'reconstruction/output' / submission['step']).resolve()
        output = (root / 'reconstruction/output').resolve()
        if candidate.is_relative_to(output) and candidate.suffix.lower() in ('.step', '.stp') and candidate.is_file():
            artifacts['reconstruction_step'] = candidate.relative_to(root).as_posix()
    latest = read_json(root / '.launcher/latest.json')
    launch = read_json(root / '.launcher' / latest['id'] / 'launch.json') if (
        isinstance(latest, dict) and isinstance(latest.get('id'), str)
        and len(latest['id']) == 32 and all(c in '0123456789abcdef' for c in latest['id'])) else None
    metric_latest = read_json(root / '.metric-reviews/latest.json') or {}
    metric_id = metric_latest.get('id') if isinstance(metric_latest,dict) else None
    reviewed = read_json(root/'.metric-reviews'/metric_id/'metrics.json') if (
        isinstance(metric_id,str) and len(metric_id)==32 and all(c in '0123456789abcdef' for c in metric_id)) else None
    episodes = results.get('episodes') or []
    for stage, entry in stages.items():
        rows = [r for r in episodes if isinstance(r, dict) and r.get('stage') == stage] if isinstance(episodes, list) else []
        entry['reported_cad_requests'] = sum(r['cad_requests'] for r in rows) if rows and all(
            number(r.get('cad_requests')) is not None for r in rows) else None
    return {'schema': SCHEMA, 'stage': state.get('stage'), 'status': state.get('status', 'not_started'),
            'updated': state.get('updated'), 'lock_present': (root / 'controller/runner.lock').exists(),
            'lock_note': 'A lock may be active or stale; presence does not prove liveness.',
            'stages': stages, 'metrics': metrics, 'formal_score': False,
            'artifacts': artifacts, 'launcher': launch,
            'current_metrics': reviewed.get('metrics') if isinstance(reviewed,dict) else None,
            'model_rounds': None, 'model_round_limit_enforced_by_entry': False}


def doctor(root, python):
    cfg = runtime_config(root)
    checks = []

    def add(name, ok, reason):
        checks.append({'check': name, 'passed': bool(ok), 'detail': reason})

    add('windows', sys.platform == 'win32', 'SOLIDWORKS execution requires Windows.')
    for rel in ('runner.py', 'pilotlib.py', 'run_episode.py', 'tools/cad_exec.py',
                'tools/finalize_drawing.py', 'tools/render_dxf.py',
                'drawing/TASK.md', 'reconstruction/TASK.md', 'drawing/input/model.step'):
        add(rel, (root / rel).is_file(), 'Required prepared runtime file.')
    for field in ('codex', 'cad_sandbox_cli', 'cad_python', 'geometry_python'):
        value = cfg.get(field)
        add(field, isinstance(value, str) and Path(value).is_file(), 'Configured executable must exist.')
    for field, upper in (('case_timeout_seconds', None), ('diagnostic_memory_mib', None),
                         ('diagnostic_cpu_percent', 100)):
        value = number(cfg.get(field))
        add(field, value is not None and value > 0 and (upper is None or value <= upper),
            'Positive runtime budget; CPU percentage must not exceed 100.')
    for name in PREFLIGHTS:
        evidence = read_json(root / 'controller' / (name + '.json'))
        ok = isinstance(evidence, dict) and (evidence.get('valid') is True if name == 'geometry-preflight'
                                             else evidence.get('status') == 'passed')
        add(name, ok, 'Stored preflight evidence only; this is not a fresh CAD or isolation probe.')
    catalog = read_json(root / 'controller/available-models.json') or {}
    models = catalog.get('models', []) if isinstance(catalog, dict) else []
    add('model_catalog', any(isinstance(m, dict) and m.get('model') == cfg.get('model') for m in models),
        'Stored catalog only; current account access is not contacted or verified.')
    add('controller_python', python.is_file(), 'Configured controller Python exists.')
    return {'schema': SCHEMA, 'ready_for_existing_runtime': all(c['passed'] for c in checks),
            'checks': checks, 'api_requests': 0, 'cad_started': False,
            'model': cfg.get('model'), 'reasoning_effort': cfg.get('reasoning_effort'),
            'budgets': {k: cfg.get(k) for k in ('case_timeout_seconds', 'diagnostic_memory_mib', 'diagnostic_cpu_percent')},
            'scope': 'Prepared-runtime checks only; no installation, authentication or live isolation certification.'}


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def launch(root, python, resume=False, dry_run=False):
    checks = doctor(root, python)
    if not checks['ready_for_existing_runtime']:
        raise EntryError('Runtime checks failed. Run doctor and fix the reported items first.')
    current = snapshot(root)
    if current['lock_present'] or (root / '.launcher/entry.lock').exists():
        raise EntryError('A runtime/entry lock exists. Inspect the local process before manually resolving a stale lock.')
    if current['status'] == 'partial_metrics_completed':
        raise EntryError('This run already completed. Use results; prepare a separate runtime for another trial.')
    used = (root / 'controller/state.json').exists() or any(
        s['cli_launches'] or s['submission_requested'] for s in current['stages'].values())
    if used and not resume:
        raise EntryError('Existing progress found. Use --resume explicitly; this does not reset attempts or budgets.')
    if dry_run:
        return {'schema': SCHEMA, 'status': 'launch_ready', 'executed': False,
                'resume': resume, 'model': checks['model'], 'budgets': checks['budgets']}
    folder = root / '.launcher'
    folder.mkdir(exist_ok=True)
    try:
        lock = (folder / 'entry.lock').open('x')
    except FileExistsError as exc:
        raise EntryError('Another entry command acquired the launch lock.') from exc
    child = None
    record = None
    try:
        lock.write(str(os.getpid())); lock.flush()
        run_id = uuid.uuid4().hex
        logdir = folder / run_id
        logdir.mkdir()
        record = {'id': run_id, 'status': 'starting', 'started': datetime.now(timezone.utc).isoformat(),
                  'stdout': '.launcher/' + run_id + '/stdout.log',
                  'stderr': '.launcher/' + run_id + '/stderr.log', 'exit_code': None}
        save(logdir / 'launch.json', record)
        save(folder / 'latest.json', {'id': run_id})
        with (logdir / 'stdout.log').open('wb') as out, (logdir / 'stderr.log').open('wb') as err:
            env = os.environ.copy()
            env.update(PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
            child = subprocess.Popen([str(python), str(root / 'runner.py'), 'run'],
                cwd=root, stdin=subprocess.DEVNULL, stdout=out, stderr=err, env=env)
            record.update(status='running', pid=child.pid)
            save(logdir / 'launch.json', record)
            previous = None
            while child.poll() is None:
                try:
                    status = snapshot(root)
                    message = (status['stage'], status['status'])
                    if message != previous:
                        print(json.dumps({'event': 'progress', 'stage': message[0], 'status': message[1]}), flush=True)
                        previous = message
                except EntryError:
                    # A temporarily incomplete legacy JSON write must not kill a running experiment.
                    pass
                time.sleep(1)
        record.update(status='exited', exit_code=child.returncode, finished=datetime.now(timezone.utc).isoformat())
        save(logdir / 'launch.json', record)
        return {'schema': SCHEMA, 'launcher': record, 'result': snapshot(root)}
    except BaseException:
        if child is not None and child.poll() is None:
            # Do not pretend the controller or its CAD children were terminated.
            record.update(status='entry_interrupted_child_may_be_running')
            save(logdir / 'launch.json', record)
        elif record is not None:
            record.update(status='entry_failed', exit_code=child.returncode if child else None)
            save(logdir / 'launch.json', record)
        raise
    finally:
        lock.close()
        # Keep the guard if the launcher was interrupted with a live controller.
        if child is None or child.poll() is not None:
            (folder / 'entry.lock').unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='Create a local entry config; no CAD or model calls')
    init.add_argument('--pilot-root', type=Path, required=True)
    init.add_argument('--python', type=Path, default=Path(sys.executable))
    init.add_argument('--config', type=Path, default=Path('.local/solidworks.toml'))
    for name in ('doctor', 'status', 'results', 'run'):
        sub = commands.add_parser(name)
        sub.add_argument('--config', type=Path, required=True)
        if name == 'run':
            sub.add_argument('--resume', action='store_true')
            sub.add_argument('--dry-run', action='store_true')
    score = commands.add_parser('score', help='Local three-metric review; no model calls and no historical overwrite')
    score.add_argument('--config', type=Path, required=True)
    score.add_argument('--metrics-root', type=Path, required=True, help='Local CadQuery repository containing shared evaluation code')
    score.add_argument('--output-dir', type=Path, required=True)
    score.add_argument('--expert-json', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            root, python = args.pilot_root.resolve(), args.python.resolve()
            if not (root / 'runner.py').is_file() or not python.is_file():
                raise EntryError('Choose a prepared runtime containing runner.py and an existing Python interpreter.')
            args.config.parent.mkdir(parents=True, exist_ok=True)
            try:
                with args.config.open('x', encoding='utf-8') as f:
                    f.write('[pilot]\nroot = ' + json.dumps(root.as_posix(), ensure_ascii=False)
                            + '\npython = ' + json.dumps(python.as_posix(), ensure_ascii=False) + '\n')
            except FileExistsError as exc:
                raise EntryError('Config already exists; it was not overwritten.') from exc
            result = {'schema': SCHEMA, 'status': 'config_created', 'api_requests': 0}
        else:
            root, python = load_config(args.config.resolve())
            if args.command == 'doctor':
                result = doctor(root, python)
            elif args.command in ('status', 'results'):
                result = snapshot(root)
            elif args.command == 'score':
                script = args.metrics_root.resolve()/'evaluation/rescore.py'
                if not script.is_file():
                    raise EntryError('Shared local evaluation/rescore.py is missing.')
                geometry_python = Path(runtime_config(root)['geometry_python'])
                command = [str(geometry_python), '-W', 'ignore', str(script),
                           '--dxf', str(root/'drawing/output/frozen/drawing.dxf'),
                           '--native-views', str(root/'drawing/output/frozen/drawing.json'),
                           '--iou-json', str(root/'evaluator/iou.json'),
                           '--output-dir', str(args.output_dir.resolve())]
                if args.expert_json:
                    command += ['--expert-json', str(args.expert_json.resolve())]
                completed = subprocess.run(command, cwd=args.metrics_root.resolve(), timeout=300)
                return 0 if completed.returncode == 0 else 1
            else:
                result = launch(root, python, args.resume, args.dry_run)
                metric_config = tomllib.loads(args.config.read_text(encoding='utf-8-sig')).get('metrics')
                if not args.dry_run and result['launcher']['exit_code'] == 0 and metric_config:
                    metric_root = Path(metric_config['root'])
                    if not metric_root.is_absolute():
                        metric_root = args.config.resolve().parent / metric_root
                    review = root / '.metric-reviews' / uuid.uuid4().hex
                    code = main(['score','--config',str(args.config),'--metrics-root',str(metric_root),
                                 '--output-dir',str(review)])
                    result['metric_review'] = {'exit_code':code,'directory':review.relative_to(root).as_posix()}
                    if code == 0:
                        result['current_metrics'] = read_json(review/'metrics.json')['metrics']
                        save(root/'.metric-reviews/latest.json', {'id':review.name})
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        if args.command == 'doctor' and not result['ready_for_existing_runtime']:
            return 2
        if args.command == 'run' and not args.dry_run:
            return 0 if result['launcher']['exit_code'] == 0 and result.get('metric_review',{}).get('exit_code',0)==0 else 1
        return 0
    except (EntryError, OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        message = str(exc) if isinstance(exc, EntryError) else 'Local operation failed; inspect runtime files and permissions.'
        print(json.dumps({'schema': SCHEMA, 'status': 'error', 'message': message}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
