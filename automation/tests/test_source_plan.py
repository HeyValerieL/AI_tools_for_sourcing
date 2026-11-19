import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_plan import plan


class SourcePlanTests(unittest.TestCase):
    def test_exact_month_first_no_historical_values(self):
        def source(month):
            return {'url':'https://www.stats.gov.cn/'+month,'recordedMonths':[month],
                    'title':month,'metricIds':['output']}
        catalog = {'rules':[], 'sources':{'old':source('2026-09'),
                   'current':source('2026-10'),'future':source('2026-11')},
                   'categories':{'aluminum':{'metrics':{'output':{
                       'sourceIds':['old','future','current'],'unit':'万吨/月'}}}}}
        result = plan('aluminum','2026-10',catalog)
        self.assertEqual(result['seeds'][0]['url'],'https://www.stats.gov.cn/2026-10')
        self.assertEqual(len(result['seeds']),1)
        self.assertNotIn('historicalReferences',result)

    def test_real_catalog_covers_all_categories(self):
        for cat in ('aluminum','copper','iron'):
            result = plan(cat,'2026-10')
            self.assertTrue(result['seeds'])
            self.assertIn('calculation',result['metrics']['building'])
            self.assertIn('newOrders',result['metrics'])
