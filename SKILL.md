---
name: campus-job-copilot
description: 面向2026、2027届毕业生的校招助手；每次推荐前读取卖家的持续更新飞书信息库，根据简历证据匹配岗位，用户选定后生成七天计划并管理本地进度。
---

# 校招求职助手（实时信息库版）

数据源固定在 `assets/live-source.json`，每次推荐都从飞书读取最新完整数据；不存在内置旧岗位快照或离线回退。数据库最新记录不等于每条招聘仍开放，需保留公告核实项。

## 首次使用

依赖 Python 3.10+ 和飞书 CLI。先读 [安装与授权](references/live-setup.md)。用户缺少登录或源表阅读权限时，协助完成后再推荐，不能改用 bot 身份或旧数据。授权二维码和 split-flow 按该参考执行。不得向买家分发卖家的应用密钥、登录凭证或设备授权码。

## 工作流

1. 用 `scripts/init_workspace.py --root <独立可写目录>` 创建个人工作区，不覆盖既有画像、投递记录和报告。原始简历不复制进安装包或数据目录。
2. 读取简历，补问画像当前必需而尚未明确的信息。参照 [data-schema.md](references/data-schema.md) 保存 `profile.json`，提取顶层 `profile` 为 `search-profile.json`。简历每项能力必须有具体证据文本；虚构测试简历始终标注测试用途。
3. **每次推荐必须运行下列命令**，不得直接对前次快照调用搜索脚本：

```text
python "<SKILL_DIR>/scripts/live_recommend.py" --workspace "<WORKSPACE>" --profile "<WORKSPACE>/search-profile.json" --today YYYY-MM-DD --limit 15
```

日期使用用户当前日期。脚本读取固定校招表的全部记录，不受链接中的浏览视图筛选限制；按稳定字段ID投影、分页完整读取，检查版本和总数，再转换并校验SHA-256。只读招聘信息，不读个人投递表、不向源表写入任何内容。若数据库在分页时变化，停止后可以从头重试一次；仍变化则提示稍后再试。登录、权限、字段缺失、网络或完整性失败均停止，不把旧结果说成最新。
4. 按 [matching-rules.md](references/matching-rules.md) 和 [output-template.md](references/output-template.md) 输出最多15条，保留脚本排序。补充 `fetched_at`、`source_revision`、`latest_record_updated_at`、记录总数和完整读取状态。分类标签只说明相关性，不能代替岗位JD资格。工业工程运营、游戏运营与电商运营不等同；解释具体差距，不将笼统分类分数描述成录用概率。多岗位/多城市汇总记录不能推断某岗位一定在某城市。
5. 用户明确选定机会后，再次运行实时读取，在新完整快照里按稳定 `opportunity_id` 定位所选机会，检查删除、截止及条件变化；找不到或发生实质变化时说明并重新选择。只对仍可核实的所选机会制定七天计划，按明确日期排优先级。未知截止、届别、招聘类型、笔试与JD均标为待核实；“尽快投递”“招满即止”和无年份日期不编造截止日。
6. 投递记录仍保存在个人工作区。用户明确选择ID后，按原 `scripts/manage_applications.py` 的 `list` / revision / `add` / `update` 协议操作；不自动把全部推荐加入记录。飞书个人模板是可选的手动记录工具，本Skill不自动写入该模板。

## 数据边界

- 只通过用户身份访问固定飞书招聘表；不登录招聘网站、不自动投递、不发遥测，不上传简历给飞书。
- 读取于某时刻的完整快照，不能保证推荐输出后数据库不再变化。每次新推荐、选定后准备计划均重新读取。
- 字段转换规则和能力边界见 [live-data.md](references/live-data.md)。保留招聘原文和来源记录ID。含免笔试不代表所有岗位免笔试；混合届别、专业条件以公告为准。
- JSON、校验和、CSV表头或revision异常时停止，不绕过校验或覆盖损坏文件。报告及读取快照仅存于个人工作区，不写Skill安装目录。
