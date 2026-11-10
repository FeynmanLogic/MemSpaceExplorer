import copy
import json
from pathlib import Path
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memspace import validate, project, analyze


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((Path(__file__).resolve().parents[1] / 'examples/demo.json').read_text())

    def test_memory_bound_improvement_and_compute_bound_plateau(self):
        d = validate(self.data)
        replay, backward = d['phases']
        hbm = d['technologies'][0]
        self.assertAlmostEqual(project(replay, hbm, d['baseline'])['roof_ratio'], 4)
        self.assertAlmostEqual(project(backward, hbm, d['baseline'])['roof_ratio'], 1)

    def test_hbf_latency_and_write_exclusion(self):
        d = validate(self.data)
        hbf = d['technologies'][1]
        r = project(d['phases'][0], hbf, d['baseline'])
        self.assertEqual(r['limit'], 'latency')
        self.assertAlmostEqual(r['latency_ms'], 7.632)
        self.assertEqual(project(d['phases'][1], hbf, d['baseline'])['status'], 'excluded')

    def test_capacity_and_pim_gating(self):
        d = validate(self.data)
        p = d['phases'][0]
        self.assertEqual(project(p, d['technologies'][2], d['baseline'])['status'], 'excluded')
        d['technologies'][0]['capacity_gb'] = 1
        self.assertEqual(project(p, d['technologies'][0], d['baseline'])['status'], 'excluded')

    def test_invalid_and_missing_measurements(self):
        for field, value in [('flops', -1), ('bytes', 0), ('time_ms', float('nan')), ('write_fraction', 2)]:
            d = copy.deepcopy(self.data)
            d['phases'][0][field] = value
            with self.assertRaises(ValueError):
                validate(d)
        del self.data['phases'][0]['flops']
        with self.assertRaises(KeyError):
            validate(self.data)

    def test_copy_phase_and_unknown_capacity(self):
        d = validate(self.data)
        p = d['phases'][0]
        p['flops'] = 0
        p['working_set_gb'] = None
        r = project(p, d['technologies'][0], d['baseline'])
        self.assertEqual(r['compute_ms'], 0)
        self.assertIn('Capacity fit unknown', r['notes'])

    def test_timing_inconsistency_reported(self):
        d = validate(self.data)
        d['phases'][0]['time_ms'] = 0.01
        report, _ = analyze(d)
        self.assertIn('Input inconsistency', report)

    def test_latency_concurrency_required(self):
        self.data['technologies'][1].pop('concurrency')
        with self.assertRaises(ValueError):
            validate(self.data)


if __name__ == '__main__':
    unittest.main()
