# 月度数据与采购研究后台

该后台增强现有静态工作台，无需把网页改为服务器应用。正式历史数据继续保留；新采集的研究报告在页面顶部展示，并有独立统计月份。**合并月报PR才发布；采集任务绝不直接推送main。**

## 启用（仓库所有者一次配置）

### DeepSeek（可选，当前接入）

- 在Actions Secrets添加 `DEEPSEEK_API_KEY`，在Variables添加 `DEEPSEEK_MODEL`，填写账户 `/models` 列表中可用的模型，如 `deepseek-v4-pro` 或 `deepseek-flash`。密钥不能发到聊天或放入仓库。
- 有DeepSeek密钥时优先使用DeepSeek，不会自动回退到OpenAI。也可显式设置变量 `AI_PROVIDER=deepseek` 或 `openai`。
- 兼容把DeepSeek模型名填在旧 `OPENAI_MODEL` 变量的情况，但不会把旧GPT模型名传给DeepSeek。
- 独立Search API每品类最多6次搜索，每次4个结果；最多18个白名单来源、每品类最多100000正文字符进入提取模型。原文仍需独立请求核验，模型输出再经过本地JSON字段及业务校验。
- 单次最多6个模型请求、18次独立搜索；搜索与模型均按DeepSeek账户规则计费。运行先检查模型可用性，不记录密钥或余额信息。
- 本实现不使用DeepSeek兼容层不支持的OpenAI `store`、`include`、`max_tool_calls` 参数，也不依赖模型内置搜索来限制调用次数。
- 首次试采通过更新 `automation/run-request.json` 发起；结果仍先到草稿PR，不直接发布。

### OpenAI（保留）

1. 打开仓库 Settings → Secrets and variables → Actions → Secrets，添加 `OPENAI_API_KEY`。只在GitHub密钥框粘贴，不放到聊天、代码或网页。需要可用API额度；建议先在服务商项目里设置用量提醒/限额。
2. 在同一页 Variables 添加 `OPENAI_MODEL`，值为你账户支持联网搜索和结构化输出的模型ID。配置前任务仅运行测试，不发送模型请求。
3. Settings → Actions → General → Workflow permissions：允许 **Read and write permissions**，勾选 **Allow GitHub Actions to create and approve pull requests**。本任务只创建草稿PR，不批准或自动合并。
4. Actions → Monthly sourcing research → Run workflow，第一次指定 `2026-10` 做一次真实试运行。检查下载的 `monthly-review-*` artifact、来源原文、被拦截项与用量。
5. 在 Pull requests 打开月报草稿，核验统计期、口径、来源、采购行动与调整条件。确认后点击 Ready for review 再合并；若无需发布，关闭PR即可。发布后工作台顶部显示月报，历史图表原数据保持可回看。

仓库地址：https://github.com/HeyValerieL/AI_tools_for_sourcing

密钥设置：https://github.com/HeyValerieL/AI_tools_for_sourcing/settings/secrets/actions

变量设置：https://github.com/HeyValerieL/AI_tools_for_sourcing/settings/variables/actions

任务权限：https://github.com/HeyValerieL/AI_tools_for_sourcing/settings/actions

## 调度与费用边界

北京时间每月5、18、25日10:17检查上一个完整月；这是设计的检查点，不保证所有来源当日已发布。手动可指定更早月份补采。

仓库连接也可以通过更新 `automation/run-request.json` 发起一次明确月份的试运行；只有 main 上这个请求文件变化才触发，不会因普通代码或数据更新重复调用模型。该文件不能包含密钥。

每次最多6次模型请求（三品类各一次联网采集、一次分析）；每品类最多6次搜索工具调用、18个网页核验，每请求最多9000输出token。不自动重试付费请求，失败保留报告与旧版，后续检查点补采。限制请求量不等同于硬金额上限，金额由模型、输入长度、搜索调用计费决定；账户预算需自行设置。

GitHub定时任务可能延迟；公共仓库长期无活动时可能暂停，需要在Actions重新启用。运行不依赖个人电脑开机。

## 数据约定与限制

- `automation/config.json` 是三品类固定采集清单、单位、口径和域名白名单。电价关注山东、蒙西、新疆、云南；不把代理购电分项说成铝厂最终电价。
- 来源网页、搜索结果均视为不可信数据；仅允许公开白名单域名，跳转也受限制，不绕过登录/付费墙，不执行网页指令。
- AI联网寻找并提取原文，程序独立请求来源，核对引用、数值、日期、月份和单位；文字匹配不能完全替代经济口径审核。PDF/图片/动态正文尚不自动核验，缺值写入报告，后续可添加授权数据接口或专用解析器。
- 比较值优先用原文明示同比/环比；自行计算仅使用此前已合并、同定义/单位/期间的观测。缺基期不计算；指数变化用百分点。第一轮可能暂时缺少同口径基期，不能确认趋势时输出待观察。
- 不把累计值当单月，不把年度参考当所选月，不把当月下旬代理当全月均价。建筑累计差分暂不自动推算，避免不同发布版累计值误减；可人工核验后扩展。
- 每条采购行动引用通过检查的事实，并给调整条件。未提供企业订单、库存、交期时，不编造锁量比例、库存天数或具体谈判价。
- 输出 `automation/output/draft.json`、`review.md`、`usage.json`，由Actions保存90天；只将通过检查的报告写入PR中的 `data/ai-monthly.json`。失败品类不会覆盖此前已批准内容。
- Vercel副本目前不是该GitHub仓库的自动部署目标；审核后先更新GitHub Pages。若需要两边同步，应把Vercel项目连接同一仓库后再启用自动部署。

## 本地检查

```text
python -m unittest discover -s automation/tests -v
python automation/monthly.py --month 2026-10
```

第二条需要环境变量中的密钥和模型；未配置时在联网前停止。没有把密钥写入任何文件的步骤。

实现依据：[OpenAI联网搜索](https://developers.openai.com/api/docs/guides/tools-web-search)、[结构化输出](https://developers.openai.com/api/docs/guides/structured-outputs)、[GitHub定时事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。
# 固定来源同步

`source-catalog.json` 从原工作台台账导出；`SOURCES.md` 是便于阅读的对应表。
每次提取会向模型传入指标口径、单位、历史来源链接与计算规则，不传历史数值。
DeepSeek 路径先重读最多12个已有链接，再用搜索寻找补充或新月份发布。
统计期与逐字原文核验继续生效，失败记录在 `source-attempts.json`。
修改旧台账或指标清单后运行 `python automation/build_source_catalog.py` 重建目录。
来源目录包含累计差分的四项输入规则；当前自动核验仍不接纳模型自行计算的差分，须人工核验。
PDF、图片和无法读取的网页目前会记录为缺失，不代表已经自动采集成功。
地区电价通过该网站自身使用的公开接口读取公告正文；执行月份独立核验，未标注发布日期时保留未知。
每个品类的来源计划保存在 `source-plan-*.json`，读取失败的 HTTP 状态保存在 `source-attempts.json`，便于复查。

