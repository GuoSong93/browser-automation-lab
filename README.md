# Browser Automation Lab

本地虚构服务商后台 + Playwright 机器人。演示稳定定位、等待目标数据、选择本年度通知书、有限重试及下载后内容验证。

## 一次跑通

```shell
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
python bot.py --scenario success
python -m unittest discover -s tests -v
```

机器人会自动启动仅监听 127.0.0.1 的临时后台，完成后关闭。无需真实服务或密钥。
成功产物在 `artifacts/run/`：`notice.pdf`、`result.json`、`success.png`、`trace.zip`。
`--headed` 可观看流程，默认无头运行。

## 故障演示

| --scenario | 行为与预期 |
| --- | --- |
| success | 去年记录排在第一行，机器人仍选择本年度 |
| delayed | 后台延迟 600ms，等待 Loaded 状态后再选择 |
| empty | 无查询结果，拒绝下载，退出 2 |
| stale-only | 只有往年通知书，拒绝下载，退出 2 |
| download-once | 首次下载 503，第二次成功，次数记录为 2 |
| wrong-amount | 页面显示正确，文件金额错误；下载后拒绝通过 |
| wrong-order | 文件订单不匹配；拒绝通过 |

```shell
python bot.py --scenario download-once --out artifacts/retry
python bot.py --scenario wrong-amount --out artifacts/rejected
python -m playwright show-trace artifacts/rejected/trace.zip
```

失败不会留下 `notice.pdf` 和成功 JSON；错误报告、截图和 trace 帮助定位。产物默认不进入 Git。

## 手工浏览

```shell
python fake_portal.py --port 8084 --scenario delayed
```

访问 http://127.0.0.1:8084。虚构账号 `demo@example.test`，密码 `demo-pass`；页面直接显示模拟邮箱验证码。
OTP 同时绑定登录请求与时间窗口；机器人容忍 5 秒时钟偏差，并拒绝其他请求或过旧邮件。

## 设计边界

- 机器人只访问本地页面；没有接入第三方保司、真实邮箱、验证码识别或身份核验。
- 产品可见名称变化，通过稳定 data-testid 和产品编码选择。
- 验证 PDF 正文中的订单、年份、金额；HTTP 200 和下载完成都不足以证明业务正确。
- 有限次数重试只针对临时下载故障，不盲目重试业务错误。
- 示例 PDF 用 pypdf 构造简单文本内容；生产文档转换、任意布局支持不属于本版。
- 本地单用户测试服务，没有生产级认证、消息队列或任务调度。

技术参考：[Playwright downloads](https://playwright.dev/python/docs/downloads)、[auto-waiting](https://playwright.dev/python/docs/actionability)。

## 测试分层

默认测试会启动真实 Chromium。`tests/test_portal.py` 直接调用真实 HTTP handler 并验证响应，覆盖全部故障场景，但不替代浏览器集成测试。
受限环境可显式设置 `SKIP_BROWSER_E2E=1`，只运行离线检查；测试输出会标注跳过，CI 不设置该变量。

## 实现与验证说明

本项目为全新演示代码，使用虚构规则和样例，由作者结合业务经验、通过 AI 辅助实现。
已验证项目与受环境限制的检查见 [VERIFICATION.md](VERIFICATION.md)。
