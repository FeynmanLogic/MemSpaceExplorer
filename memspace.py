#!/usr/bin/env python3
"""MemSpaceExplorer: transparent phase-level memory scenario exploration."""
import argparse
import csv
import json
import math
from pathlib import Path


def number(value, label, minimum=0, strict=False):
    if isinstance(value, bool):
        raise ValueError(f'{label}: expected a number')
    value = float(value)
    if not math.isfinite(value) or value < minimum or (strict and value == minimum):
        raise ValueError(f'{label}: expected finite value {">" if strict else ">="} {minimum}')
    return value


def validate(data):
    b = data['baseline']
    for key in ('compute_gflops', 'bandwidth_gbs'):
        b[key] = number(b[key], key, strict=True)
    if not data['phases'] or not data['technologies']:
        raise ValueError('At least one phase and one technology are required')
    for collection in ('phases', 'technologies'):
        names = [x['name'] for x in data[collection]]
        if any(not isinstance(n, str) or not n.strip() or '\n' in n for n in names):
            raise ValueError('Names must be nonempty single-line strings')
        if len(names) != len(set(names)):
            raise ValueError(f'Duplicate names in {collection}')
    for p in data['phases']:
        for key in ('flops', 'bytes', 'time_ms'):
            p[key] = number(p[key], key, strict=key != 'flops')
        if p.get('traffic_basis') not in ('measured_dram', 'analytic'):
            raise ValueError('traffic_basis must be measured_dram or analytic')
        if p.get('access', 'unknown') not in ('sequential', 'random', 'unknown'):
            raise ValueError('Invalid access pattern')
        for key in ('working_set_gb',):
            if p.get(key) is not None:
                p[key] = number(p[key], key, strict=True)
        if p.get('write_fraction') is not None:
            p['write_fraction'] = number(p['write_fraction'], 'write_fraction')
            if p['write_fraction'] > 1:
                raise ValueError('write_fraction must be <= 1')
        if p.get('pim_compatible') not in (True, False, None):
            raise ValueError('pim_compatible must be true, false or null')
    for t in data['technologies']:
        for key in ('bandwidth_gbs',):
            t[key] = number(t[key], key, strict=True)
        for key in ('compute_gflops', 'capacity_gb', 'page_bytes', 'concurrency'):
            if t.get(key) is not None:
                t[key] = number(t[key], key, strict=True)
        for key in ('page_bytes', 'concurrency'):
            if t.get(key) is not None and not t[key].is_integer():
                raise ValueError(f'{key} must be an integer')
        for key in ('latency_us', 'extra_ms'):
            t[key] = number(t.get(key, 0), key)
        t['page_utilization'] = number(t.get('page_utilization', 1), 'page_utilization', strict=True)
        if t['page_utilization'] > 1:
            raise ValueError('page_utilization must be <= 1')
        if t.get('kind', 'memory') not in ('memory', 'hbf', 'pim'):
            raise ValueError('kind must be memory, hbf or pim')
        if t.get('supports_writes') not in (True, False, None):
            raise ValueError('supports_writes must be true, false or null')
        if t.get('kind') == 'pim' and t.get('compute_gflops') is None:
            raise ValueError('PIM requires an operation/precision-compatible compute roof')
        if t.get('kind') == 'hbf' and not t['latency_us']:
            raise ValueError('HBF requires explicit nonzero read latency')
        if t['latency_us'] and not (t.get('page_bytes') and t.get('concurrency')):
            raise ValueError('Latency modeling requires page_bytes and concurrency')
        if not t.get('evidence'):
            raise ValueError('Each scenario needs evidence or an explicit illustrative label')
    return data


