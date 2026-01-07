import pandas as pd
import json
import os

# ================= 配置区域 =================
SOURCE_FILE = '测试集结果.csv'  
#SOURCE_FILE = '训练集结果.csv'  
OUTPUT_FILE = 'dataset/FP-base-full/测试集结果.json'
#OUTPUT_FILE = 'dataset/FP-base-full/训练集结果.json'

def transform_row(row, index):
    """
    将 CSV 的一行转换为 Fraud-R1 需要的 JSON 格式
    CSV列名: specific_dialogue_content, interaction_strategy, call_type, is_fraud, fraud_type
    """
    # 处理 data_type (Fraud-R1 依赖这个字段来选择 Prompt)
    raw_call_type = str(row.get('call_type', 'message')).lower()
    if 'mail' in raw_call_type:
        data_type = 'email'
    elif 'job' in raw_call_type:
        data_type = 'job posting'
    else:
        data_type = 'message' # 默认为短信/消息

    return {
        "id": index + 1,
        "category": row.get('fraud_type', 'Unknown'),
        "subcategory": row.get('fraud_type', 'Unknown'), # 暂时复用 fraud_type
        "data_type": data_type,
        "language": "Chinese", 
        
        # 将诈骗文本放入 'generated text'，这是 LevelAttack 读取的字段
        "generated text": row.get('specific_dialogue_content', ''),
        
        # 保留原始信息备查
        "raw_data": row.get('specific_dialogue_content', ''),
        "interaction_strategy": row.get('interaction_strategy', ''),
        
        # 补充必要的默认字段，防止报错
        "role_bg": {
            "Sender": "未知发送者",
            "Receiver": "未知接收者",
            "Receiver_occupation": ["用户"]
        }
    }

def main():
    try:
        # 读取 CSV，自动处理编码问题
        try:
            df = pd.read_csv(SOURCE_FILE, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(SOURCE_FILE, encoding='gbk')
        
        print(f"成功读取文件，共 {len(df)} 条数据。")
        print(f"数据列名: {df.columns.tolist()}")

        # 过滤数据：只保留是诈骗的数据 (is_fraud == 1)
        if 'is_fraud' in df.columns:
            original_count = len(df)
            df = df[df['is_fraud'] == 1]
            print(f"过滤非诈骗数据 (is_fraud!=1) 后，剩余 {len(df)} 条。")

        # 转换数据
        new_data = []
        for idx, row in df.iterrows():
            # 确保内容不为空
            if pd.notna(row.get('specific_dialogue_content')):
                new_data.append(transform_row(row, len(new_data)))

        # 保存为 JSON
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, ensure_ascii=False, indent=4)
            
        print(f"转换完成！新数据集已保存至: {OUTPUT_FILE}")

    except FileNotFoundError:
        print(f"错误: 找不到文件 {SOURCE_FILE}，请确保文件在当前目录下。")
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main()