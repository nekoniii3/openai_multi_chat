import os
import json
import base64
import re
import time
import datetime
from zoneinfo import ZoneInfo
from PIL import Image
from io import BytesIO
import shutil
import gradio as gr
from openai import (
    OpenAI, AuthenticationError, NotFoundError, BadRequestError
)


# GPT用設定
DF_INSTRUCTIONS = "あなたはイラストレーターです。提供されている関数を使用して画像を作ったり、画像を解析したりします。"
DF_MODEL = "gpt-3.5-turbo-1106"
DUMMY = "********************"
file_format = {".png", ".jpeg", ".jpg", ".webp", ".gif", ".PNG", ".JPEG", ".JPG", ".WEBP", ".GIF"}

# 各種出力フォルダ
# IMG_FOLDER = "sample_data"   #"images"

# 各種メッセージ
PLACEHOLDER = "DaLL-E3を利用の場合「『○○』で画像を作ってください。」\nVisionを利用の場合「この画像について説明して下さい。」など入力して下さい。"
# IMG_MSG = "(画像ファイルを追加しました。リセットボタンの上に表示されています。)"
DEL_MSG = "こちらをクリックして表示"
ANT_MSG = "（下部の[出力ファイル]にファイルを追加しました。）"

# 各種設定値
MAX_TRIAL = int(os.environ["MAX_TRIAL"])  # メッセージ取得最大試行数
INTER_SEC = int(os.environ["INTER_SEC"])   # 試行間隔（秒）
MAX_TOKENS = int(os.environ["MAX_TOKENS"])  # Vison最大トークン

# 正規表現用パターン
pt = r".*\[(.*)\]\((.*)\)"

# サンプル用情報
examples = ["1980s anime girl with straight bob-cut in school uniform, roughly drawn drawing"
          , "a minimalisit logo for a sporting goods company"]
          # , "この画像について説明して下さい。"]


# 各関数定義
def set_state(openai_key, size, quality, detail, state):
    """ 設定タブの情報をセッションに保存する関数 """

    state["openai_key"] = openai_key
    state["size"] = size
    state["quality"] = quality
    state["detail"] = detail

    return state


def init(state, text, image):
    """ 入力チェックを行う関数 """
    """ ※ここで例外を起こすと入力できなくなるので次の関数でエラーにする """

    err_msg = ""

    if not text:

        # テキスト未入力
        err_msg = "プロンプトを入力して下さい。"

        return state, err_msg

    elif image:

        # 入力画像のファイル形式チェック
        root, ext = os.path.splitext(image)

        if ext not in file_format:

            # ファイル形式チェック
            err_msg = "指定した形式のファイルをアップしてください。（注意事項タブに記載）"

            return state, err_msg

    try:

        if state["client"] is None:

            # クライアント新規作成
            client = OpenAI()

            # セッションにセット
            state["client"] = client

            # IDとして現在時刻をセット
            dt = datetime.datetime.now(ZoneInfo("Asia/Tokyo"))
            state["user_id"] = dt.strftime("%Y%m%d%H%M%S")

        else:

            # 既存のクライアントをセット
            client = state["client"]


        if state["thread_id"] == "":

            # スレッド作成
            thread = client.beta.threads.create()

            state["thread_id"] = thread.id


        if state["assistant_id"] == "":

            # アシスタントIDセット
            state["assistant_id"] = os.environ["IL_ASSIST_ID"]


        # ユーザIDでフォルダ作成
        os.makedirs(state["user_id"], exist_ok=True)

    # except NotFoundError as e:
    #     err_msg = "アシスタントIDが間違っています。新しく作成する場合はアシスタントIDを空欄にして下さい。"
    except AuthenticationError as e:
        err_msg = "認証エラーとなりました。OpenAPIKeyが正しいか、支払い方法などが設定されているか確認して下さい。"
    except Exception as e:
        err_msg = "その他のエラーが発生しました。"
        print(e)
    finally:
        return state, err_msg


def raise_exception(err_msg):
    """ エラーの場合例外を起こす関数 """

    if err_msg != "":
        raise Exception("これは入力チェックでの例外です。")

    return


def add_history(history, text, image):
    """ Chat履歴"history"に追加を行う関数 """

    err_msg = ""

    if image is None or image == "":

        # テキストだけの場合そのまま追加
        history = history + [(text, None)]

    elif image is not None:

        # 画像があれば画像とテキストを追加
        history = history + [((image,), DUMMY)]
        history = history + [(text, None)]

    # テキストは利用不可・初期化し、画像は利用不可に
    update_text = gr.update(value="", placeholder = "",interactive=False)
    update_file = gr.update(interactive=False)

    return history, update_text, update_file, err_msg


