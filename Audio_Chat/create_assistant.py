# ※環境変数"OPENAI_API_KEY"にOpenAI APIキーをセットして下さい。

from openai import OpenAI

# モデルはGPT-4でも構いません
GPT_MODEL = "gpt-3.5-turbo-1106"

client = OpenAI()

assistant_ja = client.beta.assistants.create(
  name="Japanese Assistant",
  instructions="あなたは日本人の優秀なアシスタントです。質問は日本語で回答して下さい。",
  model=GPT_MODEL
)

assistant_en = client.beta.assistants.create(
  name="English teacher",
  instructions="You are an English teacher. Please be sure to answer in English.",
  model=GPT_MODEL
)


print(f"ASSIST_JA：{assistant_ja.id}")
print(f"ASSIST_EN：{assistant_en.id}")
print("として環境変数にセットして下さい。")