"""Transfer the existing, human-reviewed source ledger; never relabel old values as new."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, urldefrag

ROOT = Path(__file__).resolve().parent.parent


def build(root=ROOT):
    load = lambda name: json.loads((root / name).read_text(encoding='utf-8'))
    config = load('automation/config.json')
    aluminum = load('data/monthly-analysis.json')
    materials = load('data/materials-monthly.json')
    catalog = {'schemaVersion':1, 'origin':'Existing workbench manually reviewed source ledgers',
               'rules':['旧值仅作历史对照；新月份必须重新读取对应原文。',
                        '同一指标固定来源、统计期、单位和规格；换来源需保留差异并人工确认。',
                        '累计差分由程序计算并标估算；缺少输入不推算；1—2月合并值不拆月。',
                        '月末价格代理为当月下旬均价；库存为期末存量；不把上期旬比当月环比。',
                        '未知发布日期保留未知；不能编造日期；发布日不等于统计月份。'],
               'sources':{}, 'categories':{}}
    aliases = {'socialIngot':'stock','refined':'output','smeltLoss':'smeltingProfit',
               'crude':'output','crudeYtd':'outputYtd','crudePriorYear':'outputPriorYear'}

    def add(source, category, month='', key=''):
        if not isinstance(source, dict) or not (source.get('url') or '').startswith('https://'):
            return None
        url = urldefrag(source['url'])[0]
        sid = 's' + hashlib.sha256(url.encode()).hexdigest()[:12]
        entry = catalog['sources'].setdefault(sid, {
            'url':url, 'title':source.get('title','既有来源'), 'host':urlsplit(url).hostname,
            'format':'pdf' if '.pdf' in url.lower() else 'html',
            'publishedAt':source.get('published'), 'access':source.get('access','public'),
            'method':source.get('method',''), 'caveat':source.get('caveat',''),
            'categories':[], 'recordedMonths':[], 'sourceKeys':[], 'metricIds':[],
            'reviewStatus':'previous_manual_source_record_not_revalidated_by_catalog_export'})
        for field, value in [('categories',category), ('recordedMonths',month), ('sourceKeys',key)]:
            if value and value not in entry[field]: entry[field].append(value)
        return sid

    def scan(value, category, month='', key=''):
        if isinstance(value, dict):
            month = value.get('month', month)
            if value.get('url'): add(value, category, month, key)
            for field in ('sourceUrl', 'previousUrl', 'policyUrl'):
                if isinstance(value.get(field), str):
                    add({'url':value[field], 'title':value.get('title', key),
                         'method':value.get('method','')}, category, month, key)
            for name, child in value.items():
                scan(child, category, name if re.fullmatch(r'\d{4}-\d{2}', name) else month, name)
        elif isinstance(value, list):
            for child in value: scan(child, category, month, key)

    bindings = {
        'price':['price'], 'output':['nbs'], 'outputYtd':['nbs'], 'outputPriorYear':['previousYearOutput','annual'],
        'building':['property','propertyBase9','propertyBase10'], 'auto':['nbs'], 'electronics':['nbs'],
        'machineTools':['nbs'], 'pig':['nbs'], 'applianceRetail':['retail'],
        'pmi':['pmi','pmiBase'], 'newOrders':['pmi','pmiBase'],
        'alumina':['oxide','monthly'], 'stock':['socialMonthEnd','inventory'],
        'gridInvestment':['gridDemand'], 'lme3mAvg':['review'],
        'steelExport':['trade','tradeRate'], 'steelImport':['trade'], 'steelNetExport':['trade'],
        'aluminumExport':['tradeLatest','tradeHistory'], 'aluminumImport':['importHistory'],
        'primaryImport':['tradeAnalysis','importHistory'], 'primaryExport':['tradeAnalysis','tradeHistory'],
        'oreImport':['trade','oreImport'], 'refinedImport':['refinedImport'], 'refinedExport':['refinedExport'],
        'cokingCoal':['price'], 'coke':['price'], 'smeltingProfit':['smmProduction'],
    }
    for category in config['categories']:
        data = aluminum if category == 'aluminum' else materials['categories'][category]
        scan(data,category)
        if category == 'aluminum':
            observations = load('data/monthly-observations.json')['observations']
            for item in observations:
                add({'url':item['sourceUrl'],'title':'国家统计局 · 流通领域下旬价格','published':item.get('publishedAt')},category,item['month'],'price')
            scan(load('data/monthly-sources.json'),category)
        profiles = {}
        for row in config['categories'][category]['metrics']:
            mid, section, label, unit, basis = row
            keys = bindings.get(mid, [])
            if category == 'copper' and mid in ('output','outputYtd','outputPriorYear'):
                keys = ['smmProduction','productionHistory']  # Preserve SMM series; do not splice NBS.
            if mid.startswith('power'):
                region = {'powerShandong':'山东','powerInnerMongolia':'蒙西','powerXinjiang':'新疆','powerYunnan':'云南'}[mid]
                candidates = [sid for sid,s in catalog['sources'].items() if category in s['categories'] and
                              (region in s['title'] or {'山东':'shandong','蒙西':'mengxi','新疆':'xinjiang','云南':'yunnan'}[region] in s['url'])]
            else:
                candidates = [sid for sid,s in catalog['sources'].items() if category in s['categories'] and set(keys) & set(s['sourceKeys'])]
            profiles[mid] = {'label':label,'section':section,'unit':unit,'basis':basis,'sourceIds':candidates,
                             'method':'cumulative_difference_estimate' if mid == 'building' else basis,
                             'missingPolicy':'记录来源失败原因并留空；不得搬用上月值'}
            if mid == 'building':
                profiles[mid]['calculation'] = {
                    'formula':'current_ytd - previous_month_ytd',
                    'yoyFormula':'((current_ytd - previous_month_ytd)/(prior_year_ytd - prior_year_previous_ytd)-1)*100',
                    'inputs':['同年本月累计','同年上月累计','上年同月累计','上年上月累计'],
                    'caveat':'跨发布版累计差分是估算；保留每个输入来源、年份、统计月、单位，缺值不算。'}
            for sid in candidates:
                if mid not in catalog['sources'][sid]['metricIds']: catalog['sources'][sid]['metricIds'].append(mid)
        # Also bind exact historic metric sources (including those outside today's active list).
        history = []
        for month,d in data['months'].items():
            sources = (data.get('sources',{}) | d.get('sources',{}))
            for module in d['modules']:
                for item in module.get('metrics',[]):
                    mid = aliases.get(item['id'],item['id'])
                    sid = add(sources.get(item.get('source'),{}), category,month,item.get('source',''))
                    if sid and mid in profiles and sid not in profiles[mid]['sourceIds']:
                        profiles[mid]['sourceIds'].append(sid)
                    if sid and mid in profiles and mid not in catalog['sources'][sid]['metricIds']:
                        catalog['sources'][sid]['metricIds'].append(mid)
                    history.append({'id':mid,'recordedMonth':month,'label':item['label'],'value':item.get('value'),
                                    'unit':item.get('unit'),'sourceId':sid,'method':item.get('method'),
                                    'calculation':item.get('calculation'),'caveat':item.get('caveat'),
                                    'use':'historical_reference_only'})
        catalog['categories'][category] = {'name':config['categories'][category]['name'],
                                           'metrics':profiles,'historicalReferences':history}
    for source in catalog['sources'].values():
        for key in ('categories','recordedMonths','sourceKeys','metricIds'): source[key].sort()
    (root/'automation/source-catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines = ['# 已有来源同步清单','', '由原工作台来源台账导出，供自动采集与DeepSeek共同使用。历史数字不作为新月份采集结果。','']
    for category,data in catalog['categories'].items():
        lines += ['## '+data['name'],'','|指标|口径与单位|既有来源|','|---|---|---|']
        for mid,metric in data['metrics'].items():
            links = []
            ordered = sorted(metric['sourceIds'], key=lambda sid:max(catalog['sources'][sid]['recordedMonths'] or ['']),reverse=True)
            for sid in ordered[:3]:
                source = catalog['sources'][sid]
                links.append('['+source['title'].replace('|','／')+']('+source['url']+')')
            lines.append('|'+metric['label']+'|'+metric['basis']+' · '+metric['unit']+'|'+'；'.join(links or ['现有台账无直接来源，按固定提供方补查'])+'|')
        lines += ['']
    lines += ['## 运行规则',''] + ['- '+rule for rule in catalog['rules']]
    (root/'automation/SOURCES.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return catalog


if __name__ == '__main__':
    data = build()
    print('Source catalog:',len(data['sources']),'sources;',sum(len(c['metrics']) for c in data['categories'].values()),'active metrics')
