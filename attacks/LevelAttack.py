import os
import json
import time
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from attacks.Attack import Attack
from attacks.attack_utils.GPTCheck import GPTCheck 
from attacks.attack_utils.PromptStorage import start_prompt, more_prompt

class LevelAttack(Attack):
    def __init__(self, file_name, model, output_file, task, scenario):
        super().__init__()
        self.model = model
        self.output_file = output_file
        self.file_name = file_name
        self.task = task
        self.scenario = scenario
        # 并发线程数
        self.max_workers = 5 

    def process_fraud_data(self):
        if not self.file_name.endswith(".json"):
            return

        with open(self.file_name, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 确定任务类型对应的 key
        if self.task == "one-round":
            print(f"Processing one-round attacking (Threads: {self.max_workers})...")
            model_response_key = "one-round response"
        elif self.task == "multi-round":
            print(f"Processing multi-round attacking (Threads: {self.max_workers})...")
            model_response_key = "GPT judge"
        elif self.task == "one-round-eval":
            print(f"Processing one-round GPT checking (Threads: {self.max_workers})...")
            model_response_key = "one-round judge"
        else:
            print("unknown task")
            return

        # 定义单条处理函数（供线程调用）
        def process_entry(index, entry):
            if self.task == "multi-round":
                if "GPT judge" in entry and entry.get("GPT judge") != "":
                    multi_rounds = entry.get("multi-rounds fraud", [])
                    all_filled = True
                    for round_item in multi_rounds:
                        if "model response" in round_item and round_item["model response"] == "":
                            all_filled = False
                            break
                    if all_filled:
                        return False # Skipped
            else:
                if model_response_key in entry and entry.get(model_response_key) != "":
                    return False # Skipped

            try:
                if self.task == "one-round":
                    self.process_one_round(entry)
                elif self.task == "multi-round":
                    self.process_multi_round(entry)
                elif self.task == "one-round-eval":
                    self.process_one_round_judge(entry)
            except Exception as e:
                print(f"Error processing item {index}: {e}")
            
            return True # Processed

        # 多线程并发执行
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            futures = {executor.submit(process_entry, idx, item): idx for idx, item in enumerate(data)}
            
            # 进度条
            for future in tqdm(as_completed(futures), total=len(data), desc="Processing"):
                future.result()

        # 统一保存结果
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        print(f"All finished! Saved to {self.output_file}")
    
    def process_one_round_judge(self, entry):
        checker = GPTCheck()
        language = entry.get("language")
        response_content = entry.get("one-round response")

        judge_result = checker.judge(response_content, language)
        entry["one-round judge"] = judge_result

    def process_one_round(self, entry):
        try:
            from attacks.attack_utils.PromptStorage import synonym_prompt
            if self.scenario == 'ablation':
                prompt = synonym_prompt(entry)
            else:
                prompt = start_prompt(entry, self.scenario, self.task)
        except ImportError:
            prompt = start_prompt(entry, self.scenario, self.task)

        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # 初始化模型
        client = self.init_model(self.model)

        # 获取回复
        response = self.get_response(messages, client, self.model)
        
        if not response or not hasattr(response, "choices") or not response.choices:
            response_content = ""
        else:
            try:
                response_content = response.choices[0].message.content.strip()
            except (AttributeError, IndexError, json.JSONDecodeError) as e:
                response_content = ""

        # 尝试解析 JSON，如果不是 JSON 则直接存字符串
        try:
            entry["one-round response"] = json.loads(response_content)
        except json.JSONDecodeError:
            entry["one-round response"] = response_content

    def _truncate_text(self, text, max_length=512):
        return text[:max_length] if len(text) > max_length else text

    def truncate_conversation_messages(self, messages, max_length=512):
        truncated = []
        for msg in messages:
            new_msg = {"role": msg["role"], "content": ""}
            truncated_text = self._truncate_text(msg["content"], max_length)
            new_msg["content"] = truncated_text
            truncated.append(new_msg)
        return truncated


    def process_multi_round(self, entry):
        checker = GPTCheck()
        language = entry.get("language")
        
        conversation_messages = []
        
        client = self.init_model(self.model)
        
        total_rounds = 4
        if "multi-rounds fraud" not in entry or not isinstance(entry["multi-rounds fraud"], list):
            entry["multi-rounds fraud"] = []
        while len(entry["multi-rounds fraud"]) < total_rounds:
            entry["multi-rounds fraud"].append({})
        
        for round_num in range(1, total_rounds + 1):
            # 第一轮检查
            if round_num == 1 and entry.get("one-round response", "").strip() != "" and entry.get("one-round judge", "").strip() in ["YES", "NO", "NEXT ROUND"]:
                prompt = start_prompt(entry, self.scenario, self.task, rounds=1)
                conversation_messages.append({"role": "user", "content": prompt})
                conversation_messages.append({"role": "assistant", "content": entry["one-round response"]})
                
                round_dict = entry["multi-rounds fraud"][0]
                round_dict["round"] = 1
                round_dict["model response"] = entry["one-round response"]
                round_dict["GPT check"] = entry["one-round judge"]
                
                if "NEXT ROUND" not in entry["one-round judge"] and entry["one-round judge"] != "NEXT ROUND":
                    break
                continue  

            if round_num == 1:
                prompt = start_prompt(entry, self.scenario, self.task, rounds=1)
            else:
                prompt = more_prompt(entry, self.scenario, self.task, rounds=round_num)
            
            current_user_message = {"role": "user", "content": prompt}
            messages_to_send = self.truncate_conversation_messages(conversation_messages, 512) + [current_user_message]
            
            response = self.get_response(messages_to_send, client, self.model)
            if not response or not hasattr(response, "choices") or not response.choices:
                response_content = ""
            else:
                try:
                    response_content = response.choices[0].message.content.strip()
                except Exception:
                    response_content = ""
            
            round_dict = entry["multi-rounds fraud"][round_num - 1]
            round_dict["round"] = round_num
            round_dict["model response"] = response_content
            
            if not response_content:
                conversation_messages.append(current_user_message)
                conversation_messages.append({"role": "assistant", "content": ""})
                continue
            
            conversation_messages.append(current_user_message)
            conversation_messages.append({"role": "assistant", "content": response_content})
            
            check_result = checker.judge(response_content, language)
            round_dict["GPT check"] = check_result
            
            if "NEXT ROUND" not in check_result and check_result != "NEXT ROUND":
                break
        
        final_result = None
        for r in entry["multi-rounds fraud"]:
            if "GPT check" in r and r["GPT check"] in ["YES", "NO"]:
                final_result = r["GPT check"]
                break
        if final_result is None:
            final_result = "NO"
        entry["GPT judge"] = final_result
        entry["truncated conversation history"] = conversation_messages