def bot(state, history, image_path):
    """ GPTへ問い合わせChat画面に表示する関数 """

    err_msg = ""
    out_image_path = None
    image_preview = False

    ant_file = None

    # セッション情報取得
    client = state["client"]
    assistant_id = state["assistant_id"]
    thread_id = state["thread_id"]
    last_msg_id = state["last_msg_id"]
    user_id = state["user_id"]
    image_count = state["image_count"]

    # メッセージ設定
    message = client.beta.threads.messages.create(
    thread_id=thread_id,
    role="user",
    content=history[-1][0],
    )

    # RUNスタート
    run = client.beta.threads.runs.create(
      thread_id=thread_id,
      assistant_id=assistant_id,
      # instructions=system_prompt
    )

    # "completed"となるまで繰り返す（指定秒おき）
    for i in range(0, MAX_TRIAL, 1):

        if i > 0:
          time.sleep(INTER_SEC)

        # 変数初期化
        tool_outputs = []

        # メッセージ受け取り
        run = client.beta.threads.runs.retrieve(
          thread_id=thread_id,
          run_id=run.id
        )

        if run.status == "requires_action":   # 関数の結果の待ちの場合

            # tool_callsの各項目取得
            tool_calls = run.required_action.submit_tool_outputs.tool_calls

            # 一つ目だけ取得
            tool_id = tool_calls[0].id
            func_name = tool_calls[0].function.name
            func_args = json.loads(tool_calls[0].function.arguments)

            if func_name == "request_DallE3":

                # ファイル名は現在時刻に
                dt = datetime.datetime.now(ZoneInfo("Asia/Tokyo"))
                image_name = dt.strftime("%Y%m%d%H%M%S") + ".png"

                # ファイルパスは手動設定（誤りがないように）
                out_image_path = user_id + "/" + image_name

                # dall-e3のとき"image_path"は出力ファイルパス
                func_args["image_path"] = out_image_path

            elif func_name == "request_Vision":

                if image_path is None:

                    # 画像がない場合エラーとなるようにする
                    func_args["image_path"] = ""

                else:

                    # ファイルパスは手動設定
                    func_args["image_path"] = image_path

            else:

                # 関数名がないなら次へ
                continue

            # 関数を実行
            func_output = func_action(state, func_name, func_args)

            # tool_outputリストに追加
            tool_outputs.append({"tool_call_id": tool_id, "output": func_output})

            # 複数の関数が必要な場合
            if len(tool_calls) > 1:

                # for i in range(len(tool_calls) - 1):
                for i, tool_call in enumerate(tool_calls):

                    if i > 0:

                         # ダミー をセットする
                        tool_outputs.append({"tool_call_id": tool_call.id, "output": '{"answer" : ""}'})

            # 関数の出力を提出
            run = client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )

            if func_name == "request_DallE3":

                  # 画像の表示をする
                  image_preview = True

            # セッション更新
            # history_outputs += tool_outputs
            # state["tool_outputs"] = history_outputs

        else:

            # 前回のメッセージより後を昇順で取り出す
            messages = client.beta.threads.messages.list(
              thread_id=thread_id,
              after=last_msg_id,
              order="asc"
            )

            # messageを取り出す
            for msg in messages:

                if msg.role == "assistant":

                    for content in msg.content:

                        res_text = ""
                        file_id = ""

                        cont_dict = content.model_dump()  # 辞書型に変換

                        # 返答テキスト取得
                        res_text = cont_dict["text"].get("value")

                        if res_text != "":

                            # テキストを変換（"sandbox:"などを」消す）
                            result = re.search(pt, res_text)

                            if result:

                                # パターン一致の場合はプロンプトだけ抜き出す
                                res_text = result.group(1)

                                # 「こちらをクリックして表示」は削除
                                res_text = res_text.replace(DEL_MSG, "")

                            # Chat画面更新
                            if history[-1][1] is not None:

                                # 新しい行を追加
                                history = history + [[None, res_text]]

                            else:

                                history[-1][1] = res_text

                            if image_preview:

                                # Functionで画像を取得していた場合表示
                                history = history + [(None, (out_image_path,))]

                                image_count += 1

                                image_preview = False

                            # 最終メッセージID更新
                            last_msg_id = msg.id

                    # Chatbotを返す（labelとhistoryを更新）
                    yield gr.Chatbot(label=run.status ,value=history), out_image_path, ant_file, err_msg

            # セッションのメッセージID更新
            state["last_msg_id"] = last_msg_id
            state["image_count"] = image_count

            # 完了なら終了
            if run.status == "completed":

                yield gr.Chatbot(label=run.status ,value=history), out_image_path, ant_file, err_msg
                break

            elif run.status == "failed":

                # エラーとして終了
                err_msg = "※メッセージ取得に失敗しました。"
                yield gr.Chatbot(label=run.status ,value=history), out_image_path, ant_file, err_msg
                break

            elif i == MAX_TRIAL:

                # エラーとして終了
                err_msg = "※メッセージ取得の際にタイムアウトしました。"
                yield gr.Chatbot(label=run.status ,value=history), out_image_path, ant_file, err_msg
                break

            else:
                if i > 3:

                    # 作業中とわかるようにする
                    yield gr.Chatbot(label=run.status + " (Request:" + str(i) + ")" ,value=history), out_image_path, ant_file, err_msg


