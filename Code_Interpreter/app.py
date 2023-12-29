import os
import time
import gradio as gr
from openai import OpenAI
from openai.types.beta.threads.runs import ToolCallsStepDetails

# GPT用設定
SYS_PROMPT_DEFAULT = "あなたは優秀なアシスタントです。質問をされた場合は、質問に答えるコードを作成して実行します。回答は日本語でお願いします。"
DUMMY = "********************"
file_format = {".txt", ".csv", ".pdf"}

# 各種出力フォルダ
IMG_FOLDER = "images"
ANT_FOLDER = "annotations"

# 各種メッセージ
PLACEHOLDER = "これは東京都の年別人口データです、折れ線グラフでデータの可視化をお願いします… など"
IMG_MSG = "(画像ファイルを追加しました。リセットボタンの上に表示されています。)"
ANT_MSG = "（下部の[出力ファイル]にファイルを追加しました。）"

# 各種設定値
MAX_TRIAL = int(os.environ["MAX_TRIAL"])  # メッセージ取得最大試行数
INTER_SEC = int(os.environ["INTER_SEC"])   # 試行間隔（秒）

# コード出力用
code_mode = {'ON': True, 'OFF': False}


# 各関数
def set_state(openai_key, sys_prompt, code_output, state):
    """ 設定タブの情報をセッションに保存する関数 """

    state["openai_key"] = openai_key
    state["system_prompt"] = sys_prompt
    state["code_mode"] = code_mode[code_output]

    return state


def init(state, text, file):
    """ 入力チェックを行う関数
        ※ここで例外を起こすと入力できなくなるので次の関数でエラーにする """

    err_msg = ""
    file_id = None

    if not text:

        # テキスト未入力
        err_msg = "テキストを入力して下さい。"

        return state, file_id, err_msg

    elif file:

        # 入力画像のファイル形式チェック
        root, ext = os.path.splitext(file)

        if ext not in file_format:

            # ファイル形式チェック
            err_msg = "指定した形式のファイルをアップしてください。（注意事項タブに記載）"

            return state, file_id, err_msg

    # 出力フォルダ作成
    os.makedirs(IMG_FOLDER, exist_ok=True)
    os.makedirs(ANT_FOLDER, exist_ok=True)

    if state["client"] is None:

        # クライアント新規作成
        client = OpenAI()

        # セッションにセット
        state["client"] = client

    else:

        # 既存のクライアントをセット
        client = state["client"]


    if state["thread_id"] == "":

        # スレッド作成
        thread = client.beta.threads.create()

        state["thread_id"] = thread.id


    if state["assistant_id"] == "":

        state["assistant_id"] = os.environ["ASSIST_ID"]   # アシスタントは固定


    if file:

        # ファイルのアップ
        file_response = client.files.create(
            purpose="assistants",
            file=open(file,"rb"),
        )

        if file_response.status != "processed":

            # 失敗時
            err_msg = "ファイルのアップロードに失敗しました"

        else:
            # ファイルのIDをセット
            file_id = file_response.id

    return state, file_id, err_msg


def raise_exception(err_msg):
    """ エラーの場合例外を起こす関数 """

    if err_msg != "":
        raise Exception("これは入力チェックでの例外です。")

    return


def add_history(history, text, file_id):
    """ Chat履歴"history"に追加を行う関数 """

    err_msg = ""

    if file_id is None or file_id == "":

        # テキストだけの場合そのまま追加
        history = history + [(text, None)]

    elif file_id is not None:

        # ファイルがあればファイルIDとテキストを追加
        history = history + [("file:" + file_id, DUMMY)]
        history = history + [(text, None)]

    # テキスト・ファイルを初期化し利用不可に
    update_text = gr.update(value="", placeholder = "",interactive=False)
    update_file = gr.update(value=None, interactive=False)

    return history, update_text, update_file, err_msg


