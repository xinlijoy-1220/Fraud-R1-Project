# Fraud-R1: 对抗性数据改写在欺诈对话检测中的应用

这是 [自然语言处理] 课程期末大作业的代码仓库。本项目通过隐蔽的社会工程学改写策略，成功降低了大模型在欺诈检测中的防御准确率。

## 📂 项目结构
- `dataset/`: 实验数据集 (包含 Baseline, Synonym, Rewrite, Stealth)
- `results/`: 实验运行结果 (包含 2.09% 攻击成功的记录)
- `attacks/`: 攻击核心代码
- `main.py`: 主程序入口
- `final_eval.py`: 结果评估

## 🚀 如何运行

1. 安装依赖:
   ```bash
   pip install -r requirements.txt
2. 配置 API Key:
在utils/config.py中填入你的API Key

3. 运行评估:
Bash

python final_eval.py
该命令将直接输出实验结果统计。