"""Bounded, metric-specific discovery. A failed search is not proof of non-publication."""
import calendar
import re


def routes(category, month, metrics):
    year, mon = map(int, month.split('-'))
    period = f'{year}年{mon}月'
    groups = {}
    for mid, section, label, unit, basis in metrics:
        if mid == 'building':
            continue  # Requires verified cumulative inputs, not another monthly headline.
        if mid in ('output','outputYtd','outputPriorYear'):
            group, term = 'production', ('电解铜产量 SMM' if category == 'copper' else '原铝产量' if category == 'aluminum' else '粗钢产量')
            domains = ['smm.cn','mysteel.com'] if category == 'copper' else ['stats.gov.cn','gov.cn']
        elif mid == 'stock':
            group, term = 'inventory', {'copper':'铜 社会库存 月末','aluminum':'铝锭 社会库存 月末','iron':'重点钢铁企业 钢材库存 月末'}[category]
            domains = ['smm.cn','mysteel.com'] if category != 'iron' else ['chinaisa.org.cn','cnfin.com']
        elif mid in ('oreImport','refinedImport','refinedExport','steelImport','steelExport','primaryImport','primaryExport','aluminumExport'):
            group = 'trade'
            term = {'copper':'铜矿砂 精矿 精炼铜 进口 出口 海关分项', 'aluminum':'原铝 未锻轧铝及铝材 进口 出口 海关', 'iron':'钢材 铁矿砂 进口 出口 海关'}[category]
            domains = ['customs.gov.cn','smm.cn' if category != 'iron' else 'mysteel.com']
        elif mid in ('pmi','newOrders'):
            group, term, domains = 'pmi', '制造业PMI 新订单指数', ['stats.gov.cn','gov.cn']
        elif mid.startswith('power'):
            group, term, domains = 'power', '山东 蒙西 新疆 云南 代理购电价格 公告', ['energydc.cn','sgcc.com.cn']
        elif mid == 'alumina':
            group, term, domains = 'alumina', '氧化铝 国内现货 月均价格 月报', ['ccmn.cn','smm.cn']
        elif mid == 'smeltingProfit':
            group, term, domains = 'smelting', '电解铜 现货冶炼 模型 盈亏 SMM', ['smm.cn','mysteel.com']
        elif mid in ('price','cokingCoal','coke'):
            group, term, domains = 'price', {'copper':'电解铜','aluminum':'铝锭','iron':'热轧板卷 焦煤 焦炭'}[category] + ' 下旬 流通领域价格', ['stats.gov.cn','gov.cn']
        elif mid == 'applianceRetail':
            group, term, domains = 'retail', '家用电器 音像器材 零售额', ['stats.gov.cn','gov.cn']
        else:
            group, term, domains = 'industrial', '汽车 集成电路 金属切削机床 产量 工业生产', ['stats.gov.cn','gov.cn']
        entry = groups.setdefault(group, {'group':group,'metricIds':[],'term':term,'domains':domains})
        entry['metricIds'].append(mid)
    priority = ['production','inventory','trade','alumina','power','smelting','price','industrial','retail','pmi']
    return [dict(groups[key], queries=[f'{period} {groups[key]["term"]} site:{d}' for d in groups[key]['domains']])
            for key in priority if key in groups]


def followup_jobs(category, month, metrics, missing, maximum=6):
    selected = [row for row in metrics if row[0] in missing]
    # Three most important missing groups, each with primary and backup provider.
    groups = routes(category, month, selected)[:maximum // 2]
    return [dict(group, query=query, tier='primary' if index == 0 else 'backup')
            for group in groups for index,query in enumerate(group['queries'])]


def missing_details(category, month, metrics, checked, attempts, searches):
    labels = {row[0]:row[2] for row in metrics}
    details = []
    for mid in checked['missing']:
        matching = [a for a in attempts if a.get('category') == category and mid in a.get('metricIds',[])]
        queries = [s for s in searches if s.get('category') == category and mid in s.get('metricIds',[])]
        reasons = [x['reason'] for x in checked['rejected'] if x.get('id') == mid]
        if mid == 'building':
            status = 'calculation_required'
        elif any('口径' in r or '累计' in r or '单位' in r for r in reasons):
            status = 'definition_mismatch'
        elif any(a.get('httpStatus') in (401,403) or a.get('status') == 'access_limited' for a in matching) and not any(a.get('status') == 'retrieved' for a in matching):
            status = 'access_limited'
        elif matching and not any(a.get('status') == 'retrieved' for a in matching):
            status = 'unreadable'
        elif reasons:
            status = 'wrong_period' if any('统计期不符' in r for r in reasons) else 'evidence_incomplete'
        else:
            status = 'not_found_in_checked_sources'
        details.append({'id':mid,'label':labels[mid],'status':status,'publicationState':'unconfirmed',
                        'reason':'累计差分仍需核验四项输入' if mid == 'building' else '；'.join(reasons) or '在本次有限补查中未取得通过核验的目标月份数值，不能据此断言尚未发布',
                        'attemptedUrls':list(dict.fromkeys(a['url'] for a in matching)),
                        'queries':[q['query'] for q in queries]})
    return details
