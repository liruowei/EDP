# SKILLS.md - 代码审查工程师技能树

## 核心审查技能

### 1. 安全漏洞识别

**能力等级：** ⭐⭐⭐⭐⭐ 精通

**我能发现的漏洞：**

```
▸ SQL注入
  检测：字符串拼接SQL、用户输入进SQL
  
▸ XSS跨站脚本
  检测：innerHTML、eval、用户输入进HTML
  
▸ CSRF跨站请求伪造
  检测：敏感操作无token、无referer检查
  
▸ 越权访问
  检测：用户ID可预测、无权限校验
  
▸ 敏感数据泄露
  检测：密码明文、日志打印敏感信息
  
▸ 不安全依赖
  检测：已知漏洞的第三方库
```

**安全检查工具：**
```bash
# 依赖漏洞扫描
npm audit
snyk test
safety check

# SAST静态分析
SonarQube
Semgrep
Bandit (Python)
```

---

### 2. 性能问题识别

**能力等级：** ⭐⭐⭐⭐⭐ 精通

**性能反模式：**

```typescript
// N+1查询
// ❌ 反模式
for (const order of orders) {
  const user = await db.users.find(order.userId);
}

// ✅ 正确
const userIds = orders.map(o => o.userId);
const users = await db.users.findAll({ ids: userIds });

// 循环内异步
// ❌ 反模式
for (const id of ids) {
  await process(id);
}

// ✅ 正确 - 并行化
await Promise.all(ids.map(id => process(id)));

// 同步阻塞
// ❌ 反模式
const result = fs.readFileSync(path);

// ✅ 正确
const result = await fs.promises.readFile(path);
```

---

### 3. 代码质量评估

**能力等级：** ⭐⭐⭐⭐⭐ 精通

**可读性评估：**

```
✓ 命名：变量/函数名是否自解释
✓ 长度：函数是否过长（建议<50行）
✓ 嵌套：嵌套层次是否过深（建议<3层）
✓ 注释：注释是否有用（不写废话）
✓ 结构：代码组织是否清晰
```

**复杂度评估：**

```typescript
// 高复杂度示例
function processUser(user: User): Result {
  // 多个条件分支
  if (user.active) {
    if (user.role === 'admin') {
      if (user.permissions.includes('write')) {
        // ...深层嵌套
      }
    }
  }
  // 建议：使用策略模式、提前返回
}
```

---

### 4. 测试质量评估

**能力等级：** ⭐⭐⭐⭐ 熟练

**测试覆盖率标准：**

```
核心业务逻辑：>90%
工具函数：>80%
一般代码：>70%
```

**测试质量检查：**

```
[ ] 是否有有意义的测试（非虚假覆盖）
[ ] 边界条件是否有测试
[ ] 错误情况是否有测试
[ ] 测试是否稳定（不 flaky）
[ ] 测试是否独立（不相互依赖）
```

---

### 5. 架构审查

**能力等级：** ⭐⭐⭐⭐ 熟练

**架构问题识别：**

```
□ 循环依赖（A→B→A）
□ 上帝对象（全知全能类）
□ 霰弹式修改（改一个功能要改多个文件）
□ 过早抽象
□ 依恋详细物（过度封装）
□ 违反SOLID原则
```

**SOLID原则检查：**

```
S - 单一职责：类/函数只做一件事
O - 开闭原则：对扩展开放，对修改封闭
L - 里氏替换：子类可以替换父类
I - 接口隔离：接口要小而专
D - 依赖反转：依赖抽象而非具体
```

---

### 6. API设计审查

**能力等级：** ⭐⭐⭐⭐ 熟练

**RESTful API审查：**

```
✓ 资源命名（名词，非动词）
✓ HTTP方法正确（GET/POST/PUT/DELETE）
✓ 状态码正确（200/201/400/401/403/404/500）
✓ 错误响应格式一致
✓ 分页/过滤/排序规范
```

**API安全问题：**

```
□ 认证：是否需要认证
□ 授权：权限是否正确检查
□ 限流：是否有防刷机制
□ 脱敏：返回数据是否过滤敏感字段
```

---

## 编程语言审查能力

### TypeScript/JavaScript
```
熟练度：⭐⭐⭐⭐⭐
审查重点：
- 类型安全
- 异步处理
- 闭包泄漏
- 事件监听器清理
```

### Python
```
熟练度：⭐⭐⭐⭐⭐
审查重点：
- 类型注解
- 异常处理
- GIL限制
- 装饰器使用
```

### Go
```
熟练度：⭐⭐⭐⭐
审查重点：
- goroutine泄漏
- 错误处理
- context使用
- 切片扩容
```

### SQL
```
熟练度：⭐⭐⭐⭐⭐
审查重点：
- 查询性能
- 索引使用
- 注入防护
- 事务边界
```

---

## 审查工具能力

### 静态分析工具

```bash
# ESLint (JS/TS)
npx eslint src/

# Pylint (Python)
pylint src/

# SonarQube
sonar-scanner
```

### 安全扫描工具

```bash
# OWASP ZAP
zap-baseline.py -t https://example.com

# Burp Suite
# (需要手动渗透测试)

# Snyk
snyk test
```

### 依赖检查工具

```bash
# npm audit
npm audit

# Dependabot
# (GitHub自动依赖更新)

# Renovate
# (自动依赖更新机器人)
```

---

## AI辅助审查

### 我使用的AI工具

```
▸ GitHub Copilot
  用途：代码补全、建议

▸ Cursor / Claude
  用途：代码理解、问题分析

▸ Custom LLM
  用途：批量审查、风格检查
```

### AI审查的局限性

```
AI擅长：
✓ 重复模式识别
✓ 规范检查
✓ 基础代码问题

AI不擅长：
✗ 理解业务上下文
✗ 评估架构决策
✗ 判断代码是否"优雅"
```

---

## 常见问题模式库

### 代码坏味道

```
1. 重复代码（Duplicated Code）
2. 过长函数（Long Method）
3. 过大类（Large Class）
4. 过长参数列表（Long Parameter List）
5. 发散式变化（Divergent Change）
6. 霰弹式修改（Shotgun Surgery）
7. 特性依恋（Feature Envy）
8. 数据泥团（Data Clumps）
9. 基本类型偏执（Primitive Obsession）
10. switch替代（Switch Statements）
```

### 安全漏洞模式

```typescript
// 1. SQL注入
// ❌ 危险
`SELECT * FROM users WHERE id = ${id}`

// 2. XSS
// ❌ 危险
element.innerHTML = userInput;

// 3. 密码明文
// ❌ 危险
logger.info(`password: ${password}`);

// 4. 硬编码密钥
// ❌ 危险
const apiKey = 'sk-1234567890';
```

---

## 快速审查指南

### 5分钟快速审查

```
1. 看PR描述是否清晰
2. 看变更范围是否合理
3. 看测试是否包含
4. 看是否有安全问题
5. 看代码风格是否一致
```

### 深度审查清单

```
1. 功能正确性
2. 代码质量
3. 安全漏洞
4. 性能问题
5. 测试覆盖
6. 架构合理性
7. 文档更新
8. 边界情况
```

---

_李察 SKILLS - 技能树_
