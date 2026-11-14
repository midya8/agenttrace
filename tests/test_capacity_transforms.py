"""Finite coordinate/penalty transformations, with tie-policy controls."""
import copy
import itertools
import unittest

from agenttrace.capacity import capacity_report


ROWS = [
    dict(id='long', start=0, end=4, drop_penalty=9),
    dict(id='left', start=0, end=2, drop_penalty=6),
    dict(id='right', start=2, end=4, drop_penalty=6),
    dict(id='point', start=2, end=2, drop_penalty=3),
    dict(id='free', start=1, end=3, drop_penalty=0),
    dict(id='tie', start=0, end=2, drop_penalty=6),
    dict(id='low', start=6, end=7, drop_penalty=2),
    dict(id='high', start=6, end=7, drop_penalty=3),
]


class CapacityTransformTests(unittest.TestCase):
    def test_positive_affine_time_preserves_complete_report_after_remap(self):
        for k, scale, shift in itertools.product(range(5), [1, 2, 7], [0, 11, 100]):
            with self.subTest(capacity=k, scale=scale, shift=shift):
                request = dict(capacity=k, intervals=copy.deepcopy(ROWS))
                expected = capacity_report(request)
                for row in request['intervals']:
                    for field in ['start', 'end']:
                        row[field] = row[field] * scale + shift
                actual = capacity_report(request)
                for rows in [expected['input']['intervals'], expected['intervals'], expected['segments']]:
                    for row in rows:
                        for field in ['start', 'end']:
                            row[field] = row[field] * scale + shift
                network = expected['selected']['network']
                network['times'] = [t * scale + shift for t in network['times']]
                self.assertEqual(actual, expected)

    def test_positive_penalty_scaling_preserves_every_frontier_choice(self):
        for k, scale in itertools.product(range(5), [1, 2, 13, 100]):
            with self.subTest(capacity=k, scale=scale):
                original = capacity_report(dict(capacity=k, intervals=ROWS))
                changed = copy.deepcopy(ROWS)
                for row in changed:
                    row['drop_penalty'] *= scale
                report = capacity_report(dict(capacity=k, intervals=changed))
                for before, after in zip(original['frontier'], report['frontier']):
                    expected = copy.deepcopy(before)
                    for key in ['retained_penalty', 'drop_penalty']:
                        expected[key] *= scale
                    self.assertEqual(after, expected)
                self.assertEqual([r['lane'] for r in report['intervals']],
                                 [r['lane'] for r in original['intervals']])
                self.assertEqual(report['selected']['network']['gap'], 0)
                self.assertTrue(all(a['reduced_cost'] >= 0 for a in report['selected']['network']['residual']))

    def test_reordering_equal_votes_can_change_the_named_winner(self):
        rows = [dict(id=name, start=0, end=1, drop_penalty=3) for name in ['a', 'b']]
        before = capacity_report(dict(capacity=1, intervals=rows))
        after = capacity_report(dict(capacity=1, intervals=list(reversed(rows))))
        self.assertEqual(before['selected']['retained_ids'], ['a'])
        self.assertEqual(after['selected']['retained_ids'], ['b'])
        self.assertEqual(before['selected']['retained_penalty'], after['selected']['retained_penalty'])
