import os
import json
import random
from datetime import date, timedelta
from pathlib import Path
from gtts import gTTS
from playsound import playsound
from prettytable import PrettyTable
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models
from tencentcloud.common import credential
import re
import readchar

# 配置项
class Config:
    WORD_FILE = "words.txt"
    DATA_FILE = "learning_data.json"
    EXAMPLE_DB = "word_examples.json"
    MAX_SUCCESS_COUNT = 4  # 成功4次即掌握
    TTS_ENABLED = True      # 是否启用语音功能

# 腾讯混元大模型集成（需自行实现）
class HunyuanGenerator:
    def __init__(self, secret_id, secret_key):
    # 本地基础例句库
        self.local_db = {
            "apple": ["An apple a day keeps the doctor away.", 
                        "The apple pie smells delicious."],
            "book": ["This book is a masterpiece.",
                    "I borrowed the book from the library."]
        }
        # 初始化腾讯混元大模型
        cred = credential.Credential(secret_id, secret_key)
        self.client = hunyuan_client.HunyuanClient(cred, "ap-beijing")
    def split_ch_en(text):
        # 匹配中文字符及常见中文标点（范围包含大部分常用汉字和中文符号）
        ch_pattern = re.compile(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]+')
        
        # 查找第一个中文字符的位置
        match = ch_pattern.search(text)
        if not match:
            return text.strip(), ''
        
        split_pos = match.start()
        english = text[:split_pos].strip()
        chinese = text[split_pos:].strip()
        return english, chinese
    
    def get_example(self, word):
        """获取包含指定单词的例句"""
        try:
            # 验证输入
            if not word or not isinstance(word, str):
                print("⚠️ 无效的单词输入")
                return None
        
            # 准备请求
            req = models.ChatCompletionsRequest()
            req.Model = "hunyuan-lite"
            req.Messages = [
                {
                    "Role": "user",
                    "Content": f"请生成一包含英文单词'{word}'的例句，全部小写字母, 带中文翻译。输出格式为英文例句_中文翻译, 不要其他多余的输出"
                }
            ]
        
            # 设置超时时间
            self.client.set_timeout(10)  # 10秒超时
        
            # 发送请求
            resp = self.client.ChatCompletions(req)
            
            # 处理响应
            if not resp or not resp.Choices:
                print("⚠️ 未获取到有效响应")
                return None
        
            # 解析响应
            raw_list = resp.Choices[0].Message.Content.split('\n')
            if not raw_list:
                print("⚠️ 响应内容格式错误")
                return None
        
            # 返回随机例句
            return random.choice(raw_list)
        
        except Exception as e:
            print(f"⚠️ 获取例句失败: {str(e)}")
            # 返回本地例句库中的例句
            if word.lower() in self.local_db:
                return random.choice(self.local_db[word.lower()])
            return None

# 单词类
class Word:
    def __init__(self, english, chinese, success_count=0, next_review_date=None, example=None):
        self.english = english
        self.chinese = chinese
        self.success_count = success_count
        self.next_review_date = next_review_date or date.today()
        self.example = example

    def to_dict(self):
        return {
            'english': self.english,
            'chinese': self.chinese,
            'success_count': self.success_count,
            'next_review_date': self.next_review_date.isoformat(),
            'example': self.example
        }

    @classmethod
    def from_dict(cls, data):
        data['next_review_date'] = date.fromisoformat(data['next_review_date'])
        return cls(**data)

