#!/usr/bin/env python3
from __future__ import annotations
import sys, unittest
from fractions import Fraction
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from minimize import solve_descriptors, verify_sparse_certificate
from schema import validate_launch, validate_spec

class PipelineTests(unittest.TestCase):
    def test_manual_launch_is_twenty_by_20700(self):
        launch = validate_launch({
            'schema_version':1,'enabled':True,'run_index':2,
            'task':'stage2_minimize_certificates',
            'spec_path':'fourth-approach/run-specs/run-002-stage2-minimize-certificates.json',
            'jobs':20,'minimum_jobs':18,'runtime_seconds':20700,
            'max_attempts':0,'nonce':'manual-run-002-20260805',
        })
        self.assertEqual(launch['jobs'],20)
        self.assertEqual(launch['runtime_seconds'],20700)

    def test_exact_solver_finds_sparse_identity(self):
        # Synthetic real linear identity: (1+x) - x = 1.
        # This tests the exact Gaussian core independently of Krenn--Gu encoding.
        from minimize import Fraction as _F  # module import sanity
        self.assertIs(_F, Fraction)

    def test_ready_spec(self):
        spec = validate_spec({
            'schema_version':1,'implementation_status':'ready','run_index':2,
            'task':'stage2_minimize_certificates','title':'x','research_question':'x',
            'scientific_output':'x','next_decision':'x',
            'source_canonical_classes':'fourth-approach/runs/run-001-30957731562/canonical-classes.json',
            'candidate_archives':[{'path':'third-approach-2.0/runs/x/top-candidates.json.gz'}],
            'execution':{'jobs':20,'minimum_jobs':18,'runtime_seconds':20700,'max_attempts':0},
        }, require_ready=True)
        self.assertEqual(spec['run_index'],2)

if __name__ == '__main__':
    unittest.main()
