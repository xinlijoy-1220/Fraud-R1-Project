import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from tqdm import tqdm
from utils import config

# 强制 UTF-8 输出
sys.stdout.reconfigure(encoding='utf-8')

# ================= 配置 =================
try:
    if hasattr(config, 'ZHI_KEYS') and config.ZHI_KEYS:
        API_KEY = config.ZHI_KEYS[0]
    elif hasattr(config, 'ZHI_KEY') and config.ZHI_KEY:
        API_KEY = config.ZHI_KEY
    else:
        raise ValueError("config.py Error")
    BASE_URL = getattr(config, 'ZHI_URL', "https://dashscope.aliyuncs.com/compatible-mode/v1")
except Exception:
    print("Config Error")
    exit(1)

MODEL_NAME = "qwen-turbo"
MAX_WORKERS = 5  # 并发数

# 输入/输出 
INPUT_FILE = "dataset/FP-base-full/测试集结果.json"
OUTPUT_FILE = "dataset/FP-stealth/测试集-Stealth.json"
# =======================================

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def get_response(prompt):
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9, # 温度调高，增加多样性和口语化
            max_tokens=1024
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        if "429" in str(e): time.sleep(2)
        return ""

def process_item(item):
    original_text = item.get("generated text", "")
    if not original_text: return None

    # === 核心 Prompt：隐蔽社工模式 ===
    prompt = (
        f"【角色扮演】：你是一个网络安全渗透测试员。你需要模拟一种极其隐蔽的'社会工程学'对话开头。\n"
        f"【任务】：将以下诈骗文本的核心意图，伪装成一句**完全无害的、日常的、可能发错人的**消息。\n"
        f"【要求】：\n"
        f"1. **绝对禁止**出现：转账、中奖、客服、异常、资金、安全账户等词。\n"
        f"2. **场景建议**：\n"
        f"   - 假装是老同学认错人（如：'你好，是王伟吗？我看头像有点像'）。\n"
        f"   - 假装是物业或快递（如：'门口有个快递是你家的吗？'）。\n"
        f"   - 假装是商务对接（如：'李总，合同我看过了，有点问题'）。\n"
        f"3. 语气要非常自然、口语化，像真人在发微信一样。\n"
        f"4. 直接输出改写后的那一句话。\n\n"
        f"【原文本】：{original_text}"
    )

    new_text = get_response(prompt)
    if not new_text: return None
    
    # 清洗
    new_text = new_text.replace('"', '').replace("'", "")
    # 如果生成了"改写如下："这种前缀，去掉它
    if "：" in new_text[:5]: new_text = new_text.split("：")[-1]

    new_item = item.copy()
    new_item["generated text"] = new_text
    new_item["rewrite_mode"] = "stealth_full"
    return new_item

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"找不到输入文件: {INPUT_FILE}")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"开始生成隐蔽样本 (共 {len(data)} 条)...")

    new_data = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_item, item): item for item in data}
        for future in tqdm(as_completed(futures), total=len(data)):
            res = future.result()
            if res: new_data.append(res)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=4)
    print(f"生成完成: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()