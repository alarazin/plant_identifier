import os
os.environ.setdefault('EACHLABS_API_KEY', 'offline-test')
import unittest
from unittest.mock import AsyncMock
from eval.run_eval import CONFIGS, sample_rows, score_row, spending, summarize


class EvaluationTests(unittest.IsolatedAsyncioTestCase):
    def test_configurations_are_current(self):
        from backend.app.main import CHAIN
        self.assertEqual(list(CONFIGS), [p.slug for p in CHAIN] + ['production-chain'])

    def test_sampling_covers_tiers(self):
        rows = [{'tier': t, 'filename': str(i)} for i, t in enumerate(['easy', 'easy', 'tree', 'toxic'])]
        self.assertEqual([r['tier'] for r in sample_rows(rows, 3)], ['easy', 'tree', 'toxic'])

    def test_cost_includes_failed_and_missing_attempts(self):
        records = [{'ok': False, 'attempts': [{'metrics': {'cost': '0.03'}}, {}]}]
        self.assertEqual(spending(records, .1), {'recorded_usd': .03, 'unknown_cost_attempts': 1, 'recorded_plus_reserve_usd': .13})

    def test_failures_count_against_effective_accuracy(self):
        score = {key: True for key in ('top1_species', 'top3_species', 'top1_genus', 'top3_genus')}
        rows = [{'ok': True, 'score': score, 'tier': 'easy', 'elapsed_s': 2},
                {'ok': False, 'tier': 'easy', 'elapsed_s': 4}]
        result = summarize(rows, .1)
        self.assertEqual(result['effective_top1_species'], .5)
        self.assertEqual(result['completed_top1_species'], 1)
        rows[0].pop('score')
        self.assertIsNone(summarize(rows, .1)['effective_top1_species'])

    async def test_taxonomy_failure_is_not_an_unmatched_name(self):
        gbif = AsyncMock()
        gbif.match.side_effect = ValueError('lookup unavailable')
        with self.assertRaises(ValueError):
            await score_row(None, gbif, 'Monstera deliciosa', [])

    async def test_synonyms_and_genus_only_matches(self):
        gbif = AsyncMock()
        gbif.match.side_effect = [
            {'speciesKey': 1, 'genus': 'Dracaena'},
            {'speciesKey': 1, 'genus': 'Dracaena', 'matchType': 'EXACT'},
            {'genus': 'Dracaena', 'matchType': 'HIGHERRANK'},
        ]
        result = await score_row(None, gbif, 'Dracaena trifasciata', [
            {'scientific_name': 'Sansevieria trifasciata'}, {'scientific_name': 'Dracaena'}])
        self.assertTrue(result['top1_species'])
        self.assertFalse(result['ranked'][1]['species_hit'])
        self.assertFalse(result['any_unmatched_name'])

class PipelineTraceTests(unittest.IsolatedAsyncioTestCase):
    async def test_isolated_model_retains_raw_metrics_on_validation_failure(self):
        import asyncio
        from unittest.mock import patch
        from backend.app import main
        from backend.app.errors import EachlabsError
        provider = main.CHAIN[-1]
        record = {'output': {'is_plant': 'wrong'}, 'metrics': {'cost': .02}, 'id': 'test-id'}
        attempts = []
        with patch.object(main._client, 'predict_json', AsyncMock(return_value=(record['output'], record))) as predict:
            with self.assertRaises(EachlabsError):
                await main._run_chain(None, 'identify', lambda p: {}, deadline=asyncio.get_running_loop().time() + 20,
                                      providers=[provider], attempts=attempts)
        self.assertEqual(predict.await_count, 1)
        self.assertEqual(predict.call_args.args[1], provider.slug)
        self.assertEqual(attempts[0]['metrics']['cost'], .02)
        self.assertEqual(attempts[0]['error_kind'], 'invalid_response')
        self.assertEqual(attempts[0]['prediction_id'], 'test-id')

    async def test_parser_failure_retains_billing_metadata(self):
        from unittest.mock import patch
        from backend.app.eachlabs import EachlabsClient
        from backend.app.errors import EachlabsError
        client = EachlabsClient('test-key')
        record = {'output': 'broken JSON', 'metrics': {'cost': .04}}
        with patch.object(client, 'predict', AsyncMock(return_value=record)):
            with self.assertRaises(EachlabsError) as caught:
                await client.predict_json(None, 'test-model', {})
        self.assertEqual(caught.exception.record, record)

    async def test_shared_identify_pipeline_normalizes_upload(self):
        import io
        from unittest.mock import patch
        from PIL import Image
        from fastapi import UploadFile
        from backend.app import main
        image = io.BytesIO()
        Image.new('RGB', (2048, 1024), 'green').save(image, 'PNG')
        image.seek(0)
        provider = main.CHAIN[-1]
        record = {'output': {'is_plant': False, 'image_quality': 'good', 'candidates': []}, 'metrics': {'cost': .01}}
        upload_mock = AsyncMock(return_value='https://example.test/image')
        predict_mock = AsyncMock(return_value=(record['output'], record))
        attempts = []
        with patch.object(main._client, 'upload_image', upload_mock), patch.object(main._client, 'predict_json', predict_mock):
            response = await main.identify_image(UploadFile(image, filename='test.png'), providers=[provider], attempts=attempts)
        normalized = Image.open(io.BytesIO(upload_mock.call_args.args[1]))
        self.assertEqual(normalized.size, (1024, 512))
        self.assertEqual(normalized.format, 'JPEG')
        self.assertEqual(response['meta']['model'], provider.slug)
        self.assertFalse(response['meta']['fallback'])
        self.assertEqual(len(attempts), 1)
