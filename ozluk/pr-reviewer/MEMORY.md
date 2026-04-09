# MEMORY.md - 代码审查工程师经验库

## 审查教训

### 🔴 教训1：不要过度审查

**事件：**
对一个小小的格式问题写了3条详细反馈，作者感到被过度挑剔。

**根因：**
我没有区分"必须修改"和"建议修改"。

**学到的：**
```
必须修改：
- 安全漏洞
- 错误逻辑
- 缺失测试
- 规范违规

建议修改：
- 代码风格
- 命名优化
- 小优化

平衡的艺术：保持标准，但不要事事计较。
```

---

### 🔴 教训2：反馈要具体

**事件：**
写了"这段代码不好"，作者问"哪里不好"。

**根因：**
反馈太模糊，没有具体指出问题和解决方案。

**学到的：**
```
模糊反馈："这段代码不好"
具体反馈："这个函数第45行，user未定义会抛异常，建议添加可选链或默认值"
```

---

### 🟡 教训3：考虑作者背景

**事件：**
对一个新人写了"这不符合设计模式"，新人很迷茫。

**根因：**
没有考虑对方的经验水平，反馈过于抽象。

**学到的：**
```
对新人：
- 解释为什么
- 给出具体例子
- 鼓励为主

对资深：
- 指出问题即可
- 可以讨论最优解
```

---

### 🟡 教训4：紧急时简化流程

**事件：**
线上故障需要紧急修复，我还在详细审查，作者很着急。

**根因：**
没有区分紧急审查和常规审查。

**学到的：**
```
紧急审查：
1. 只看核心问题（止血优先）
2. 简化反馈
3. 记录问题后续完善
```

---

## 常见问题模式库

### 1. SQL注入漏洞

**模式：**
```typescript
// ❌ 危险
const query = `SELECT * FROM users WHERE name = '${name}'`;

// ✅ 安全
const query = `SELECT * FROM users WHERE name = ?`;
db.execute(query, [name]);
```

**发现技巧：**
```
grep搜索：\$\{  ${ 模板字符串拼接SQL
检查：所有SQL是否使用参数化查询
```

---

### 2. XSS漏洞

**模式：**
```typescript
// ❌ 危险
element.innerHTML = userInput;

// ✅ 安全
element.textContent = userInput;

// 或
element.innerHTML = DOMPurify.sanitize(userInput);
```

**发现技巧：**
```
grep搜索：innerHTML  .html()
检查：用户输入是否经过sanitize
```

---

### 3. N+1查询

**模式：**
```typescript
// ❌ 危险
for (const order of orders) {
  const user = await db.getUser(order.userId);
}

// ✅ 安全
const userIds = orders.map(o => o.userId);
const users = await db.getUsers({ ids: userIds });
```

**发现技巧：**
```
日志中大量相似查询
循环内的await
缺少批量接口
```

---

### 4. 敏感信息泄露

**模式：**
```typescript
// ❌ 危险
console.log(`password: ${password}`);
logger.info(user);
```

**发现技巧：**
```
grep搜索：password, secret, token, key, logger
检查日志内容
检查API返回
```

---

## 审查检查清单

### 新PR审查
```
□ PR描述是否清晰
□ 变更范围是否合理
□ 是否关联issue
□ 是否有测试
□ CI是否通过
```

### 代码质量审查
```
□ 命名是否清晰
□ 函数是否过长
□ 是否重复代码
□ 是否有注释
□ 代码风格一致
```

### 安全审查
```
□ 输入是否验证
□ SQL是否安全
□ XSS是否防护
□ 权限是否正确
□ 敏感数据是否保护
```

### 性能审查
```
□ 是否有N+1查询
□ 是否有循环问题
□ 是否正确使用缓存
□ 大数据量处理
```

---

## 问题知识库

### 问题：密码明文传输

**发现方法：**
```
grep -r "password" src/
检查网络请求
```

**修复方案：**
```
1. 使用HTTPS
2. 不要在URL中传密码
3. 使用POST body
4. 后端不要记录明文密码
```

---

### 问题：无限循环

**发现方法：**
```
1. 代码审查
2. 性能profiling
3. 超时检测
```

**修复方案：**
```
1. 添加循环上限
2. 使用递归深度限制
3. 添加超时
```

---

### 问题：内存泄漏

**发现方法：**
```
1. 长期运行观察内存
2. Heap Snapshot对比
3. 监控内存增长曲线
```

**修复方案：**
```
1. 清理定时器
2. 移除事件监听
3. 使用WeakMap
4. 限制缓存大小
```

---

## 最佳实践总结

### 反馈的格式

```
1. 指出位置（文件:行号）
2. 说明问题（什么问题）
3. 解释原因（为什么是问题）
4. 给出建议（如何修改）
```

### 审查节奏

```
1. 每次审查不超过60分钟
2. 每天不超过4小时深度审查
3. 复杂PR分多次审查
4. 保持专注，避免疲劳
```

### 沟通原则

```
1. 对事不对人
2. 解释原因，不只是结论
3. 提供方案，不只指出问题
4. 考虑作者感受
5. 区分必须和建议
```

---

## 审查案例库

### 案例1：修复未考虑边界

**PR描述：**
修复用户状态显示问题

**审查发现：**
```typescript
// 原代码
const status = user.status ? '在线' : '离线';

// 问题：user可能为null
// 边界：user.status可能为'unknown'
```

**反馈：**
```
[问题] src/user.ts:23

这里没有处理user为null的情况，也没有处理未知的status值。

建议：
```typescript
const status = {
  'online': '在线',
  'offline': '离线',
  'unknown': '未知'
}[user?.status] ?? '未知';
```
```

---

### 案例2：性能问题

**PR描述：**
优化用户列表查询

**审查发现：**
```typescript
// 原代码
for (const id of userIds) {
  const user = await getUser(id);
}

// 问题：串行查询，100个用户=100次DB调用
```

**反馈：**
```
[性能问题] src/user.service.ts:45

循环内的异步查询会产生N+1问题。100个用户ID会执行100次数据库查询。

建议：
```typescript
const users = await getUsers(userIds); // 一次批量查询
```
```

---

### 案例3：安全问题

**PR描述：**
添加文件上传功能

**审查发现：**
```typescript
// 原代码
const filename = req.files.upload.name;
fs.writeFile(`./uploads/${filename}`, data);
```

**反馈：**
```
[安全问题] src/upload.service.ts:15

文件名直接拼接到路径，存在路径穿越漏洞。用户可能上传名为../../../etc/passwd的文件。

建议：
```typescript
const safeName = path.basename(filename);
const safePath = path.join('./uploads', safeName);
fs.writeFile(safePath, data);
```
```

---

## 审查指南

### 何时Approve

```
✓ 功能正确
✓ 无安全问题
✓ 无严重性能问题
✓ 测试充分
✓ 代码可读
```

### 何时Request Changes

```
✗ 有bug
✗ 有安全漏洞
✗ 有严重性能问题
✗ 缺少必要测试
✗ 违反硬性规范
```

### 何时Comment

```
○ 代码优化建议
○ 风格建议
○ 最佳实践分享
○ 提问
○ 鼓励
```

---

_李察 MEMORY - 经验是最好的老师_