def project(p, t, baseline):
    compute = t.get('compute_gflops') or baseline['compute_gflops']
    terms = {'compute': p['flops'] / (compute * 1e6),
             'bandwidth': p['bytes'] / t['page_utilization'] / (t['bandwidth_gbs'] * 1e6),
             'latency': 0.0}
    if t['latency_us']:
        pages = math.ceil(p['bytes'] / t['page_utilization'] / t['page_bytes'])
        terms['latency'] = math.ceil(pages / t['concurrency']) * t['latency_us'] / 1000
    notes, blocked = [], False
    if p.get('working_set_gb') is None or t.get('capacity_gb') is None:
        notes.append('Capacity fit unknown')
    elif p['working_set_gb'] > t['capacity_gb']:
        notes.append('Working set exceeds capacity; tiering is not modeled')
        blocked = True
    writes = p.get('write_fraction')
    if writes is None:
        notes.append('Write demand unknown')
    if t.get('supports_writes') is False and writes is not None and writes > 0:
        notes.append('Writes unsupported by this scenario')
        blocked = True
    elif t.get('supports_writes') is None and (writes is None or writes > 0):
        notes.append('Write support unverified')
    if t.get('kind') == 'hbf':
        if writes is None or writes > 0:
            notes.append('HBF read-latency model does not establish write performance/endurance')
        if p.get('access', 'unknown') != 'sequential':
            notes.append('Validate page utilization and achieved request concurrency for this access pattern')
    if t.get('kind') == 'pim':
        if p.get('pim_compatible') is False:
            blocked = True
            notes.append('PIM operations/precision incompatible')
        elif p.get('pim_compatible') is not True:
            notes.append('PIM operation/precision compatibility unknown')
        notes.append('PIM traffic transformation and host/offload transfers need validation')
    if p['traffic_basis'] == 'measured_dram':
        notes.append('Reuses baseline cache-dependent DRAM traffic')
    else:
        notes.append('Analytic traffic may omit cache reuse or overcount DRAM traffic')
    base_ms = max(p['flops'] / (baseline['compute_gflops'] * 1e6),
                  p['bytes'] / (baseline['bandwidth_gbs'] * 1e6))
    projected = max(terms.values()) + t['extra_ms']
    return {'phase': p['name'], 'technology': t['name'],
            'status': 'excluded' if blocked else 'conditional',
            'limit': max(terms, key=terms.get), 'projected_ms': projected,
            'roof_ratio': base_ms / projected,
            'compute_ms': terms['compute'], 'bandwidth_ms': terms['bandwidth'],
            'latency_ms': terms['latency'], 'extra_ms': t['extra_ms'],
            'notes': '; '.join(notes), 'evidence': t['evidence']}


def analyze(data):
    b = data['baseline']
    lines = ['# MemSpaceExplorer', '',
             'Conditional scenario exploration. Roof ratios compare modeled bounds, not measured speedups.',
             'All memory scenarios retain baseline compute unless a different compatible compute roof is supplied.',
             f"Baseline evidence: {b.get('evidence', 'user supplied; unverified')}", '',
             'Phases are analyzed independently. No end-to-end sum is inferred from possibly overlapping timings.', '']
    rows = []
    for p in data['phases']:
        ai = p['flops'] / p['bytes']
        ridge = b['compute_gflops'] / b['bandwidth_gbs']
        roof_ms = max(p['flops'] / (b['compute_gflops'] * 1e6), p['bytes'] / (b['bandwidth_gbs'] * 1e6))
        utilization = roof_ms / p['time_ms']
        lines += [f"## {p['name']}", '',
                  f"AI: {ai:.4g} FLOP/B. Baseline ridge: {ridge:.4g} FLOP/B.",
                  f"Roof model limit: {'bandwidth' if ai < ridge else 'compute'}. "
                  f"Observed time: {p['time_ms']:.4g} ms. Modeled baseline bound: {roof_ms:.4g} ms.",
                  f"Achieved throughput: {p['flops'] / (p['time_ms'] * 1e6):.4g} GFLOP/s; "
                  f"traffic rate: {p['bytes'] / (p['time_ms'] * 1e6):.4g} GB/s."]
        if utilization > 1.05:
            lines.append('Input inconsistency: observed runtime beats the supplied roof. Check units, counters, timing scope and precision.')
        elif utilization < 0.3:
            lines.append('Far below the supplied roof: investigate launch overhead, occupancy, dependencies, and access efficiency before attributing runtime to bandwidth.')
        if ai >= ridge:
            lines.append('Increasing bandwidth alone does not improve this compute roof bound; inspect compute efficiency or compatible compute capability.')
        group = [project(p, t, b) for t in data['technologies']]
        rows.extend(group)
        ranked = sorted((r for r in group if r['status'] != 'excluded'), key=lambda r: r['projected_ms'])
        if ranked:
            best = ranked[0]
            if best['roof_ratio'] > 1.05:
                lines.append(f"Candidate to investigate: {best['technology']} ({best['roof_ratio']:.3g}x roof ratio). Review conditions below.")
            else:
                lines.append('No eligible scenario materially improves the modeled baseline bound.')
        else:
            lines.append('No eligible scenario; review capacity, writes, and PIM compatibility.')
        lines += ['', '| Scenario | Bound (ms) | Roof ratio | Limit | Status |',
                  '|---|---:|---:|---|---|']
        for r in sorted(group, key=lambda r: r['projected_ms']):
            name = r['technology'].replace('|', '/')
            ratio = 'n/a' if r['status'] == 'excluded' else f"{r['roof_ratio']:.3g}x"
            lines.append(f"| {name} | {r['projected_ms']:.4g} | {ratio} | {r['limit']} | {r['status']} |")
        lines.append('')
        for r in group:
            lines += [f"- {r['technology']}: {r['notes']}. Evidence: {r['evidence']}"]
        lines.append('')
    return '\n'.join(lines) + '\n', rows


