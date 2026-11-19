import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from discovery import followup_jobs, missing_details


class DiscoveryTests(unittest.TestCase):
    def test_missing_copper_groups_use_target_month_then_backup(self):
        rows = [[mid,'supply',mid,'万吨/月','monthly'] for mid in
                ['output','outputYtd','stock','oreImport','refinedImport','refinedExport','building','auto']]
        jobs = followup_jobs('copper','2026-10',rows,[r[0] for r in rows if r[0]!='auto'])
        self.assertEqual(len(jobs),6)
        self.assertEqual([j['tier'] for j in jobs],['primary','backup']*3)
        self.assertIn('site:smm.cn',jobs[0]['query'])
        self.assertIn('site:mysteel.com',jobs[1]['query'])
        self.assertTrue(all('2026年10月' in j['query'] for j in jobs))
        self.assertFalse(any('building' in j['metricIds'] or 'auto' in j['metricIds'] for j in jobs))

    def test_no_result_is_not_reported_as_not_published(self):
        rows = [['stock','demand','社会库存','万吨','month_end']]
        d = missing_details('copper','2026-10',rows,{'missing':['stock'],'rejected':[]},[],[])[0]
        self.assertEqual(d['publicationState'],'unconfirmed')
        self.assertEqual(d['status'],'not_found_in_checked_sources')

    def test_access_failure_is_specific_to_metric(self):
        rows = [['stock','demand','库存','万吨','month_end'],['building','demand','竣工','万平方米/月','monthly']]
        attempts=[{'url':'https://news.smm.cn/example','category':'copper','metricIds':['stock'],
                   'status':'unreadable','httpStatus':403}]
        d=missing_details('copper','2026-10',rows,{'missing':['stock','building'],'rejected':[]},attempts,[])
        self.assertEqual(d[0]['status'],'access_limited')
        self.assertEqual(d[1]['status'],'calculation_required')
