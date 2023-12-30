import gradio as gr
import time
import datetime
from zoneinfo import ZoneInfo
import os
from openai import (
    OpenAI, AuthenticationError, NotFoundError, BadRequestError
)

# 各種設定値
MAX_TRIAL = int(os.environ["MAX_TRIAL"])  # メッセージ取得最大試行数
INTER_SEC = int(os.environ["INTER_SEC"])   # 試行間隔（秒）

# sys_prompt_default = "あなたは優秀なアシスタントです。日本語で質問に回答してください。"
# lang_code = {'Japanese': "ja", 'English': "en"}
auto_play_bl = {'ON': True, 'OFF': False}
voice_list = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

def set_state(state, openai_key, voice, auto_play, speed):

    state["openai_key"] = openai_key
    state["voice"] = voice
    state["auto_play"] = auto_play_bl[auto_play]
    state["speed"] = speed

    return state


def add_history(history, text_msg):
    """ Chat履歴"history"に追加を行う関数 """

    # ユーザテキストをチャットに追加
    history = history + [(text_msg, None)]

    # テキスト・オーディオ初期化
    return history, gr.Textbox(value="", interactive=False), gr.components.Audio(value=None, interactive=False)


def init(state, mode, text_msg, voice_msg):
    """ 初期処理（入力チェック・テキスト変換） """

    err_msg = ""
    text = ""


    if text_msg == "" and voice_msg is None:

        # 何も入力がないならエラーメッセージを返す
        err_msg = "テキストまたは音声を入力してください。"

        return state, "", err_msg

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

        # モードが翻訳以外はアシスタント・スレッドセット
        if mode != 2:

            if state["thread_id"] == "":

                # スレッド作成・セット
                thread = client.beta.threads.create()

                state["thread_id"] = thread.id

            if state["assistant_id"] == "":

                # アシスタント作成
                # assistant = client.beta.assistants.create(
                #   name="codeinter_test",
                #   instructions=state["system_prompt"],
                #   # model="gpt-4-1106-preview",
                #   model="gpt-3.5-turbo-1106",
                #   tools=[{"type": "code_interpreter"}]
                # )
                # state["assistant_id"] = assistant.id

                if mode == 0:

                    # 日本語アシスタントをセット
                    state["assistant_id"] = os.environ["ASSIST_JA"]

                elif mode == 1:

                    # 英語教師アシスタントをセット
                    state["assistant_id"] = os.environ["ASSIST_EN"]

        # ユーザIDでフォルダ作成
        os.makedirs(state["user_id"], exist_ok=True)

        if voice_msg is None:

            # 音声がないならテキストを返す
            text = text_msg

        else:

            # 音声があるならwhisperでテキストに変換
            text = exec_transcript(client, voice_msg)
            pass

    except NotFoundError as e:
        err_msg = "アシスタントIDが間違っています。新しく作成する場合はアシスタントIDを空欄にして下さい。"
        print(e)
    except AuthenticationError as e:
        err_msg = "認証エラーとなりました。OpenAPIKeyが正しいか、支払い方法などが設定されているか確認して下さい。"
        print(e)
    except Exception as e:
        err_msg = "その他のエラーが発生しました。"
        print(e)
    finally:
        return state, text, err_msg


def raise_exception(err_msg):
    """ エラーの場合例外を起こす関数 """

    if err_msg != "":
        raise Exception()

    return


def exec_transcript(client, voice_msg):
    """ whisperで文字に起こす関数 """

    audio_file= open(voice_msg, "rb")

    transcript = client.audio.transcriptions.create(
      model="whisper-1",
      file=audio_file,
      language = "ja",
      response_format="text"
    )

    return transcript


def exec_translation(client, text):
    """ GPTで英語に翻訳する関数 """

    response = client.chat.completions.create(
      model="gpt-3.5-turbo-1106",
      messages=[
        {"role": "system", "content": "You are a translator. Please translate the Japanese you received into English."},
        {"role": "user", "content": text},
      ]
    )

    return response.choices[0].message.content


def exec_text_to_speech(client, voice , speed, folder, text):
    """ テキストを音声にする """

    response = client.audio.speech.create(
        model= "tts-1",   # "tts-1-hd",
        voice=voice,
        input=text,
        speed=speed
    )

    # ファイル名は現在時刻
    dt = datetime.datetime.now(ZoneInfo("Asia/Tokyo"))
    file_name = dt.strftime("%Y%m%d%H%M%S") + ".mp3"
    file_path = folder + "/" + file_name

    # 音声ファイルに出力
    response.stream_to_file(file_path)

    return file_path


