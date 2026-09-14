# Contributing

1. Fork / 建分支。
2. 不提交 `.env`、AK、真实敏感数据。
3. 新功能应补测试。
4. 提交前运行：

```bash
python scripts/style_check.py
python -m compileall -q app
python -m pytest -q
```

5. Issue 请包含复现步骤、运行模式（demo/real）、Python 版本和脱敏错误信息。
