import json
import os
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from tqdm import tqdm
from utils import config

# ================= 配置区域 =================
try:
    if hasattr(config, 'ZHI_KEYS') and config.ZHI_KEYS:
        API_KEY = config.ZHI_KEYS[0]
    elif hasattr(config, 'ZHI_KEY') and config.ZHI_KEY:
        API_KEY = config.ZHI_KEY
    else:
        raise ValueError("config.py 中未配置 ZHI_KEYS")

    BASE_URL = getattr(config, 'ZHI_URL', "https://dashscope.aliyuncs.com/compatible-mode/v1")
except Exception as e:
    print(f"[ERROR] Config Error: {e}")
    exit(1)

# 模型名称
MODEL_NAME = "qwen-turbo" 

# 并发数量
MAX_WORKERS = 5 

# 输入文件
INPUT_FILE = "dataset/FP-base-full/测试集结果.json"

# 输出文件
OUTPUT_SYNONYM = "dataset/FP-ablation/测试集-Synonym.json" 
OUTPUT_REWRITE = "dataset/FP-rewrite/测试集-Rewrite.json" 
# ===========================================

print(f"[INFO] 当前模型: {MODEL_NAME} | 线程数: {MAX_WORKERS}")
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def get_response(prompt):
    """发送单个请求"""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        # 简单重试机制
        if "429" in str(e):
            time.sleep(2) # 遇到限流稍微歇一下
            return get_response(prompt) # 递归重试一次
        print(f"\n[ERROR] API Call Failed: {e}")
        return ""

def process_single_item(item, mode):
    """处理单条数据的函数"""
    original_text = item.get("generated text", "")
    if not original_text or len(original_text) < 2:
        return None

    if mode == "synonym":
        prompt = (
            f"请对以下这段文本进行'同义词替换'改写。\n"
            f"要求：\n"
            f"1. 仅替换部分词汇，严格保持原句结构、语序和长度不变。\n"
            f"2. 严禁改写句子含义，严禁扩写。\n"
            f"3. 直接输出改写后的文本，不要包含任何解释。\n\n"
            f"原文本：{original_text}"
        )
    else:
        prompt = (
            f"你是一个专业的文本改写助手。请将以下诈骗文本进行深度润色和改写，使其更具欺骗性和隐蔽性。\n"
            f"要求：\n"
            f"1. 增加紧迫感或诱惑力，通过调整语气来通过垃圾短信过滤。\n"
            f"2. 可以适当调整句式结构，使其更像真实的官方通知或好友口吻。\n"
            f"3. 直接输出改写后的文本，不要包含任何解释。\n\n"
            f"原文本：{original_text}"
        )

    new_text = get_response(prompt)
    if not new_text:
        return None

    # 清洗
    new_text = new_text.replace('"', '').replace("'", "")
    
    new_item = item.copy()
    new_item["generated text"] = new_text
    new_item["is_rewritten"] = True
    new_item["rewrite_mode"] = mode
    new_item["model_used"] = MODEL_NAME
    return new_item

def generate_dataset_concurrent(mode, input_data, output_file):
    print(f"\n[START] 开始生成: {mode} (并发模式)")
    new_data = []
    
    # 使用线程池并发处理
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_item = {executor.submit(process_single_item, item, mode): item for item in input_data}
        
        # 使用 tqdm 显示进度
        for future in tqdm(as_completed(future_to_item), total=len(input_data), desc=f"Progress"):
            result = future.result()
            if result:
                new_data.append(result)

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=4)
    print(f"[SUCCESS] 文件已保存: {output_file}")

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] 找不到输入文件: {INPUT_FILE}")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"[INFO] 读取到 {len(data)} 条数据")

    generate_dataset_concurrent("synonym", data, OUTPUT_SYNONYM)
    generate_dataset_concurrent("rewrite", data, OUTPUT_REWRITE)

if __name__ == "__main__":
    main()