def func_action(state, func_name, func_args):
    """ functionを実行する関数 """

    # セッションから情報取得
    client = state["client"]
    size = state["size"]
    quality = state["quality"]
    detail = state["detail"]

    if func_name == "request_DallE3":

        func_output = request_DallE3(
            client,
            func_args["prompt"],
            size,
            quality,
            func_args["image_path"]   # 出力パス
        )

    elif func_name == "request_Vision":

        func_output = request_Vision(
            client,
            func_args["prompt"],
            func_args["image_path"],
            detail,
            MAX_TOKENS
        )

    return func_output

def finally_proc():
    """ 最終処理用関数 """

    # テキストを使えるように
    new_text = gr.update(interactive = True)

    # 画像はリセット
    new_image = gr.update(value=None, interactive = True)

    return new_text, new_image


def clear_click(state):
    """ クリアボタンクリック時 """

    # セッションの一部をリセット
    state["thread_id"] = ""
    state["last_msg_id"] = ""

    # 順番的にgr.ClearButtonで消せないImageなども初期化
    return state, None, None


def make_archive(state):
    """ 画像のZIP化・一括ダウンロード用関数 """

    dir = state["user_id"]

    if dir is None or dir == "":

        return None, ""

    if len(os.listdir(dir)) == 0:

        return None, ""

    shutil.make_archive(dir, format='zip', root_dir=dir)

    return dir + ".zip", "下部の出力ファイルからダウンロードして下さい。"


def encode_image(image_path):
    """ base64エンコード用関数 """

    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def make_prompt(prompt):
    """ サンプル用関数 """

    return "次のプロンプトで画像を作ってください「" + prompt + "」。"


