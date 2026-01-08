# VanceCoursePro

一款基于 Python 的正方教务系统自动化选课工具，支持多账号管理、自动抢课、课程退选等功能，拥有现代化的图形界面。
基于 正方教务V9.0 制作，不一定适用于所有场景，请自行测试，如有问题欢迎提交PR和Issue。

## 📖 功能特性

- **🔑 多账号管理**：支持添加、编辑、删除多个学生账号，一键切换
- **📚 课程浏览**：查看可选课程列表，支持查看教学班详情（教师、时间、地点、余量等）
- **🚀 自动抢课**：创建抢课任务，支持自定义抢课间隔，自动重试直到成功
- **📝 任务管理**：同时运行多个抢课任务，支持单独或批量启动/停止
- **❌ 课程退选**：支持退选已选课程，退选在服务器端貌似没有验证，只会返回成功，谨慎使用
- **⚙️ 灵活配置**：支持自定义教务系统地址，适配不同学校

## 🖥️ 界面预览

应用采用 ttkbootstrap 主题，提供现代化的深色界面，主要包含：
- **左侧**：课程列表浏览区域
- **右上**：账号管理和任务管理区域
- **下方**：操作日志区域

## 🔧 安装

### 环境要求

- Python 3.8+
- Windows / macOS / Linux

### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/your-username/course-selection-helper.git
cd course-selection-helper
```

2. **创建虚拟环境（推荐）**

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

3. **安装依赖**

```bash
pip install -r requirements.txt
```

4. **配置教务系统地址**

复制配置文件模板并填写：

```bash
cp config.example.json config.json
```

编辑 `config.json`，填入你学校的教务系统地址：

```json
{
    "base_url": "http://your-jwglxt-server.edu.cn/jwglxt",
    "accounts": [],
    "default_account": null
}
```

> ⚠️ **注意**：`config.json` 包含敏感信息，已添加到 `.gitignore`，不会被提交到版本控制。

## 🚀 使用方法

### 启动应用

```bash
python main_gui.py
```

### 基本操作流程

1. **配置教务地址**：首次运行点击「设置」按钮，配置教务系统 URL
2. **添加账号**：点击账号管理区的「+」按钮添加学生账号
3. **登录**：选择账号后点击「登录」
4. **加载课程**：
   - 选择课程类型（必修/限选/任选）
   - 点击「加载列表」按钮(**否则后面的几个按钮不会按照预期工作**)
   - 点击「加载课程」获取可选课程列表
   - 点击「加载详情」查看教学班余量等详细信息
5. **创建抢课任务**：
   - 在课程列表中选择目标课程
   - 点击「添加任务」，选择教学班并设置抢课间隔
6. **启动抢课**：点击「全部开始」或单独启动任务
7. **退选课程**：选择已选课程，点击「退选」按钮

## 📁 项目结构

```
.
├── main_gui.py          # 主程序入口和图形界面
├── jwglxt_api.py        # 正方教务系统 API 封装
├── account_manager.py   # 账号管理模块
├── task_manager.py      # 抢课任务管理模块
├── config.json          # 配置文件（需自行创建）
├── config.example.json  # 配置文件模板
├── requirements.txt     # Python 依赖
└── .gitignore           # Git 忽略规则
```

## ⚠️ 免责声明

本项目仅供学习和研究使用，请勿用于任何违反学校规定的用途。使用本工具产生的一切后果由使用者自行承担。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

[MIT License](LICENSE)
