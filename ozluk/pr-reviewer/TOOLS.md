# TOOLS.md - 代码审查工程师工具箱

## Git工具

### Git命令
```bash
# 查看PR差异
git diff main...feature-branch

# 查看文件历史
git log -p --follow filename

# 查看提交影响的文件
git show commit-id --stat

# 查看分支差异
git diff branch1..branch2
```

### GitHub PR审查
```bash
# 查看PR详情
gh pr view 123

# 审查PR
gh pr review 123 --approve
gh pr review 123 --request-changes
gh pr review 123 --comment

# 合并PR
gh pr merge 123
```

---

## 静态分析工具

### ESLint (JS/TS)
```bash
# 安装
npm install eslint --save-dev

# 运行
npx eslint src/

# 带修复
npx eslint src/ --fix

# 配置文件
.eslintrc.js
```

### Pylint (Python)
```bash
# 安装
pip install pylint

# 运行
pylint src/

# 生成报告
pylint src/ --output-format=html > report.html
```

### SonarQube
```bash
# 扫描
sonar-scanner

# Maven
mvn sonar:sonar

# Gradle
gradle sonar
```

---

## 安全扫描工具

### 依赖漏洞扫描
```bash
# npm audit
npm audit
npm audit fix

# Snyk
npm install -g snyk
snyk test
snyk monitor

# Safety (Python)
pip install safety
safety check
```

### SAST工具
```bash
# Semgrep
semgrep --config=auto src/

# Bandit (Python)
bandit -r src/

# SpotBugs (Java)
spotbugs
```

### DAST工具
```bash
# OWASP ZAP
zap-baseline.py -t https://example.com

# SQLMap (SQL注入)
sqlmap -u "https://example.com/?id=1"
```

---

## 代码质量工具

### 代码格式化
```bash
# Prettier (JS/TS)
npx prettier --check src/
npx prettier --write src/

# Black (Python)
black --check src/
black src/

# Go fmt
go fmt ./...
```

### 代码复杂度
```bash
# eslint complexity
npx eslint src/ --rule 'complexity: ["error", 10]'

# cyclomatic complexity
pip install radon
radon cc src/ -a
```

---

## 性能分析工具

### 数据库查询分析
```sql
-- PostgreSQL
EXPLAIN ANALYZE SELECT * FROM users WHERE id = 1;

-- MySQL
EXPLAIN SELECT * FROM users WHERE id = 1;
```

### API性能测试
```bash
# Apache Bench
ab -n 1000 -c 10 https://api.example.com/endpoint

# wrk
wrk -t12 -c100 -d30s https://api.example.com/

# k6
k6 run script.js
```

---

## API测试工具

### curl
```bash
# GET请求
curl https://api.example.com/users

# POST请求
curl -X POST https://api.example.com/users \
  -H "Content-Type: application/json" \
  -d '{"name": "test"}'

# 带认证
curl -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/private
```

### Postman
```
用途：API调试和测试
功能：请求构建、环境变量、测试脚本
```

---

## 代码查看工具

### GitHub
```
功能：PR差异查看、评论、审查
快捷键：
- t: 文件树
- c: 评论
- e: 编辑文件
```

### VS Code扩展
```
- GitLens: 增强Git功能
- ESLint: 实时检查
- Prettier: 代码格式化
- SonarLint: 代码问题提示
```

---

## 监控和追踪

### 日志聚合
```bash
# ELK Stack
# Kibana查询
level:ERROR AND service:"user-service"

# Loki (Grafana)
{job="app"} |= "ERROR"
```

### 链路追踪
```bash
# Jaeger
# 查看trace
service:"api" operation:"GET /users"
```

---

## 文档工具

### API文档
```yaml
# OpenAPI/Swagger
openapi: 3.0.0
info:
  title: User API
  version: 1.0.0
paths:
  /users:
    get:
      summary: Get users
```

### README生成
```bash
# badges
[![Build Status](https://travis-ci.org/org/repo.svg)]

# API文档
npx @redocly/cli build-docs openapi.yaml
```

---

## 自动化工具

### GitHub Actions
```yaml
name: Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run ESLint
        run: npm run lint
      - name: Security scan
        run: npm audit
```

### 自动化审查机器人
```javascript
// 示例：自动审查机器人逻辑
const reviewBot = {
  async onPullRequest(pr) {
    const issues = [];
    
    // 检查标题格式
    if (!pr.title.match(/^\[TYPE\]/)) {
      issues.push('PR标题需要包含类型前缀');
    }
    
    // 检查测试
    if (!pr.hasTests) {
      issues.push('缺少测试用例');
    }
    
    // 返回审查意见
    return issues;
  }
};
```

---

## 环境配置

### Node.js环境
```bash
# 版本管理
nvm use 18
node --version

# 依赖检查
npm outdated
npm audit
```

### Python环境
```bash
# 版本管理
pyenv versions
pyenv use 3.11

# 依赖检查
pip list --outdated
safety check
```

---

## 常用脚本

### 快速审查脚本
```bash
#!/bin/bash
# 快速代码审查

echo "=== ESLint ==="
npm run lint

echo "=== Type Check ==="
npm run type-check

echo "=== Tests ==="
npm test

echo "=== Security ==="
npm audit
```

### PR审查清单
```markdown
## PR审查清单

### 基本信息
- [ ] PR描述完整
- [ ] 关联了正确的issue
- [ ] 分支命名规范

### 代码质量
- [ ] 通过ESLint
- [ ] 代码风格一致
- [ ] 无重复代码

### 测试
- [ ] 有测试用例
- [ ] 覆盖率达标
- [ ] 边界条件有覆盖

### 安全
- [ ] 无注入风险
- [ ] 无XSS风险
- [ ] 权限控制正确

### 性能
- [ ] 无N+1查询
- [ ] 无性能问题

### 文档
- [ ] 代码有注释
- [ ] 必要时更新README
```

---

_李察 TOOLS - 工欲善其事，必先利其器_
