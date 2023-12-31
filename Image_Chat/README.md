# OpenAI画像入力対応Chatアプリ

## 説明
DALL·E 3とGPT-4 with Visionが利用できるChatアプリです。<br>
どちらを使うかはプロンプトからFunctionCallingで自動で判断されます。

<br>

**デモはこちら** <br>
https://huggingface.co/spaces/nekoniii3/GPT_Chat_Image

<br>

## 利用方法

関数情報をセットしたアシスタント作成が必要となります。<br>
create_assistant.pyを実行し日本語と英語のアシスタントの作成を行ってください。
<br>

また以下の環境変数の設定が必要となります。   <br>

| 変数名 | 役割 | 推奨値 |
| :---:  | :---:  | :---:  |
| OPENAI_API_KEY | OpenAIのAPIキー | --- |
| IL_ASSIST_ID | 作成したアシスタントID | --- |
| MAX_TRIAL | アシスタントへの最大問い合わせ回数 | 50 |
| INTER_SEC | アシスタントへの問い合わせ間隔(秒) | 1 |
| MAX_TOKENS | Visionの最大トークン | 1000など |

<br>