def bot(state, mode, history):
    """ Chat返答処理 """

    err_msg = ""
    file_path = None

    # セッション情報取得
    client = state["client"]
    asist_id = state["assistant_id"]
    thread_id = state["thread_id"]
    last_msg_id = state["last_msg_id"]
    user_id = state["user_id"]
    voice = state["voice"]
    speed = state["speed"]

    # 最新のユーザからのメッセージ
    user_msg = history[-1][0]

    if mode in (0, 1):    # 日本語会話モードの場合

        # メッセージ作成
        message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_msg
        )

        # RUNスタート
        run = client.beta.threads.runs.create(
          thread_id=thread_id,
          assistant_id=asist_id
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

            # messageを取り出す
            for msg in messages:

                if msg.role == "assistant":

                    assist_msg = msg.content[0].text.value

                    if assist_msg != "":

                        history[-1][1] = assist_msg

                        # 音声を作成
                        file_path = exec_text_to_speech(client, voice, speed, user_id, assist_msg)

                        if file_path is None:

                            err_msg = "音声作成でエラーが発生しました。"
                            history = history + [(None, err_msg)]

                        else:

                            history = history + [(None, (file_path,))]

                        yield gr.Chatbot(label=run.status ,value=history), err_msg

                        # 最終メッセージID更新
                        last_msg_id = msg.id

            # セッション更新
            state["last_msg_id"] = last_msg_id

            # 完了なら終了
            if run.status == "completed":

                yield gr.Chatbot(label=run.status ,value=history), err_msg
                break

            elif run.status == "failed":

                # エラーとして終了
                err_msg = "※メッセージ取得に失敗しました。"
                yield gr.Chatbot(label=run.status ,value=history), err_msg
                break

            elif i == MAX_TRIAL:

                # エラーとして終了
                err_msg = "※メッセージ取得の際にタイムアウトしました。"
                yield gr.Chatbot(label=run.status ,value=history), err_msg
                break

    elif mode == 2:    # 英訳モードの場合

        # GPTで英文にする
        bot_message = exec_translation(client, user_msg)

        file_path = exec_text_to_speech(client, voice, speed, user_id, bot_message)

        # bot_message = random.choice(["How are you?", "I love you", "I'm very hungry"])
        # bot_message = "まず、新宿駅南口に出ます。"
        # voice_path = "nova.mp3"

        history[-1][1] = bot_message
        # history[-1][1] = [None, (voice_path,)]
        history = history + [(None, (file_path,))]
        # history[-1][1] = (voice_path,)

        yield history, err_msg


def finally_proc(state, history, err_msg):
    """ 最終処理 """

    # テキスト・オーディオを使えるように
    interactive = gr.update(interactive = True)

    if err_msg == "":

        # 出力オーディオをセット
        audio = gr.update(value=history[-1][1][0], autoplay=state["auto_play"])

    else:

        audio = None

    return interactive, interactive, audio


def reset_chat(state):

    state["assistant_id"] = ""
    state["thread_id"] = ""
    state["last_msg_id"] = ""

    # Chatも初期化
    return state, None

with gr.Blocks() as demo:

    title = "<h2>GPT音声対応チャット</h2>"
    message = "<h3>・WhisperとText to speechによりチャットを行います。<br>"
    message += "・テキストまたは音声を入力して下さい。モードの違いは「利用上の注意」タブをご覧ください。<br>"
    message += "・動画での紹介はこちら→https://www.youtube.com/watch?v=wMoAORg0Y5Q<br>"
    message += "※自動再生の音声は送信ボタンの下の”出力音声”から自動再生で流れています。（設定でOFFにできます）<br>"
    # message += "・テスト中でAPIKEY無しで動きます。フィードバックもお待ちしております。<br>"
    message += "</h3>"

    gr.Markdown(title + message)

    # セッションの宣言
    state = gr.State({
        # "system_prompt": SYS_PROMPT_DEFAULT,
        "openai_key" : "",
        "client" : None,
        "assistant_id" : "",
        "thread_id" : "",
        "last_msg_id" : "",
        "user_id" : "",
        "auto_play" : True,
        "speed" : 0.8,
        "voice" : "nova"
    })

    with gr.Tab("GPT-4V 音声入力対応チャット") as maintab:

      # モード選択
      mode = gr.Radio(["通常（日本語）", "英会話", "英訳"], label="Mode", value="通常（日本語）", interactive=True, type="index")

      # 各コンポーネント定義
      chatbot = gr.Chatbot(label="チャット画面")
      text_msg = gr.Textbox(label="テキスト")
      voice_msg=gr.components.Audio(label="音声入力", sources="microphone", type="filepath")
      with gr.Row():
          btn = gr.Button("送信")
          clear = gr.ClearButton([chatbot, text_msg, voice_msg])

      sys_msg = gr.Text(label="システムメッセージ", interactive = False)
      out_voice=gr.Audio(label="出力音声", type="filepath", interactive = False, autoplay = True)


      # メッセージ送信時の処理
      btn.click(init, [state, mode, text_msg, voice_msg],[state, text_msg, sys_msg], queue=False).then(
          raise_exception, sys_msg, None).success(
          add_history, [chatbot, text_msg], [chatbot, text_msg, voice_msg], queue=False).then(
          bot, [state, mode, chatbot], [chatbot, sys_msg]).then(
          finally_proc, [state, chatbot, sys_msg], [text_msg, voice_msg, out_voice], queue=False)

      # 録音終了時の処理（反応が悪いので保留）
      # voice_msg.stop_recording(init, [state, mode, text_msg, voice_msg],[state, text_msg, sys_msg], queue=False).then(
      #     raise_exception, sys_msg, None).success(
      #     add_history, [chatbot, text_msg], [chatbot, text_msg, voice_msg], queue=False).then(
      #     bot, [state, mode, chatbot], [chatbot, sys_msg]).then(
      #     finally_proc, [state, chatbot, sys_msg], [text_msg, voice_msg, out_voice], queue=False)

    with gr.Tab("設定"):
        openai_key = gr.Textbox(label="OpenAI API Key" ,visible=False)
        voice = gr.Dropdown(choices=voice_list, value = "nova", label="Voice", interactive = True)
        auto_play = gr.Dropdown(choices=["ON", "OFF"], value = "ON", label="Auto Play", interactive = True)
        speed = gr.Slider(0, 1, value=0.8, label="Speed", info="1に近づけるほど読むスピードが速くなります。", interactive = True)
        # sys_prompt = gr.Textbox(value = sys_prompt_default,lines = 5, label="Custom instructions", interactive = True)

    # モード変更時
    mode.change(reset_chat, [state], [state, chatbot])

    # 設定変更時
    maintab.select(set_state, [state, openai_key, voice, auto_play, speed], state)

    with gr.Tab("利用上の注意"):
          caution = "・通常モードは日本人アシスタントとしてGPTが日本語で回答します。<br>"
          caution += "・英会話モードは英語の教師としてGPTが回答します。<br>"
          caution += "（英語で返答するように設定していますが、まれに日本語で回答するかもしれません。）<br>"
          caution += "・英訳モードはテキスト・音声ともに入力した日本語をそのまま英語に翻訳します。<br>"
          caution += "（GPTでの英訳となり、余計な文章などが含まれる可能性があります、）<br>"
          caution += "・モードを変更すると会話はリセットされます。<br>"
          caution += "・設定タブで声の種類（デフォルトはnova）、回答を自動再生にするか決めることができます。<br>"
          gr.Markdown("<h4>" + caution + "</h4>")

    with gr.Tab("声サンプル") as voice_chk:

        gr.Markdown("<h3>Text to speechの声のサンプルです。（速度は0.8です）</h3>")

        with gr.Row():
            btn_alloy = gr.Button(value="alloy")
            btn_echo = gr.Button(value="echo")
            btn_fable = gr.Button(value="fable")

        with gr.Row():
            btn_onyx = gr.Button(value="onyx")
            btn_nova = gr.Button(value="nova")
            btn_shimmer = gr.Button(value="shimmer")

        sample_voice=gr.Audio(type="filepath", interactive = False, autoplay = True)

        btn_alloy.click(lambda:"voice_sample/alloy.mp3", None, sample_voice)
        btn_echo.click(lambda:"voice_sample/echo.mp3", None, sample_voice)
        btn_fable.click(lambda:"voice_sample/fable.mp3", None, sample_voice)
        btn_onyx.click(lambda:"voice_sample/onyx.mp3", None, sample_voice)
        btn_nova.click(lambda:"voice_sample/nova.mp3", None, sample_voice)
        btn_shimmer.click(lambda:"voice_sample/shimmer.mp3", None, sample_voice)


if __name__ == '__main__':

    demo.queue()
    demo.launch(debug=True)