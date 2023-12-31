# ※環境変数"OPENAI_API_KEY"にOpenAI APIキーをセットして下さい。
# 　モデルやインストラクションは変更して問題ありません。

from openai import OpenAI

DF_INSTRUCTIONS = "あなたはイラストレーターです。提供されている関数を使用して画像を作ったり、画像を解析したりします。"
DF_MODEL = "gpt-3.5-turbo-1106"

# 関数情報
func_Dall_E3 = {
        "type": "function",
        "function": {
            "name": "request_DallE3",
            "description": "画像生成AI「dall-e-3」で指定のPromptから画像を作る。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "画像を作るためのPrompt"},
                },
                "required": ["prompt"]
            }
        }
    }

func_Vision = {
        "type": "function",
        "function": {
            "name": "request_Vision",
            "description": "画像解析技術「Vision」により、指定の画像に関する質問に回答する。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "画像に対する質問内容（Prompt）"},
                },
                "required": ["prompt"]
            }
        }
    } 

# クライアント新規作成
client = OpenAI()

# アシスタント作成
assistant = client.beta.assistants.create(
    name="GPT_Illustrator",
    instructions=DF_INSTRUCTIONS,
    model=DF_MODEL,
    tools=[func_Vision, func_Dall_E3]
)

print('こちらが作成したアシスタントのIDです。環境変数に"IL_ASSIST_ID"としてセットして下さい。')
print(assistant.id)