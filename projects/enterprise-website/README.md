# 企业官网 Demo

## 项目说明
这是一个现代化的企业官网演示项目，采用纯 HTML/CSS/JavaScript 开发。

## 功能特性
- ✅ 响应式设计（支持桌面端和移动端）
- ✅ 平滑滚动导航
- ✅ 移动端汉堡菜单
- ✅ 企业介绍、服务展示、产品展示
- ✅ 联系表单
- ✅ 现代化 UI 设计

## 启动方式

### 方法 1：使用 Python HTTP 服务器
```bash
cd /root/hermes-hub/projects/enterprise-website
python3 -m http.server 8080
```

### 方法 2：使用 npm
```bash
npm run dev
```

访问地址：http://localhost:8080

## 测试要求
- [ ] 页面能否正常打开
- [ ] 桌面端显示是否正常
- [ ] 移动端响应式是否正常
- [ ] 导航栏功能是否正常
- [ ] 平滑滚动是否生效
- [ ] 移动端汉堡菜单是否可用
- [ ] 表单提交是否有反馈
- [ ] 控制台是否有报错
- [ ] 各个区块内容是否完整展示
- [ ] CTA 按钮和产品按钮是否可点击

## 项目结构
```
enterprise-website/
├── index.html          # 主页面
├── style.css           # 样式文件
├── script.js           # 交互脚本
├── package.json        # 项目配置
└── README.md           # 说明文档
```