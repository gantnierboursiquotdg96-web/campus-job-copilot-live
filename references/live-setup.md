# 首次安装与授权

买家需要支持本地Skill及命令执行的AI工具、Python 3.10+、Node.js/npm和飞书CLI。浏览器中的普通聊天窗口不一定能运行这些脚本。Codex已验证；其他工具按其Skill安装方式配置，本安装包不承诺RedsKill平台兼容性。

1. 把完整 `campus-job-copilot` 文件夹安装到AI工具的技能目录。Codex通常为 `~/.codex/skills/`。下一轮确认Skill已被发现。
2. 安装飞书CLI：`npm install -g @larksuite/cli`，运行 `lark-cli --version`。Python运行 `python --version` 检查3.10+。
3. 买家用自己的飞书账号配置自己的应用：`lark-cli config init --new --brand feishu --lang zh`。按命令生成的官方页面完成配置，不填写卖家密钥。
4. 用户登录时请求Base业务域：`lark-cli auth login --domain base --no-wait --json`。这是CLI的Base域权限集合，可能包含写权限，但本Skill只调用读取命令；不能宣称它只申请读取scope。更严格的scope可按当前CLI的schema及应用权限实际配置。
5. 将返回的 `verification_url` 原样展示，并用 `lark-cli auth qrcode <url> --output authorization.png` 展示PNG二维码。当前轮结束，让买家完成官方授权后返回；由AI执行 `lark-cli auth login --device-code <device_code>` 完成登录，再运行 `lark-cli auth status --verify --json` 核验。过期则重新发起；授权码不打包、不发给其他人。
6. 用同一账号打开信息库，确认有阅读权限。CLI访问同时受应用权限和资源ACL限制；浏览器可看不保证当前应用必定能读。权限失败时由AI解释缺失范围，停止推荐，不更改源表分享权限、不切换身份。

日常直接说：

> 使用 $campus-job-copilot。先读取最新信息库。我是2027届工商管理本科，目标电商运营，优先北京、上海、广州，可以接受笔试。这里是我的简历，请先推荐机会，等我选定后再制定计划。

让AI先安装及配置，买家只在官方页面完成授权，不需要记住搜索脚本参数。首次配置有学习门槛；卖家可提供这份说明和演示。

修改个人偏好后重新推荐会重新读取数据库，无需下载新安装包。卖家若更换Base或字段ID，则需要更新 `assets/live-source.json` 和安装包。仅更新同一表里的招聘记录不需要更新安装包。
