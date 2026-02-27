# Token 成本配置迁移说明

## 问题

如果您在启动 MyxAI Desk 时看到以下错误：

```
Warning: Failed to load config from C:\Users\xxx\.nanobot\config.json: 1 validation error for Config
tokenCost
  Extra inputs are not permitted [type=extra_forbidden, ...]
```

这是因为旧版本将 Token 成本配置错误地保存在了 `config.json` 中。

## 自动迁移

**新版本会在启动时自动迁移**，您只需：

1. 重启 MyxAI Desk 应用
2. 迁移会自动完成
3. 错误消息将消失

## 手动迁移（可选）

如果需要手动运行迁移：

```bash
python myxai_desk/core/migrate_token_cost.py
```

## 迁移做了什么

1. 从 `~/.nanobot/config.json` 读取 `tokenCost` 字段
2. 保存到新位置：`~/.nanobot/usage/token_cost_config.json`
3. 从 `config.json` 中删除 `tokenCost` 字段

## 配置文件位置变化

**之前**：
```
~/.nanobot/config.json
{
  "agents": {...},
  "tokenCost": {          ❌ 错误位置
    "inputPrice": 0.8,
    "outputPrice": 2,
    "dailyLimit": 1,
    "monthlyLimit": 10
  }
}
```

**之后**：
```
~/.nanobot/config.json    # 只包含 nanobot 配置
{
  "agents": {...}
}

~/.nanobot/usage/token_cost_config.json  # ✅ 正确位置
{
  "inputPrice": 0.8,
  "outputPrice": 2,
  "dailyLimit": 1,
  "monthlyLimit": 10
}
```

## 为什么要分离

- Token 成本是 MyxAI Desk 的**应用统计配置**，与 nanobot 核心无关
- nanobot 的 `config.json` 使用 Pydantic 验证，不允许额外字段
- 分离后避免配置冲突，职责更清晰

## 注意事项

- 迁移是**一次性**的，不会重复执行
- 迁移**不会**丢失您的配置
- 如果没有 `tokenCost` 字段，迁移会自动跳过