def bot(state, history, file_id):

    err_msg = ""
    image_file = None
    ant_file = None

    # セッション情報取得
    system_prompt = state["system_prompt"]
    client = state["client"]
    assistant_id = state["assistant_id"]
    thread_id = state["thread_id"]
    last_msg_id = state["last_msg_id"]
    code_mode = state["code_mode"]

    if file_id is None or file_id == "":

        # ファイルがない場合
        message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=history[-1][0],
        )
    else:

        # ファイルがあるときはIDをセット
        message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=history[-1][0],
        file_ids=[file_id]
        )

    # RUNスタート
    run = client.beta.threads.runs.create(
      thread_id=thread_id,
      assistant_id=assistant_id,
      instructions=system_prompt
    )

    # "completed"となるまで繰り返す（指定秒おき）
    for i in range(0, MAX_TRIAL, 1):

      if i > 0:
        time.sleep(INTER_SEC)

      # メッセージ受け取り
      run = client.beta.threads.runs.retrieve(
        thread_id=thread_id,
        run_id=run.id
      )

      # 前回のメッセージより後を昇順で取り出す
      messages = client.beta.threads.messages.list(
        thread_id=thread_id,
        after=last_msg_id,
        order="asc"
      )

      msg_log = client.beta.threads.messages.list(
        thread_id=thread_id,
        # after=last_msg_id,
        order="asc"
      )

      # messageを取り出す
      for msg in messages:

          if msg.role == "assistant":

            for content in msg.content:

                res_text = ""
                file_id = ""
                ant_file = None

                cont_dict = content.model_dump()  # 辞書型に変換

                ct_image_file = cont_dict.get("image_file")

                if ct_image_file:

                    # imageファイルがあるならIDセット
                    res_file_id = ct_image_file.get("file_id")

                    # ファイルをダウンロード
                    image_file = file_download(client, res_file_id, IMG_FOLDER , ".png")

                    if image_file is None:

                        err_msg = "ファイルのダウンロードに失敗しました。"

                    else:

                        res_text = IMG_MSG

                        history = history + [[None, res_text]]

                    # 最終メッセージID更新
                    last_msg_id = msg.id

                else:

                    # 返答テキスト取得
                    res_text = cont_dict["text"].get("value")

                    # 注釈（参照ファイル）ががある場合取得
                    if len(cont_dict.get("text").get("annotations")) > 0:

                        ct_ant = cont_dict.get("text").get("annotations")

                        if ct_ant[0].get("file_path") is not None:

                            # 参照ファイルのID取得
                            ant_file_id = ct_ant[0].get("file_path").get("file_id")

                            if ct_ant[0].get("text") is not None:

                                # ファイル形式（拡張子）取得
                                ext = "." + ct_ant[0].get("text")[ct_ant[0].get("text").rfind('.') + 1:]

                            # ファイルダウンロード
                            ant_file = file_download(client, ant_file_id, ANT_FOLDER, ext)

                            if ant_file is None:

                                err_msg = "参照ファイルのダウンロードに失敗しました。"

                            else:

                              # 参照ファイルがある旨のメッセージを追加
                              res_text = res_text + "\n\n" + ANT_MSG

                    if res_text != "":

                        # Chat画面更新
                        if history[-1][1] is not None:

                            # 新しい行を追加
                            history = history + [[None, res_text]]
                        else:

                            history[-1][1] = res_text

                        # 最終メッセージID更新
                        last_msg_id = msg.id

            # Chatbotを返す（labelとhistoryを更新）
            yield gr.Chatbot(label=run.status ,value=history), image_file, ant_file, err_msg

      # メッセージIDを保存
      state["last_msg_id"] = last_msg_id

      # 完了なら終了
      if run.status == "completed":

          if not code_mode:

              yield gr.Chatbot(label=run.status ,value=history), image_file, ant_file, err_msg

              break
          else:

              # コードモードがONの場合
              run_steps = client.beta.threads.runs.steps.list(
              thread_id=thread_id, run_id=run.id
              )

              # コードを取得
              input_code = get_code(run_steps)

              if len(input_code) > 0:

                    for code in input_code:

                        code = "[input_code]\n\n" + code

                        # コードを追加
                        history = history + [[None, code]]

                        yield gr.Chatbot(label=run.status ,value=history), image_file, ant_file, err_msg

              break

      elif run.status == "failed":

          # エラーとして終了
          err_msg = "※メッセージ取得に失敗しました。"
          yield gr.Chatbot(label=run.status ,value=history), image_file, ant_file, err_msg
          break

      elif i == MAX_TRIAL:

          # エラーとして終了
          err_msg = "※メッセージ取得の際にタイムアウトしました。"
          yield gr.Chatbot(label=run.status ,value=history), image_file, ant_file, err_msg
          break

      else:
          if i > 3:

              # 作業中とわかるようにする
              yield gr.Chatbot(label=run.status + " (Request:" + str(i) + ")" ,value=history), image_file, ant_file, err_msg