# 核心背诵系统
class WordReciter:
    def __init__(self):
        self.hunyuan = HunyuanGenerator("", "")
        self.all_words = []        # 待复习单词
        self.mastered_words = []   # 已掌握单词
        self.today = date.today()
        self.reviewed_mastered_words = set()  # 新增：记录已复习的已掌握词汇
        
        # 初始化数据
        self.example_db = self._load_example_db()
        self._load_data()
        self._process_overdue_words()

    def show_mastered_words(self):
        """显示已掌握词汇"""
        if not self.mastered_words:
            print("\n📚 您还没有掌握任何单词")
            return
            
        table = PrettyTable()
        table.title = "🎓 已掌握词汇"
        table.field_names = ["英文", "中文", "掌握日期", "已复习次数"]
        
        for word in self.mastered_words:
            # 计算已复习次数
            review_count = 1 if word.english in self.reviewed_mastered_words else 0
            table.add_row([
                word.english,
                word.chinese,
                word.next_review_date.strftime("%Y-%m-%d"),
                review_count
            ])
        
        print(table)
        print(f"\n📊 总计已掌握单词: {len(self.mastered_words)}")

    def review_mastered_words(self):
        """随机挑选10个已掌握词汇进行复习"""
        if not self.mastered_words:
            print("\n📚 您还没有掌握任何单词")
            return
            
        # 获取未复习过的单词
        available_words = [w for w in self.mastered_words if w.english not in self.reviewed_mastered_words]
        
        # 如果所有单词都已复习过，重置记录
        if not available_words:
            print("\n🎉 所有已掌握单词都已复习过一遍，现在重新开始")
            self.reviewed_mastered_words = set()
            available_words = self.mastered_words
            
        # 随机选择最多10个单词
        selected_words = random.sample(available_words, min(10, len(available_words)))
        
        print(f"\n📚 开始复习 {len(selected_words)} 个已掌握单词")
        for word in selected_words:
            self._practice_word(word)
            self.reviewed_mastered_words.add(word.english)
            self._save_data()  # 新增：每次复习后立即保存
            
        print("\n📊 本次复习完成！")

    def _load_example_db(self):
        """加载本地例句库"""
        try:
            with open(Config.EXAMPLE_DB) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _process_overdue_words(self):
        """处理过期单词"""
        for word in self.all_words:
            if word.next_review_date < self.today:
                word.next_review_date = self.today

    def _get_today_review_list(self):
        """获取今日复习列表"""
        return [w for w in self.all_words if w.next_review_date <= self.today]

    def show_status(self):
        """显示复习状态看板"""
        table = PrettyTable()
        table.title = "📅 单词复习看板"
        table.field_names = ["英文", "中文", "掌握进度", "下次复习", "剩余天数"]
        
        for word in sorted(self.all_words, key=lambda x: x.next_review_date):
            remaining_days = (word.next_review_date - self.today).days
            progress_bar = f"{word.success_count}/{Config.MAX_SUCCESS_COUNT} " + \
                          "★"*word.success_count + "☆"*(Config.MAX_SUCCESS_COUNT-word.success_count)
            
            table.add_row([
                word.english,
                word.chinese,
                progress_bar,
                word.next_review_date.strftime("%Y-%m-%d"),
                remaining_days if remaining_days > 0 else "今天"
            ])
        
        print(table)
        print(f"\n🎉 已掌握单词数量: {len(self.mastered_words)}")

    def _get_example(self, word):
        """获取最佳例句"""
        if word.example:
            return word.example
            
        # 优先使用NLTK获取例句
        try:
            import nltk
            from nltk.corpus import wordnet as wn
            nltk.download('wordnet', quiet=True)
            synsets = wn.synsets(word.english)
            if synsets:
                examples = synsets[0].examples()
                if examples:
                    return f"{examples[0]}_这是一个包含{word.chinese}的例句"
        except Exception as e:
            print(f"⚠️ NLTK获取例句失败: {str(e)}")
            
        # 尝试通过Hunyuan获取例句
        example = self.hunyuan.get_example(word.english)
        if example:
            return example
            
        # 本地例句库
        if word.english.lower() in self.example_db:
            return random.choice(self.example_db[word.english.lower()])
            
        # 生成默认例句
        return f"This is an example sentence with {word.english}_这是一个包含{word.chinese}的例句"

    def _text_to_speech(self, text):
        """文本转语音"""
        if not Config.TTS_ENABLED:
            return
    
        try:
            # 确保文本有效
            if not text or not isinstance(text, str):
                print("⚠️ 无效的文本输入")
                return
    
            # 提取英文部分
            en_text = text.split('_')[0]
            if not en_text:
                print("⚠️ 无法提取有效的英文文本")
                return
            
            # 使用macOS自带的say命令
            os.system(f'say "{en_text}"')
        except Exception as e:
            print(f"⚠️ 语音生成过程中发生错误: {str(e)}")

    def _practice_word(self, word):
        """单个单词练习流程"""
        print(f"\n{'━'*30}")
        print(f"🔔 当前进度: {word.success_count}/{Config.MAX_SUCCESS_COUNT}")
        
        # 显示例句
        example = self._get_example(word)
        if '_' in example:
            first_occurrence = example.index('_')
            # 保留第一个下划线，后续所有下划线删除
            example = example[:first_occurrence+1] + example[first_occurrence+1:].replace('_', '')

        if not word.example: 
            word.example = example
        
        en_example, zh_example = example.split('_') if '_' in example else (example, "")
        
        # 忽略大小写进行替换
        lower_en_example = en_example.lower()
        lower_word = word.english.lower()
        start_index = lower_en_example.find(lower_word)
        if start_index != -1:
            end_index = start_index + len(word.english)
            blanked_part = '_' * len(word.english) + f"({len(word.english)})"
            blanked_example = en_example[:start_index] + blanked_part + en_example[end_index:]
        else:
            blanked_example = en_example
        
        print(f"📖 中文释义: {word.chinese}")
        print(f"📝 例句: {blanked_example}")
        if zh_example:
            print(f"🌏 例句翻译: {zh_example}")

        # 拼写测试
        attempt = 0
        while attempt < 3:
            answer = ""
            print("请输入英文单词（h=显示答案，s=播放语音）: ", end='', flush=True)
            while True:
                char = readchar.readchar()
                if char == '\n':  # 回车提交答案
                    break
                elif char == '\x7f':  # 退格键
                    if answer: 
                        answer = answer[:-1]
                        print(' ', end='', flush=True)  # 清除显示的字符
                else: 
                    answer += char
                    print(char, end='', flush=True)
                # 在同一行更新输入提示和字母计数
                print(f"\r已输入 {len(answer)} 个字母。请输入英文单词（h=显示答案，s=播放语音）: {answer}", end='', flush=True)

            answer = answer.strip().lower()
            if answer == "h":
                print(f"\n📢 正确答案: {word.english}")
                return False
            if answer == "s":
                self._text_to_speech(example)
                print("\n")  # 新增换行
                continue
            if answer == word.english.lower():
                print("\n✅ 正确！")
                self._text_to_speech(example)
                return True
            attempt += 1
            print(f"\n❌ 错误（剩余尝试次数 {3 - attempt}）")

        print(f"\n📢 正确答案: {word.english}")
        return False

    def daily_review(self):
        """执行每日复习"""
        review_list = self._get_today_review_list()
        if not review_list:
            print("\n🎉 今日没有需要复习的单词！")
            return

        print(f"\n📚 今日需要复习 {len(review_list)} 个单词")
        random.shuffle(review_list)  # 打乱顺序
        
        mastered_today = 0
        total_words = len(review_list)
        for index, word in enumerate(review_list.copy(), start=1):
            print(f"\n⏳ 剩余 {total_words - index + 1} 个单词需要复习")
            success = self._practice_word(word)
            
            # 更新单词状态
            if success:
                word.success_count += 1
                
                if word.success_count >= Config.MAX_SUCCESS_COUNT:
                    self.mastered_words.append(word)
                    self.all_words.remove(word)
                    mastered_today += 1
                    print(f"🎉 已掌握单词: {word.english}")
                else:
                    # 设置下次复习时间
                    delta_days = word.success_count
                    word.next_review_date = self.today + timedelta(days=delta_days)
                    print(f"⏱ 下次复习: {word.next_review_date} (+{delta_days}天)")
            else:
                print("⏳ 保持原复习计划")

        # 保存进度
        self._save_data()
        
        # 显示日报
        print("\n📊 今日复习报告:")
        report = PrettyTable()
        report.field_names = ["统计项", "数量"]
        report.add_row(["复习单词总数", len(review_list)])
        report.add_row(["新掌握单词", mastered_today])
        report.add_row(["当前进度", f"{len(self.mastered_words)} 已掌握 / {len(self.all_words)} 待复习"])
        print(report)

    def add_words(self, words):
        """批量添加单词"""
        existing_words = {w.english.lower() for w in self.all_words + self.mastered_words}
        new_words = []
        
        for en, zh in words:
            if en.lower() not in existing_words:
                new_words.append(Word(en, zh))
                existing_words.add(en.lower())
        
        self.all_words.extend(new_words)
        self._save_data()
        print(f"✅ 成功添加 {len(new_words)} 个新单词")

    def _load_data(self):
        """加载学习数据"""
        try:
            with open(Config.DATA_FILE) as f:
                data = json.load(f)
                self.all_words = [Word.from_dict(w) for w in data['all_words']]
                self.mastered_words = [Word.from_dict(w) for w in data['mastered_words']]
                self.reviewed_mastered_words = set(data.get('reviewed_mastered_words', []))
                
                # 新增统计信息
                total_words = len(self.all_words) + len(self.mastered_words)
                mastered_count = len(self.mastered_words)
                reviewed_count = len(self.reviewed_mastered_words)
                print(f"📊 单词统计: 总计 {total_words} 个 | 已掌握 {mastered_count} 个 | 已复习 {reviewed_count} 个")
        except FileNotFoundError:
            print(f"⚠️ 数据文件 {Config.DATA_FILE} 不存在，将创建新文件")
            self.all_words = []
            self.mastered_words = []
            self.reviewed_mastered_words = set()
            print("📊 单词统计: 总计 0 个 | 已掌握 0 个 | 已复习 0 个")
        except json.JSONDecodeError as e:
            print(f"⚠️ 数据文件 {Config.DATA_FILE} 格式错误: {str(e)}")
            print("⚠️ 可能是文件损坏，将重置为初始状态")
            self.all_words = []
            self.mastered_words = []
            self.reviewed_mastered_words = set()
            print("📊 单词统计: 总计 0 个 | 已掌握 0 个 | 已复习 0 个")

    def _save_data(self):
        """保存学习数据"""
        data = {
            'all_words': [w.to_dict() for w in self.all_words],
            'mastered_words': [w.to_dict() for w in self.mastered_words],
            'reviewed_mastered_words': list(self.reviewed_mastered_words)  # 新增
        }
        with open(Config.DATA_FILE, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# 用户界面
class ReciterCLI:
    def __init__(self):
        self.reciter = WordReciter()
        
    def main_menu(self):
        while True:
            print("\n"+ "="*30)
            print("  智能单词背诵系统")
            print("="*30)
            print("1. 开始今日复习")
            print("2. 查看学习进度")
            print("3. 导入单词文件")
            print("4. 查看已掌握词汇")
            print("5. 复习已掌握词汇")
            print("6. 退出系统")
            
            choice = input("请选择操作: ").strip()
            
            if choice == '1':
                self.reciter.daily_review()
            elif choice == '2':
                self.reciter.show_status()
            elif choice == '3':
                self._import_file()
            elif choice == '4':
                self.reciter.show_mastered_words()
            elif choice == '5':
                self.reciter.review_mastered_words()
            elif choice == '6':
                print("👋 再见！")
                break
            else:
                print("⚠️ 无效的选项")

    def _import_file(self):
        path = input(f"输入文件路径（默认{Config.WORD_FILE}）: ").strip() or Config.WORD_FILE
        try:
            with open(path, encoding='utf-8') as f:
                words = [line.strip().split(',', 1) for line in f if ',' in line]
                self.reciter.add_words(words)
        except Exception as e:
            print(f"⚠️ 导入失败: {str(e)}")

if __name__ == "__main__":
    cli = ReciterCLI()
    cli.main_menu()