def ask_number(prompt, optional=False, minimum=0, strict=False, maximum=None, integer=False):
    while True:
        value = input(prompt + (' [Enter = unknown]' if optional else '') + ': ').strip()
        if optional and not value:
            return None
        try:
            n = number(value, prompt, minimum, strict)
            if maximum is not None and n > maximum:
                raise ValueError(f'Must be <= {maximum}')
            if integer and not n.is_integer():
                raise ValueError('Must be an integer')
            return int(n) if integer else n
        except ValueError as e:
            print(e)


def choice(prompt, options):
    while True:
        value = input(f'{prompt} ({"/".join(options)}): ').strip().lower()
        if value in options:
            return value


def text_input(prompt):
    while True:
        value = input(prompt + ': ').strip()
        if value:
            return value


def wizard():
    print('MemSpaceExplorer | decimal GB and GB/s, FLOPs count FMA as two operations.')
    print('Use the same precision, timing scope, and invocation count for all phase metrics.')
    b = {'compute_gflops': ask_number('Baseline sustained compute GFLOP/s', strict=True),
         'bandwidth_gbs': ask_number('Baseline sustained bandwidth GB/s', strict=True),
         'evidence': text_input('Baseline device, precision, and measurement provenance')}
    phases = []
    while True:
        p = {'name': text_input('Phase name'),
             'time_ms': ask_number('Measured phase runtime ms per invocation', strict=True),
             'flops': ask_number('FLOPs per invocation (0 only for a known copy/non-arithmetic phase)'),
             'bytes': ask_number('Traffic bytes per invocation (reads + writes)', strict=True),
             'traffic_basis': choice('Traffic basis', ['measured_dram', 'analytic']),
             'working_set_gb': ask_number('Resident working set GB, not traffic volume', optional=True, strict=True),
             'access': choice('Access pattern', ['sequential', 'random', 'unknown']),
             'write_fraction': ask_number('Fraction of traffic that is writes, 0 to 1', optional=True, maximum=1)}
        compat = choice('PIM operations and precision verified compatible', ['yes', 'no', 'unknown'])
        p['pim_compatible'] = {'yes': True, 'no': False, 'unknown': None}[compat]
        phases.append(p)
        if choice('Add another phase', ['yes', 'no']) == 'no':
            break
    technologies = []
    print('Enter comparable memory/system scenarios. Values are user supplied, not hardware facts.')
    while True:
        t = {'name': text_input('Scenario name'), 'kind': choice('Scenario kind', ['memory', 'hbf', 'pim']),
             'bandwidth_gbs': ask_number('Sustained physical bandwidth GB/s (before page utilization)', strict=True),
             'capacity_gb': ask_number('Capacity GB', optional=True, strict=True),
             'compute_gflops': ask_number('Compatible compute GFLOP/s; blank retains baseline (required for PIM)', optional=True, strict=True),
             'page_utilization': ask_number('Useful fraction of transferred pages, >0 to 1', strict=True, maximum=1),
             'latency_us': ask_number('Request latency us, 0 to omit; nonzero required for HBF'),
             'extra_ms': ask_number('Additional transfer/offload overhead ms per phase; 0 if omitted')}
        if t['latency_us']:
            t['page_bytes'] = ask_number('Request/page size bytes', strict=True, integer=True)
            t['concurrency'] = ask_number('Sustainable outstanding requests', strict=True, integer=True)
        t['supports_writes'] = {'yes': True, 'no': False, 'unknown': None}[choice('Writes supported', ['yes', 'no', 'unknown'])]
        t['evidence'] = text_input('Source, measurement provenance, or explicit illustrative assumption')
        if t['kind'] == 'hbf' and not t['latency_us']:
            t['latency_us'] = ask_number('HBF read request latency us', strict=True)
            t['page_bytes'] = ask_number('Request/page size bytes', strict=True, integer=True)
            t['concurrency'] = ask_number('Sustainable outstanding requests', strict=True, integer=True)
        if t['kind'] == 'pim' and t['compute_gflops'] is None:
            t['compute_gflops'] = ask_number('PIM compatible compute GFLOP/s', strict=True)
        technologies.append(t)
        if choice('Add another scenario', ['yes', 'no']) == 'no':
            break
    return {'baseline': b, 'phases': phases, 'technologies': technologies}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='Normalized JSON input; omit for interactive questions')
    parser.add_argument('--out', type=Path, default=Path('results'))
    args = parser.parse_args()
    try:
        data = validate(json.loads(args.input.read_text()) if args.input else wizard())
        report, rows = analyze(data)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / 'input.json').write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
        (args.out / 'report.md').write_text(report)
        with (args.out / 'projections.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(report)
        print(f'Saved reproducible inputs, report, and projections in {args.out.resolve()}')
    except (ValueError, KeyError, TypeError, OSError, EOFError) as error:
        parser.exit(2, f'Input error: {error}\n')


if __name__ == '__main__':
    main()
