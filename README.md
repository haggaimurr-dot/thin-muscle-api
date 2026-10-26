# thin-muscle-api

薄肌健身小程序后端（FastAPI）

## 市场 v2（字段表）

- 商品 `kind`：`plan`（周/月/全程）| `lesson`（教学模块）
- 复刻：**媒体全保留** → `GET /api/v1/market/nodes` 训练节点库
- 拼装：`POST /api/v1/market/assemble`，须 `ack_weight` + `ack_level`；`lesson_node_id` 只能挂在动作学法位
- 价格字段：`price_fen`（分），抽成 15%
- 筛选：`kind` + `cycle` + `level`

## 启动

```bash
cd /workspace/thin-muscle-api && source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

头：`X-User-Id: 4`
