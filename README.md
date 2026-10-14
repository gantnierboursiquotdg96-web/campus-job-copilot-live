# 校招求职助手 实时信息库版

根据简历和求职偏好，每次推荐前读取持续更新的飞书校招信息库，给出机会、匹配理由、差距与待核实项。用户明确选择后，再生成七天行动计划并管理本地投递记录。

本项目基于 [duuhuang-ai/campus-job-copilot](https://github.com/duuhuang-ai/campus-job-copilot) 修改，保留原作者MIT许可证。主要改动是使用实时飞书数据源，完整分页及版本校验，并提供买家安装与授权说明。

## 通过仓库安装

把本仓库页面地址交给支持本地Skill和命令执行的AI工具：

> 请从这个仓库安装 campus-job-copilot 实时版。检查Python与飞书CLI依赖，协助我用自己的飞书账号配置和授权，然后读取最新信息库。

Codex用户也可以把完整仓库下载到 `~/.codex/skills/campus-job-copilot/`，确保该目录内直接存在 `SKILL.md`、`agents/`、`scripts/`、`references/` 和 `assets/`。下一轮对话确认Skill被发现。其他AI工具按其技能安装机制操作；本项目未验证WorkBuddy或RedsKill兼容性。

## 首次配置

需要Python 3.10+、Node.js/npm、飞书CLI，以及源表阅读权限。完整步骤见 [安装与授权](references/live-setup.md)。

买家使用自己的CLI应用和飞书登录态；仓库不包含卖家密钥。安装Skill并不自动完成飞书授权。浏览器能看到源表，也仍需确认CLI应用权限和资源ACL允许读取。

## 开始使用

上传简历并说：

> 使用 $campus-job-copilot，先读取最新信息库。我是2027届工商管理本科，目标电商运营，优先北京、上海、广州，可以接受笔试。请分析附件简历并推荐机会，等我选定后再制定七天计划。

选定后提供机会ID：

> 我选择这些机会ID：……。请重新核查最新记录后制定七天计划，并建立本地投递记录。

## 数据与隐私

- [招聘信息库](https://rcn1ey8vkhdz.feishu.cn/base/VlEDbwedIaZxoqseDAUccMB6nQd?table=tblu45c5VOTkblOj&view=vewSA2MxfV)在 `assets/live-source.json` 固定；只读取招聘表，不向表内上传简历或写入数据。
- 推荐前每次重新完整分页读取；版本或总数不一致、权限或网络失败时停止，不回退到旧岗位数据。
- 卖家更新同一表内招聘记录，买家无需更新Skill；代码、字段ID或来源表变更时需更新安装版本。GitHub代码更新不会自动更新本地Skill。
- 日期含糊、届别冲突、多岗位多城市记录和具体JD要求都需核实。完整读取不等于所有岗位当前开放；分数不代表录用概率。
- 个人画像、读取快照、报告和投递CSV保存在独立本地工作区，不写入安装目录、不提交到仓库。
- [个人投递模板](https://rcn1ey8vkhdz.feishu.cn/base/M1ZdbxaMrar1C3sWXD3cXfOinBc)可创建副本手动使用，与Skill本地记录不会自动双向同步。

## 验证范围

修改版本已在卖家账号和Codex环境两次完整读取8314条招聘记录，核对分页版本和总数。独立买家账号及不同租户权限仍需端到端验收。脚本只用Python标准库，无第三方Python运行依赖。

## 许可证

代码与Skill文本遵循仓库保留的 [MIT许可证](LICENSE)。招聘数据及企业名称、公告链接等第三方内容的权利归各原发布方；本仓库不打包全量招聘数据库。