def get_code(run_steps):
    """ 生成過程のコードを全てを返す """

    input_code = []

    for data in run_steps.data:

        if isinstance(data.step_details, ToolCallsStepDetails):

            # コードが存在するときだけ取得
            for tool_call in data.step_details.tool_calls:

                input_code.append(tool_call.code_interpreter.input)

    return input_code


def file_download(client, file_id, folder, ext):
    """ OpenAIからファイルをダウンロードしてパスを返す """

    api_response = client.files.with_raw_response.retrieve_content(file_id)

    if api_response.status_code == 200:

        content = api_response.content

        file_path = folder + "/" + file_id + ext

        with open(file_path, 'wb') as f:
            f.write(content)

        return file_path

    else:
        return None


def finally_proc():
    """ 最終処理用関数 """

    # テキスト・ファイルを使えるように
    interactive = gr.update(interactive = True)

    # ファイルIDはリセット
    new_file_id = gr.Textbox(value="")

    return interactive, interactive, new_file_id


def clear_click(state):
    """ クリアボタンクリック時 """

    # セッションの一部をリセット（）
    state["thread_id"] = ""
    state["last_msg_id"] = ""

    return state

# 画面構成
with gr.Blocks() as demo:

    title = "<h2>GPT Code Interpreter対応チャット</h2>"
    message = '<h3>※動いているかわかりづらいですが、左上の"in_progress(Request:XX)"が止まっていなければ回答の生成中となります。</h3><br>'


    gr.Markdown(title + message)

    # セッションの宣言
    state = gr.State({
        "system_prompt": SYS_PROMPT_DEFAULT,
        "openai_key" : "",
        "code_mode" : False,
        "client" : None,
        "assistant_id" : "",
        "thread_id" : "",
        "last_msg_id" : ""
    })

    with gr.Tab("Chat画面") as chat:

      # 各コンポーネント定義
      chatbot = gr.Chatbot(label="チャット画面")
      text_msg = gr.Textbox(label="テキスト", placeholder = PLACEHOLDER)
      with gr.Row():
        up_file = gr.File(label="ファイルアップロード", type="filepath",interactive = True)
        result_image = gr.Image(label="出力画像", type="filepath", interactive = False)
    #   gr.Examples(label="サンプルデータ", examples=examples, inputs=[up_file])
      with gr.Row():
        btn = gr.Button(value="送信")
        btn_clear = gr.ClearButton(value="リセット", components=[chatbot, text_msg, up_file])
      sys_msg = gr.Textbox(label="システムメッセージ", interactive = False)
      result_file = gr.File(label="出力ファイル", type="filepath",interactive = False)

      # ファイルID保存用
      file_id = gr.Textbox(visible=False)

      # 送信ボタンクリック時の処理
      bc = btn.click(init, [state, text_msg, up_file], [state, file_id, sys_msg], queue=False).success(
          raise_exception, sys_msg, None).success(
          add_history, [chatbot, text_msg, file_id], [chatbot, text_msg, up_file, sys_msg], queue=False).success(
          bot, [state, chatbot, file_id],[chatbot, result_image, result_file, sys_msg]).then(
          finally_proc, None, [text_msg, up_file, file_id], queue=False
      )

      # クリア時でもセッションの設定（OpenAIKeyなどは残す）
      btn_clear.click(clear_click, state, state)

    with gr.Tab("設定") as set:
      openai_key = gr.Textbox(label="OpenAI API Key", visible=False)   # テスト中は表示せず
      # language = gr.Dropdown(choices=["Japanese", "English"], value = "Japanese", label="Language", interactive = True)
      system_prompt = gr.Textbox(value = SYS_PROMPT_DEFAULT,lines = 5, label="Custom instructions", interactive = True)
      code_output = gr.Dropdown(label="コード出力", choices=["OFF", "ON"], value = "OFF", interactive = True)

      # 設定タブからChatタブに戻った時の処理
      chat.select(set_state, [openai_key, system_prompt, code_output, state], state)

    with gr.Tab("注意事項") as notes:
            caution = "現在Assistant APIはβ版でのリリースとなっています。<br>"
            caution += "文字化けする場合フォントファイルをZIPで渡し「解凍してフォントを取得して下さい。」と指示してください。<br>"
            caution += "※アシスタントに渡しておくと楽です<br>"
            gr.Markdown("<h3>" + caution + "</h3>")


if __name__ == "__main__":

    demo.queue()
    demo.launch(debug=True)

