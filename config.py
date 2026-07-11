import os
from dotenv import load_dotenv


# 加载 .env 文件
load_dotenv()


# DeepSeek API Key
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


# DeepSeek API 地址
DEEPSEEK_BASE_URL = "https://api.deepseek.com"