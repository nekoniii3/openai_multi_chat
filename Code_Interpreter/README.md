# Code Interpreter対応Chatアプリ

## 説明
GPT Assitants APIのCode Interpreter機能が利用できるChatアプリです。<br>
データの分析、グラフの作成などが簡単にできます。

<br>

**デモはこちら** <br>
https://huggingface.co/spaces/nekoniii3/GPT_Chat_Audio

<br>

## 利用方法

アシスタント作成が必要となります。<br>
create_assistant.pyを実行しコードインタープリターが利用できるアシスタントの作成を行ってください。
<br>

また以下の環境変数の設定が必要となります。   <br>

| 変数名 | 役割 | 推奨値 |
| :---:  | :---:  | :---:  |
| OPENAI_API_KEY | OpenAIのAPIキー | --- |
| ASSIST_ID | 作成したアシスタントID | --- |
| MAX_TRIAL | アシスタントへの最大問い合わせ回数 | 50 |
| INTER_SEC | アシスタントへの問い合わせ間隔(秒) | 3 |

<br>


