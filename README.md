# English Reciter（英语背诵系统）

基于 Python 的英语单词学习与复习工具：提供**命令行（CLI）**与**简化 Web 界面**，内置间隔重复（SRS）与可选语音朗读（TTS），支持 Docker 一键部署。

## 功能概览

- **间隔重复**：按 `config.json` 中的间隔安排复习（默认与艾宾浩斯式阶梯一致：1 → 2 → 4 → … → 90 天）。
- **掌握判定**：连续答对达到配置次数后移入「已掌握」列表（默认 `max_success_count: 8`）。
- **CLI 模式**：终端菜单，适合本地专注背诵；可启用 TTS、例句、学习统计与自动备份。
- **Web 模式（Flask）**：注册登录、按用户隔离数据、导入词表、复习与健康检查接口；默认端口 **8000**。
- **容器部署**：`docker-compose` 暴露 8000 端口，并挂载 `user_data_simple` 持久化用户数据。

## 环境要求

- Python **3.11+**（与 `Dockerfile` / 推荐环境一致；CLI 最低可尝试 3.8+，以本机实测为准）
- 操作系统：Windows / macOS / Linux
- Web/TTS：部分能力依赖网络（如 gTTS）；离线例句可走本地例句库（见 `reciter.py` 中 `ExampleGenerator`）

## 快速开始

### 方式一：Docker（推荐用于 Web）

```bash
docker compose up -d
```

浏览器访问：<http://localhost:8000>  
健康检查：<http://localhost:8000/api/health>

停止服务：

```bash
docker compose down
```

生产环境请将 `SECRET_KEY` 设为强随机值（可通过环境变量或 `.env` 传入 Compose）。

### 方式二：本地运行 Web

```bash
pip install -r requirements-simple.txt
python simple_web_app.py
```

### 方式三：仅使用命令行

```bash
pip install -r requirements-simple.txt
python reciter.py
```

启动后按菜单选择「今日复习」「查看进度」「已掌握词汇」等（以程序内提示为准）。

### 可选：启动脚本（类 Unix）

```bash
bash start_simple_web.sh
```

## Web 使用流程简述

1. 打开 <http://localhost:8000>，注册并登录。
2. 在「导入单词」中上传 UTF-8 文本文件，每行一条：`英文,中文`（逗号分隔，仅分割第一个逗号）。
3. 按页面提示进行复习；需要时在浏览器中触发朗读（具体以界面为准）。

## 配置说明

核心参数在 **`config.json`**（可被程序读取并合并默认值），例如：

| 项 | 含义 |
|----|------|
| `word_file` | 初始词表文件（CLI） |
| `data_file` | 学习进度与词库数据文件 |
| `example_db` | 本地例句 JSON 路径 |
| `max_success_count` | 判定为「已掌握」所需的连续成功次数 |
| `review_interval_days` | 各成功等级对应的复习间隔（天） |
| `backup_enabled` / `backup_interval_days` / `max_backups` | 自动备份策略 |

修改后请重启对应进程（CLI 或 Web）。

## 项目结构（主要文件）

```
english_reciter/
├── reciter.py              # 核心背诵逻辑、CLI 入口
├── simple_web_app.py       # Flask Web 应用与 API
├── static/                 # 前端静态资源（HTML/CSS/JS）
├── config.json             # 运行时配置
├── requirements-simple.txt # Python 依赖
├── Dockerfile
├── docker-compose.yml
├── words.txt               # 示例/默认词表（CLI）
├── learning_data.json      # CLI 学习数据（运行后生成或维护）
└── user_data_simple/       # Web 多用户数据目录（每用户子目录 + users.json）
```

更多细节可参考仓库内文档：`QUICK_START.md`、`DEPLOYMENT.md`、`USAGE.md`。

## 数据与隐私

- **CLI**：进度主要在 `learning_data.json`（及配置的备份目录 `backups/`）。
- **Web**：用户与进度在 `user_data_simple/` 下；请勿将真实密码或生产数据直接提交到公开仓库。

## 故障排除

- **无法朗读**：检查网络与 TTS 开关（`tts_enabled`）；服务器端朗读还受操作系统音频命令影响。
- **数据异常**：若 `learning_data.json` 损坏，可尝试从 `words.txt` 或备份恢复（逻辑见 `reciter.py`）。
- **端口占用**：修改 `simple_web_app.py` 中 `app.run` 的 `port`，并同步 `docker-compose.yml` 端口映射。

## 开发与贡献

欢迎通过 Issue / Pull Request 反馈问题或提交改进。提交前建议本地运行 `test_reciter.py`、`test_stats.py`（如有改动相关逻辑）。

## 许可证

MIT License

---

**English Reciter** — 在终端或浏览器里坚持复习，比收藏夹更接近「学会」。
