# ※環境変数"OPENAI_API_KEY"にOpenAI APIキーをセットして下さい。

from openai import OpenAI

# モデルはGPT-4でも構いません
GPT_MODEL = "gpt-3.5-turbo-1106"

client = OpenAI()

assistant = client.beta.assistants.create(
  name="ast_code_interpreter",
  instructions="あなたは優秀なアシスタントです。質問をされた場合は、質問に答えるコードを作成して実行します。",
  model=GPT_MODEL,
  tools=[{"type": "code_interpreter"}]
)


print(f"ASSIST_ID：{assistant.id}")
print("として環境変数にセットして下さい。")