(() => {
  'use strict';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const names = {aluminum:'铝', copper:'铜', iron:'钢材'};
  const sections = {price:'行情价格', supply:'供给与政策', demand:'需求与库存', inputs:'原材料与能源', macro:'宏观与贸易'};
  const panel = document.createElement('section');
  panel.id = 'ai-monthly'; panel.className = 'ai-monthly'; panel.hidden = true;
  document.querySelector('main')?.before(panel);
  let data, selectedMonth = '';
  const category = () => ({steel:'iron'}[document.body.dataset.category] || document.body.dataset.category || 'aluminum');
  const url = value => { try { const u = new URL(value); return u.protocol === 'https:' ? escape(u.href) : '#'; } catch { return '#'; } };
  const source = fact => '<a href="' + url(fact.url) + '" target="_blank" rel="noopener noreferrer">' + escape(fact.title || fact.label) + ' ↗</a>';
  const number = value => Number.isFinite(value) ? value.toLocaleString('zh-CN', {maximumFractionDigits:4}) : '—';
  function render() {
    if (!data) return;
    const cat = category();
    const months = Object.keys(data.reports).filter(m => data.reports[m].categories?.[cat]?.analysis).sort().reverse();
    if (!months.length) { panel.hidden = true; return; }
    if (!months.includes(selectedMonth)) selectedMonth = months[0];
    const report = data.reports[selectedMonth].categories[cat], a = report.analysis;
    const byId = Object.fromEntries([...report.facts, ...report.policies].map(f => [f.id, f]));
    const refs = ids => ids.filter(id => byId[id]).map(id => source(byId[id])).join(' · ');
    panel.hidden = false;
    panel.innerHTML = '<div class="section-title"><div><p class="eyebrow">MONTHLY RESEARCH</p><h2>' + names[cat] + ' · 月度研究与采购行动</h2></div><label>统计月份 <select aria-label="AI月报月份">' + months.map(m => '<option' + (m === selectedMonth ? ' selected' : '') + '>' + m + '</option>').join('') + '</select></label></div>' +
      '<p class="ai-summary"><strong>' + escape(a.trend) + '</strong> ' + escape(a.summary) + '</p><div class="ai-horizons"><p><b>短期 · 1—3个月</b>' + escape(a.shortTerm) + '</p><p><b>中期 · 3—6个月</b>' + escape(a.mediumTerm) + '</p></div>' +
      '<div class="grid strategy-cards">' + a.actions.map((action, i) => '<article><div class="strategy-top"><span class="strategy-number">0' + (i+1) + '</span><span class="badge">行情应对</span></div><h3>' + escape(action.title) + '</h3><p>' + escape(action.action) + '</p><p class="ai-evidence"><b>本月依据</b>' + refs(action.evidenceIds) + '</p><p><b>调整条件</b>' + escape(action.adjustWhen) + '</p></article>').join('') + '</div>' +
      '<details class="ai-facts"><summary>本月指标与原始依据</summary>' + Object.entries(sections).map(([id, title]) => {
        const facts = report.facts.filter(f => f.section === id);
        return facts.length ? '<h3>' + title + '</h3><div class="ai-fact-grid">' + facts.map(f => '<article><span>' + escape(f.label) + '</span><strong>' + number(f.value) + '</strong><small>' + escape(f.unit) + ' · ' + escape(f.period) + '</small><p>' + (Number.isFinite(f.yoy) ? '同比 ' + number(f.yoy) + (f.basis === 'index' ? ' 个百分点' : '%') : '') + (Number.isFinite(f.mom) ? '　环比 ' + number(f.mom) + (f.basis === 'index' ? ' 个百分点' : '%') : '') + '</p>' + source(f) + '<small>发布 ' + escape(f.publishedAt) + '</small><p>' + escape(f.definition) + '</p><blockquote>' + escape(f.quote) + '</blockquote></article>').join('') + '</div>' : '';
      }).join('') + report.policies.map(p => '<article class="ai-policy"><h3>' + escape(p.title) + '</h3><p>' + escape(p.impact) + '</p>' + source(p) + '</article>').join('') + '</details><p class="ai-note">AI辅助整理，经审核发布。' + escape(a.riskNote) + ' 下方保留历史行情工作台，可按月份回看。</p>';
    panel.querySelector('select').addEventListener('change', e => { selectedMonth = e.target.value; render(); });
  }
  new MutationObserver(() => { selectedMonth = ''; render(); }).observe(document.body, {attributes:true, attributeFilter:['data-category']});
  fetch('./data/ai-monthly.json').then(r => { if (!r.ok) throw Error('月报读取失败'); return r.json(); }).then(value => {data = value; render();}).catch(() => {panel.hidden = true;});
})();
