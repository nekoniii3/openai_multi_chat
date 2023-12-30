# OpenAI音声対応Chatアプリ

## 説明
GPT Assitantを利用した音声での入出力ができるChatアプリです。<br>
①通常会話 ②英会話 ③英語翻訳 の3モードが利用できます。

デモはこちら<br>
https://huggingface.co/spaces/nekoniii3/GPT_Chat_Audio

<br>

## 利用方法

アシスタント作成が必要となります。<br>
create_assistant.pyを実行し日本語と英語のアシスタントの作成を行ってください。
<br>

また以下の環境変数の設定が必要となります。   <br>

| 変数名 | 役割 | 推奨値 |
| :---:  | :---:  | :---:  |
| OPENAI_API_KEY | OpenAIのAPIキー | --- |
| ASSIST_JA | 作成したアシスタントID（日本語） | --- |
| ASSIST_EN | 作成したアシスタントID（英語） | --- |
| MAX_TRIAL | アシスタントへの最大問い合わせ回数 | 50 |
| INTER_SEC | アシスタントへの問い合わせ間隔(秒) | 1 |

<br>