# 画面構成
with gr.Blocks() as demo:

    title = "<h2>GPT画像入出力対応チャット</h2>"
    message = "<h3>・DallE3の画像生成とGPT-4 with Visionの画像解析が利用できます。<br>"
    message += "・DallE3を利用する場合はプロンプト、GPT-4 Visionを利用する場合は画像とプロンプトを入力して下さい。<br>"
    message += "・OpenAIのAPIKEYを入力しないと動きません。（設定タブ）<br>"
    message += "・動画での紹介はこちら→https://www.youtube.com/watch?v=CIxVPNBMFQw<br>"
    message += "</h3>"

    gr.Markdown(title + message)

    # セッションの宣言
    state = gr.State({
        # "system_prompt": SYS_PROMPT_DEFAULT,
        "openai_key" : "",
        "size" : "1024x1024",
        "quality" : "standard",
        "detail" : "low",
        "client" : None,
        "assistant_id" : "",
        "thread_id" : "",
        "last_msg_id" : "",
        "user_id" : "",
        "image_count" : 0
    })

    with gr.Tab("Chat画面") as chat:

      # 各コンポーネント定義
      chatbot = gr.Chatbot(label="チャット画面")
      text_msg = gr.Textbox(label="プロンプト", lines = 2, placeholder = PLACEHOLDER)
      text_dummy = gr.Textbox(visible=False)
      gr.Examples(label="サンプルプロンプト", examples=examples, inputs=text_dummy, outputs=text_msg, fn=make_prompt,  cache_examples=True)

      with gr.Row():
        btn = gr.Button(value="送信")
        btn_dl = gr.Button(value="画像の一括ダウンロード")  # 保留中
        btn_clear = gr.ClearButton(value="リセット", components=[chatbot, text_msg])

      sys_msg = gr.Textbox(label="システムメッセージ", interactive = False)

      with gr.Row():
        image = gr.Image(label="ファイルアップロード", type="filepath",interactive = True)
        out_image = gr.Image(label="出力画像", type="filepath", interactive = False)

      # out_text = gr.Textbox(label="出力テキスト", lines = 5, interactive = False)
      out_file = gr.File(label="出力ファイル", type="filepath",interactive = False)

      # 送信ボタンクリック時の処理
      bc = btn.click(init, [state, text_msg, image], [state, sys_msg], queue=False).success(
          raise_exception, sys_msg, None).success(
          add_history, [chatbot, text_msg, image], [chatbot, text_msg, image, sys_msg], queue=False).success(
          bot, [state, chatbot, image],[chatbot, out_image, out_file, sys_msg]).then(
          finally_proc, None, [text_msg, image], queue=False
      )
      btn_dl.click(make_archive, state, [out_file, sys_msg])
      # クリア時でもセッションの一部は残す（OpenAIKeyなど）
      btn_clear.click(clear_click, state, [state, image ,out_image])

      # テキスト入力Enter時の処理
      # txt_msg = text_msg.submit(respond, inputs=[text_msg, image, chatbot], outputs=[text_msg, image, chatbot])

    with gr.Tab("設定") as set:

      gr.Markdown("<h4>OpenAI設定</h4>")
      with gr.Row():
        openai_key = gr.Textbox(label="OpenAI API Key")   # テスト中は表示せず
      # system_prompt = gr.Textbox(value = SYS_PROMPT_DEFAULT,lines = 5, label="Custom instructions", interactive = True)
      gr.Markdown("<h4>DaLL-E3用設定</h4>")
      with gr.Row():
        size = gr.Dropdown(label="サイズ", choices=["1024x1024"], value = "1024x1024", interactive = True)
        quality = gr.Dropdown(label="クオリティ", choices=["standard"], value = "standard", interactive = True)
      gr.Markdown("<h4>Vison用設定</h4>")
      with gr.Row():
        detail = gr.Dropdown(label="コード出力", choices=["low", "high" , "auto"], value = "low", interactive = True)

      # 設定タブからChatタブに戻った時の処理
      chat.select(set_state, [openai_key, size, quality, detail, state], state)

    with gr.Tab("注意事項") as notes:
            caution = '・動いているかわかりづらいですが、左上の"in_progress(Request:XX)"が止まっていなければ回答の生成中となります。<br>'
            caution += "・[画像一括ダウンロード]を押すと、下部[出力ファイル]にZIPファイルができます。<br>"
            caution += "・画像を生成した際、チャット画面に「こちらをクリック」となる場合がありますが画像は[出力画像]に表示されます。<br>"
            caution += "・テスト中はDaLL-E3用設定は固定となっております。<br>"
            caution += "・現在画像から画像を作るimg2imgはできません。<br>"
            caution += "・こういうときにエラーになるなどフィードバックあればお待ちしています。"
            gr.Markdown("<h3>" + caution + "</h3>")


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

def request_DallE3(client, prompt, size, quality, out_image_path):

    err_msg = ""

    try:

        response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=size,
        quality=quality,
        n=1,
        response_format="b64_json"
        )

        # データを受け取りデコード
        image_data_json = response.data[0].b64_json
        image_data = base64.b64decode(image_data_json)

        # 画像として扱えるように保存
        image_stream = BytesIO(image_data)
        image = Image.open(image_stream)
        image.save(out_image_path)

    except BadRequestError as e:
        print(e)
        out_image_path = ""
        err_msg = "リクエストエラーです。著作権侵害などプロンプトを確認して下さい。"
    except Exception as e:
        print(e)
        out_image_path = ""
        err_msg = "その他のエラーが発生しました。"

    finally:

        # 結果をJSONで返す
        dalle3_result = {
            "image_path" : out_image_path,
            "error_message" : err_msg
        }
        return json.dumps(dalle3_result)


def request_Vision(client, prompt, image_path, detail, max_tokens):

    response_text = ""
    err_msg = ""

    if image_path == "":

        # 画像がない時はエラーとして返す
        vision_result = {"answer" : "", "error_message" : "画像をセットして下さい。"}
        return json.dumps(vision_result)

    try:

        # 画像をbase64に変換
        image = encode_image(image_path)

        # メッセージの作成
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image}",
                            "detail": detail,
                        }
                    },
                ],
            }
        ]

        # gpt-4-visionに問い合わせて回答を表示
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",   # Visionはこのモデル指定
            messages=messages,
            max_tokens=max_tokens,
        )

        response_text = response.choices[0].message.content

    except BadRequestError as e:
        print(e)
        err_msg = "リクエストエラーです。画像がポリシー違反でないか確認して下さい。"
    except Exception as e:
        print(e)
        err_msg = "その他のエラーが発生しました。"

    finally:

        # 結果をJSONで返す
        vision_result = {
            "answer" : response_text,
            "error_message" : err_msg
        }
        return json.dumps(vision_result)
    
    
if __name__ == '__main__':

    demo.queue()
    demo.launch(debug=True)
