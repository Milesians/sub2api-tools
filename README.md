# sub2api-tools

合并版 sub2api 工具项目。目标是一个容器内运行一个 Vue 前端和一个 Python 后端，功能按模块划分。

## 路径

- 用户 LG：`{basePath}/lg`
- 管理员 LG：`{basePath}/admin/lg`
- 账号调度：`{basePath}/admin/scheduler`
- 后端接口：`{basePath}/api/...`

## 配置

运行配置只读取一个 YAML：

```bash
cp config.example.yaml config.yaml
docker compose -f docker-compose.example.yml up -d
```

关键路径：

- 只配置 `app.basePath`，例如 `/tools`
- 前端页面固定为 `{basePath}/lg`、`{basePath}/admin/scheduler`
- 后端接口固定为 `{basePath}/api/...`，例如 `/tools/api/health`
- `features[].visibility` 必须是 YAML list，值只支持 `user` / `admin`
- `security.allowed_origins` 控制允许访问工具的外部来源，支持 `https://*.example.com`；泛域名只匹配子域，不包含根域。
- sub2api 内部接口路径由程序固定，YAML 只配置 `sub2api.base_url` 和 `sub2api.admin_api_key`。
- `scheduler.enabled` 控制账号调度模块是否可用；`scheduler.auto_start: false` 可只启用查询/API，不启动后台调度循环。

## 部署

以主站域名 `sub2api.example.com`、工具路径 `/tools` 为例：

```yaml
app:
  basePath: "/tools"

security:
  allowed_origins:
    - "https://sub2api.example.com"

sub2api:
  base_url: "https://sub2api.example.com"
  admin_api_key: "change_this_admin_api_key"
```

启动容器：

```bash
cp config.example.yaml config.yaml
docker compose -f docker-compose.example.yml up -d
```

示例 compose 默认使用：

```yaml
image: ghcr.io/milesians/sub2api-tools:latest
ports:
  - "127.0.0.1:18080:8080"
```

Nginx 反代时保留 `/tools` 前缀，不要在 `proxy_pass` 末尾加 `/`：

```nginx
location ^~ /tools/ {
    proxy_pass http://127.0.0.1:18080;
    proxy_http_version 1.1;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_buffering off;
    proxy_read_timeout 300s;
}
```

访问地址：

- `https://sub2api.example.com/tools/lg`
- `https://sub2api.example.com/tools/admin/lg`
- `https://sub2api.example.com/tools/admin/scheduler`

## 镜像

GitHub Actions 会在 `main` 分支 push 时构建并推送：

```text
ghcr.io/milesians/sub2api-tools:latest
```

## 当前模块

- `looking-glass`：网络诊断基础接口、入口发现、诊断 ping/blob/upload/stream。
- `account-scheduler`：复用原 scheduler 核心策略，作为 FastAPI 同进程后台任务运行。

## 本地开发

后端：

```bash
cd backend
pip install -e ".[dev]"
python -m sub2api_tools --config ../config.example.yaml
```

前端：

```bash
cd frontend
npm install
npm run dev
```
