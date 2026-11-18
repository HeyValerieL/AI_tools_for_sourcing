import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('monthly', Path(__file__).parents[1] / 'monthly.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
URL = 'https://www.stats.gov.cn/sj/zxfb/202611/example.html'
PAGE = '发布日期2026-11-16。2026年10月份工业生产。原铝产量385万吨，同比增长1.8%。汽车产量304.5万辆，同比下降7.7%。制造业PMI49.3%。'


def observation(**changes):
    value = {'id': 'output', 'value': 385, 'unit': '万吨/月', 'period': '2026-10',
             'basis': 'monthly', 'definition': '国家统计局原铝产量', 'url': URL,
             'title': '10月工业生产', 'publishedAt': '2026-11-16',
             'quote': '原铝产量385万吨，同比增长1.8%', 'periodEvidence': '2026年10月份工业生产',
             'yoy': 1.8, 'yoyQuote': '原铝产量385万吨，同比增长1.8%',
             'mom': None, 'momQuote': '', 'comparisonDefinition': '官方可比口径'}
    value.update(changes)
    return value


def analysis(**changes):
    value = {'trend': '待观察', 'summary': '供给增长，等待价格验证', 'shortTerm': '观察库存',
             'mediumTerm': '观察订单', 'supportingEvidenceIds': ['output'],
             'conflictingEvidenceIds': [], 'actions': [{'title': '分批确认交付',
             'action': '在订单确定时分批确认交期', 'evidenceIds': ['output'],
             'adjustWhen': '供应转紧时提前锁量'}], 'riskNote': '结合实际订单安排。'}
    value.update(changes)
    return value


class ValidationTests(unittest.TestCase):
    def check(self, item, page=PAGE):
        return m.validate_research('aluminum', '2026-10', {'observations': [item]}, {URL}, fetch=lambda _: page)

    def test_real_quote_and_statistical_month(self):
        result = self.check(observation())
        self.assertEqual(len(result['facts']), 1)
        self.assertEqual(result['facts'][0]['yoy'], 1.8)

    def test_rejects_invalid_source_numbers_units_and_periods(self):
        for changes in [{'value': 999}, {'period': '2026-09'}, {'unit': '吨/月'},
                        {'url': 'https://attacker.example/'}, {'publishedAt': '2099-01-01'},
                        {'quote': '原铝产量999万吨，同比增长1.8%'}, {'id': 'unknown'},
                        {'periodEvidence': '2025年10月份工业生产'}, {'value': float('nan')}]:
            with self.subTest(changes=changes):
                self.assertFalse(self.check(observation(**changes))['facts'])

    def test_rejects_page_without_publication_date(self):
        self.assertFalse(self.check(observation(), PAGE.replace('2026-11-16', ''))['facts'])

    def test_missing_year_in_period_is_not_verified(self):
        self.assertFalse(self.check(observation(periodEvidence='10月份工业生产'))['facts'])

    def test_unconfirmed_change_is_removed(self):
        self.assertIsNone(self.check(observation(yoy=8.8))['facts'][0]['yoy'])

    def test_no_search_citation_no_acceptance(self):
        result = m.validate_research('aluminum', '2026-10', {'observations':[observation()]}, set(), fetch=lambda _: PAGE)
        self.assertFalse(result['facts'])

    def test_duplicate_metric_not_duplicated(self):
        result = m.validate_research('aluminum', '2026-10', {'observations':[observation(), observation()]}, {URL}, fetch=lambda _: PAGE)
        self.assertEqual(len(result['facts']), 1)

    def test_hostname_boundary(self):
        for url in ['http://stats.gov.cn/', 'https://stats.gov.cn.evil.example/',
                    'https://stats.gov.cn@evil.example/', 'https://stats.gov.cn:8888/']:
            self.assertFalse(m.allowed(url))
        self.assertTrue(m.allowed(URL))

    def test_price_requires_final_ten_days(self):
        fact = observation(id='price', unit='元/吨', basis='month_end_proxy', period='2026-10-31')
        self.assertFalse(self.check(fact)['facts'])

    def test_previous_ten_days_not_treated_as_monthly_change(self):
        fact = observation(id='price', unit='元/吨', basis='month_end_proxy', period='2026-10-31',
                           periodEvidence='2026年10月21—31日', mom=1.8, momQuote='原铝产量385万吨，同比增长1.8%')
        result = self.check(fact, PAGE + '2026年10月21—31日')['facts'][0]
        self.assertIsNone(result['mom'])
        self.assertIsNone(result['yoy'])

    def test_comparison_only_for_same_definition(self):
        current = observation(yoy=None)
        base = observation(value=350, period='2026-09')
        result = m.compare([current], [base])[0]
        self.assertAlmostEqual(result['mom'], 10)
        different = observation(yoy=None)
        m.compare([different], [dict(base, definition='不同统计样本')])
        self.assertIsNone(different['mom'])

    def test_annual_is_not_compared_to_monthly(self):
        fact = observation(id='outputPriorYear', basis='annual', period='2025', yoy=None)
        self.assertIsNone(m.compare([fact], [observation()])[0]['mom'])

    def test_index_change_uses_percentage_points(self):
        fact = observation(id='pmi', value=50, basis='index', unit='%', yoy=None)
        base = dict(fact, value=49, period='2026-09')
        self.assertEqual(m.compare([fact], [base])[0]['mom'], 1)

    def test_analysis_requires_existing_evidence_and_conditions(self):
        for candidate in [analysis(supportingEvidenceIds=['fake']), analysis(supportingEvidenceIds=[]),
                          analysis(actions=[]), analysis(actions=[{'evidenceIds':['fake'], 'adjustWhen':'等待'}]),
                          analysis(actions=[{'evidenceIds':['output'], 'adjustWhen':''}]), analysis(trend='上行')]:
            with self.assertRaises(ValueError):
                m.validate_analysis(candidate, [observation()], [])
        self.assertEqual(m.validate_analysis(analysis(), [observation()], [])['trend'], '待观察')

    def test_no_secret_no_network(self):
        with patch.dict(os.environ, {}, clear=True), patch('urllib.request.urlopen') as network:
            with self.assertRaises(ValueError):
                m.Client()
            network.assert_not_called()

    def test_api_error_reports_cause_without_secrets(self):
        error = m.api_error(429, json.dumps({'error': {'code':'insufficient_quota', 'message':'secret-account-data'}}))
        self.assertIn('insufficient_quota', str(error))
        self.assertNotIn('secret-account-data', str(error))
        unknown = m.api_error(429, json.dumps({'error': {'code':'secret-sensitive-value', 'message':'private'}}))
        self.assertNotIn('secret-sensitive-value', str(unknown))

    def test_api_failure_stops_remaining_paid_calls(self):
        calls = []
        class QuotaClient:
            usage = []
            @property
            def calls(self): return len(calls)
            def request(self, *args, **kwargs):
                calls.append(1)
                raise m.api_error(429, '{"error":{"code":"insufficient_quota"}}')
        with tempfile.TemporaryDirectory() as folder, patch.object(m, 'Client', QuotaClient):
            with self.assertRaises(ValueError):
                m.run('2026-10', Path(folder))
            self.assertEqual(len(calls), 1)

    def test_dates_and_year_boundary(self):
        self.assertEqual(m.previous_month('2026-01'), '2025-12')
        self.assertEqual(m.expected_period('2024-02', 'month_end_proxy'), '2024-02-29')
        self.assertEqual(m.expected_period('2026-10', 'ytd'), '2026-01/2026-10')
        for month in ['not-a-month', '2099-12', '2026-13']:
            with self.assertRaises(ValueError):
                m.target_month(month)

    def test_end_to_end_draft_does_not_touch_historical_data(self):
        class FakeClient:
            calls = 0
            usage = []
            def request(self, instructions, payload, schema, search=False):
                self.calls += 1
                if search:
                    return {'observations': [], 'policies': [], 'missing': []}, set()
                return analysis(), set()
        checked = {'facts':[dict(observation(), label='原铝产量'), dict(observation(id='auto'), label='汽车产量'), dict(observation(id='pmi'), label='制造业PMI')],
                   'policies':[], 'missing':[], 'rejected':[], 'sourceHashes':{URL:'example'}}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            (root / 'data/monthly-analysis.json').write_text('historical', encoding='utf-8')
            with patch.object(m, 'Client', FakeClient), patch.object(m, 'validate_research', side_effect=lambda *args: copy.deepcopy(checked)):
                report = m.run('2026-10', root)
            self.assertEqual(len(report['categories']), 3)
            self.assertTrue((root / 'automation/output/review.md').exists())
            self.assertEqual((root / 'data/monthly-analysis.json').read_text(), 'historical')
            public = json.loads((root / 'data/ai-monthly.json').read_text(encoding='utf-8'))
            self.assertIn('2026-10', public['reports'])

    def test_all_failed_does_not_write_public_report(self):
        class FailedClient:
            calls = 0
            usage = []
            def request(self, *args, **kwargs):
                raise RuntimeError('来源暂不可用')
        with tempfile.TemporaryDirectory() as folder, patch.object(m, 'Client', FailedClient):
            root = Path(folder)
            with self.assertRaises(ValueError):
                m.run('2026-10', root)
            self.assertFalse((root / 'data/ai-monthly.json').exists())
            self.assertTrue((root / 'automation/output/review.md').exists())


if __name__ == '__main__':
    unittest.main()
