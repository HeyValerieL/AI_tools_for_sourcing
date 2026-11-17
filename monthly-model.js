(function(root){
'use strict';
const DAY=86400000;
function date(s){const n=Date.parse(s+'T00:00:00Z');if(!/^\d{4}-\d{2}-\d{2}$/.test(s)||!Number.isFinite(n)||new Date(n).toISOString().slice(0,10)!==s)throw Error('Invalid date');return n;}
function intervalAggregate(month,records,kind){
if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)||!['rate','flow'].includes(kind))throw Error('Invalid aggregation');
const start=date(month+'-01'),[year,m]=month.split('-').map(Number),end=Date.UTC(year,m,1),expectedDays=(end-start)/DAY,seen=new Set();let sum=0,crossMonth=false;
for(const r of records){const a=date(r.start),b=date(r.end)+DAY;if(b<=a||!Number.isFinite(r.value)||r.value<0||(kind==='rate'&&r.value>100))throw Error('Invalid interval or value');
const left=Math.max(a,start),right=Math.min(b,end);if(left>=right)continue;
if(a<start||b>end)crossMonth=true;
for(let d=left;d<right;d+=DAY){if(seen.has(d))throw Error('Overlapping intervals: deduplicate before aggregation');seen.add(d);}
sum+=kind==='rate'?r.value*(right-left)/DAY:r.value*(right-left)/(b-a);}
const coverageDays=seen.size,missing=coverageDays!==expectedDays;
return {month,value:missing?null:kind==='rate'?sum/expectedDays:sum,method:kind==='rate'?'monthly_average':'monthly_total',status:missing?'missing':kind==='flow'&&crossMonth?'estimated':'verified',coverageDays,expectedDays,missingReason:missing?'Incomplete calendar-month coverage':null,caveat:kind==='flow'&&crossMonth?'Uniform daily allocation across month boundaries':null};
}
root.MonthlyModel={intervalAggregate};if(typeof module!=='undefined')module.exports=root.MonthlyModel;
})(typeof window==='undefined'?globalThis:window);
