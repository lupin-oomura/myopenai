import  openai
from openai import OpenAI

import  os
import datetime
import json
import re #正規表現チェック用
import uuid

import requests #画像downloadで使用

#ハンドラー用
from typing_extensions import override
from openai import AssistantEventHandler

class myopenai :
    #------------------------------------------------------------#
    #--- ストリーミング表示用の、イベントハンドラークラス -----------#
    #------------------------------------------------------------#
    class EventHandler(AssistantEventHandler):
        assistant_reply = ""
        reply_placeholder = None

        def __init__(self, myst=None):
            super().__init__()  # 親クラスの初期化メソッドを呼び出す
            if myst is not None :
                self.assistant_reply = ""
                self.reply_placeholder = myst.empty()

        @override
        def on_text_created(self, text) -> None:
            if self.reply_placeholder is None :
                print(f"\nassistant > ", end="", flush=True)
            else :
                pass
                # self.assistant_reply += text.value
                # self.reply_placeholder.markdown(self.assistant_reply)

        @override
        def on_text_delta(self, delta, snapshot):
            if self.reply_placeholder is None :
                print(delta.value, end="", flush=True)
            else :
                self.assistant_reply += delta.value
                self.reply_placeholder.markdown(self.assistant_reply)

        #--- メモ: OpenAIのAPI情報に乗ってたが、この関数を使わなくてもストリーミング表示できたので、一旦コメントアウト
        # def on_tool_call_created(self, tool_call):
        #     print(f"\nassistant > {tool_call.type}\n", flush=True)

        # def on_tool_call_delta(self, delta, snapshot):
        #     if delta.type == 'code_interpreter':
        #         if delta.code_interpreter.input:
        #             print(delta.code_interpreter.input, end="", flush=True)
        #         if delta.code_interpreter.outputs:
        #             print(f"\n\noutput >", flush=True)
        #             for output in delta.code_interpreter.outputs:
        #                 if output.type == "logs":
        #                     print(f"\n{output.logs}", flush=True)


    #----------------------------------------------#
    #--- 本体 -------------------------------------#
    #----------------------------------------------#
    client       = None
    assistant    = None
    thread       = None
    messages     = None
    mystreamlit  = None
    unique_id    = None #ユーザー固有のID（音声ファイルとかの名前になる）


    def __init__(self, myst=None, model:str="gpt-4o", systemmessage:str="") :
        self.unique_id = str(uuid.uuid4())
        self.client = OpenAI()
        self.mystreamlit = myst

        self.assistant = self.client.beta.assistants.create(
            # name="感謝と半生",
            instructions=systemmessage,
            tools=[{"type": "code_interpreter"}],
            model=model,
        )

    def set_prompt(self, txt:str):
        self.assistant = self.client.beta.assistants.update(
            assistant_id=self.assistant.id,
            instructions=txt,
        )

    def create_thread(self) :
        self.thread = self.client.beta.threads.create() 
        return self.thread


    def create_message(self, msg:str) :
        self.client.beta.threads.messages.create(
            thread_id = self.thread.id,
            content   = msg,
            role="user",
        )

    def run(self, f_stream:bool=True) -> str :
        if f_stream :
            with self.client.beta.threads.runs.stream(
                thread_id     = self.thread.id,
                assistant_id  = self.assistant.id,
                event_handler = self.EventHandler(self.mystreamlit),
            ) as stream:
                stream.until_done()
            print('\n')

        else :
            run = self.client.beta.threads.runs.create_and_poll(
                thread_id    = self.thread.id,
                assistant_id = self.assistant.id,
            )

            if run.status != 'completed': 
                print(run.status)

        self.messages = self.client.beta.threads.messages.list(
            thread_id = self.thread.id,
        )

        msg = self.get_lastmsg()
        return msg 

    def get_lastmsg(self) -> str :
        return f"{self.messages.data[0].content[-1].text.value}"

    def get_allmsg(self) -> list :
        msgs = []
        for message in self.messages.data[::-1]:
            msgs.append(f"{message.content[-1].text.value}")
        return msgs

    def image_generate(self, pmt:str, model:str='dall-e-3', size:str='1024x1024', n:int=1, filename:str=None) -> str :
        # size(dalle3): 1024x1024, 1024x1792 or 1792x1024 
        # size(dalle2): 256x256, 512x512, 1024x1024 e2とe3で指定できるサイズが違うので注意！
        # model: dall-e-3, dall-e-2

        response = self.client.images.generate(
            model  = model,
            prompt = pmt,
            size   = size,
            quality="standard",
            n      = n, #dalle2のみ指定できるみたい
        )
        image_url = response.data[0].url

        if filename is not None :
            self.download_image(image_url, filename)

        return image_url

    # 画像をダウンロードして保存する関数(OPENAIとは関係ないけど、よく使うのでここで定義)
    def download_image(self, url, filename):
        response = requests.get(url)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            # print(f"画像が {filename} として保存されました。")
        else:
            print("画像のダウンロードに失敗しました。")
            

    def transcribe_audio(self, audio_file, model:str="whisper-1"):
        return self.client.audio.transcriptions.create(
            model=model,
            file=audio_file
        )




    def mytexttospeech(self, text:str, voice:str="alloy", foldername:str='', filename:str=None, model:str='tts-1') -> str :
        """
        alloy : アナウンサー的な男性
        echo : 渋い声のアナウンサー的な男性
        fable : 高い声のアナウンサー的な男性
        onyx : かなり低い俳優的な男性
        nova : アナウンサー的な女性
        shimmer : 低めの声の女性
        """
        if filename is None :
            fn = f'tts_{self.unique_id}.mp3'
        else :
            fn = filename

        response = self.client.audio.speech.create(
            model=model,
            voice=f"{voice}",
            input=text,
        )

        if os.path.exists(os.path.join(foldername, fn)) :
            os.remove(os.path.join(foldername, fn)) #ファイル削除
        with open(os.path.join(foldername, fn), "wb") as file:
            file.write(response.content)

        return fn
    


    # #会話の読み込みを行う関数を定義
    # def load_conversation_for_azure(self, api_version:str, deployment_name:str, model:str=None, streaming:bool=True, temperature:float=0):
    #     if model is None :
    #         model = self.model

    #     llm = AzureChatOpenAI(
    #         temperature        = 0,
    #         openai_api_version = api_version,
    #         deployment_name    = deployment_name,
    #         model_name         = model
    #     )

    #     memory          = ConversationBufferMemory(return_messages=True)
    #     conversation    = ConversationChain(
    #         memory      = memory,
    #         prompt      = self.prompt,
    #         llm         = llm
    #     )
    #     # print(memory)

    #     return conversation


    def myjson(self, response:str)->dict :
        # JSON形式の文字列をPythonのリストに変換
        if '```json\n' in response :
            nakami = response.split('```json\n')[1]
            nakami = nakami.split('\n```')[0] if '\n```' in nakami else nakami
                
        elif '```' in response :
            nakami = response.split('```\n')[1]
            nakami = nakami.split('\n```')[0] if '\n```' in nakami else nakami
        else :
            nakami = response

        jsondata = json.loads(nakami)
        return jsondata

    # def getdata_from_vtt(self, vtt_file_path:str) -> list :

    #     def parse_vtt_line(line):
    #         # 正規表現パターンで発話者と発話内容を抽出
    #         pattern = r"<v ([^>]+)>([^<]+)</v>"
    #         match = re.search(pattern, line)
    #         if match:
    #             speaker = match.group(1).strip()
    #             message = match.group(2).strip()
    #             return speaker, message
    #         return None, None

    #     def parse_time_range(time_range):
    #         # 時間範囲から開始と終了の時刻文字列を抽出
    #         start_time_str, end_time_str = time_range.split(' --> ')
            
    #         # 時間フォーマットの指定
    #         time_format = "%H:%M:%S.%f"
            
    #         # 文字列からdatetimeオブジェクトへの変換
    #         base_date = datetime.datetime(1900, 1, 1)  # ダミーの日付
    #         start_time = datetime.datetime.strptime(start_time_str, time_format) - base_date
    #         end_time = datetime.datetime.strptime(end_time_str, time_format) - base_date
            
    #         return start_time, end_time



    #     # VTTデータを格納するためのリスト
    #     cues = []

    #     with open(vtt_file_path, 'r', encoding='utf-8') as file:
    #         lines = file.readlines()

    #         # WEBVTTヘッダーをスキップする
    #         lines = iter(lines[1:])  # ヘッダー以降の行に対してイテレータを作成
    #         while True:
    #             try:
    #                 line = next(lines).strip()
    #                 if line and not line.startswith("NOTE") and not line.startswith("STYLE"):
    #                     # キューのIDを抽出
    #                     if '-->' in line : #キューIDがないケースもある（いきなりタイムスタンプ）
    #                         cue_id = ''
    #                         timestamp = line.strip()
    #                     else :
    #                         cue_id = line
    #                         # タイムスタンプを抽出
    #                         timestamp = next(lines).strip()

    #                     start_time, end_time = parse_time_range(timestamp)

    #                     # テキストを抽出（複数行にわたることがあるため、空行が現れるまで読み込む）
    #                     text_lines = []
    #                     line = next(lines, '').strip()
    #                     while line:
    #                         text_lines.append(line)
    #                         line = next(lines, '').strip()  # ファイルの終わりに達してもエラーを出さないように修正
    #                     text = ' '.join(text_lines)

    #                     #textに発話者と発話内容が入っているので<v></v>、正規表現で切り分ける
    #                     speaker, message = parse_vtt_line(text)
    #                     speaker = re.sub(r'\[.*?\]', '', speaker).strip() #speakerに[]が入っている場合、それを除去

                        
    #                     # 抽出したデータを辞書としてリストに追加
    #                     cues.append({
    #                         'id': cue_id,
    #                         'timestamp': timestamp,
    #                         'time_start': start_time,
    #                         'time_end': end_time,
    #                         'text': text,
    #                         'speaker': speaker,
    #                         'message': message
    #                     })
    #             except StopIteration:
    #                 break  # ファイルの終わりに達したらループを抜ける

    #     return cues

    # def youyaku_minutes(self, logfile:str, minutesfile:str, promptfile:str, model:str, streaming:bool=False) : 
    #     dic_vtt = self.getdata_from_vtt(minutesfile)
    #     # 辞書型なので、会話ログテキストにする
    #     txt_vtt = "callid | speaker | message  \n"
    #     i = 0
    #     for d in dic_vtt :
    #         i += 1
    #         txt_vtt += f"{i} | {d['speaker']} | {d['message']}\n"

    #     with open(f"{minutesfile}.txt", "w", encoding='utf-8') as f:
    #         f.write(txt_vtt)

    #     with open(promptfile, "r", encoding='utf-8') as f:
    #         txt = f.read()
    #         txt = txt.replace('||文字起こしデータ||', txt_vtt)

    #     l_prompts = [part.strip() for part in txt.split('---')]

    #     l_res = self.predictchain(logfile, l_prompts, model, streaming)
    #     return l_res, txt_vtt

    # def predictchain(self, logfile:str, l_prompts:list, model:str, streaming:bool=False)->list : 
    #     with open(logfile, 'w', encoding='utf-8') as f :
    #         now = datetime.datetime.now()  # 現在の時刻を取得
    #         formatted_now = now.strftime("%Y-%m-%d %H:%M:%S")  # 時刻を文字列に整形
    #         msg = f'start:{formatted_now}\n'
    #         f.write(msg)

    #     self.set_prompt(l_prompts[0])
    #     conv  = self.load_conversation( model = model, streaming=streaming )

    #     i = 0
    #     l_res = []
    #     for pmt in l_prompts[1:] :
    #         i += 1
    #         print(f'---処理{i}---------')
    #         print(pmt)

    #         #出力結果を使ったループ処理
    #         pattern = r'\|\|出力結果(\d+)\|([^|]*)\|\|'
    #         match = re.search(pattern, pmt)
    #         if match :
    #             loopno = int( match.group(1) )
    #             useres = l_res[ loopno - 1 ]
    #             useres = self.myjson(useres)
    #             kw = match.group(2)
    #             if kw[-1] == '*' :
    #                 kw = kw[:-1]
    #                 l = useres[kw]
    #                 l_res2 = []
    #                 for v in l :
    #                     pmt_replace = re.sub(pattern, v, pmt)
    #                     if self.handler is None :
    #                         res = conv.predict(input=pmt_replace)
    #                     else :
    #                         res = conv.predict(input=pmt_replace, callbacks=[self.handler])
    #                     if '```json' in res :
    #                         res = self.myjson(res)
    #                         res = json.dumps(res, ensure_ascii=False, indent=4)
    #                     l_res2.append(res)
    #             res = ',\n'.join(l_res2)
    #             res = f'[\n{res}\n]'
    #             del l_res2
    #         else :
    #             if self.handler is None :
    #                 res = conv.predict(input=pmt)
    #             else :
    #                 res = conv.predict(input=pmt, callbacks=[self.handler])

    #         l_res.append(res)
    #         with open(f'result_{i}.txt', 'w', encoding='utf-8') as f :
    #             f.write(res)

    #         #上書き保存（最終結果坂）
    #         with open(f'data/result.txt', 'w', encoding='utf-8') as f :
    #             f.write("test")

    #     with open(logfile, 'a', encoding='utf-8') as f :
    #         f.write(f'process:{i}\n')

    #     with open(logfile, 'a', encoding='utf-8') as f :
    #         now = datetime.datetime.now()  # 現在の時刻を取得
    #         formatted_now = now.strftime("%Y-%m-%d %H:%M:%S")  # 時刻を文字列に整形
    #         msg = f'end:{formatted_now}\n'
    #         f.write(msg)

    #     return l_res


def tanjun() :
    mo = myopenai('gpt-3.5-turbo')

    mo.set_prompt('あなたは精神科医です。私の悩みを聞いて、適切にアドバイスをしてください。')
    conv = mo.load_conversation()
    ans = conv.predict(input='上司と反りが合わずに悩んでいる。')
    print(ans)
    ans = conv.predict(input='別のアドバイスありますか？')
    print(ans)
    print(conv.memory)


def embedding_ppt() :
    mo = myopenai('gpt-3.5-turbo')

    # ベクトル化の処理
    # file_path = r'C:\Users\大村真ShinOOMURA\Documents\大村\スコアカード虎の巻\スコアカード虎の巻.pptx'
    # mo.ppt_to_vector(file_path)

    # 流れ：質問と類似度の高いドキュメントをシステムメッセージに組み込んで、質問を投げる。なので追加質問は最初の質問に関係しないとワークしないので注意
    # 事前準備
    vecname = 'スコアカード虎の巻'
    Q       = 'ダミー化について教えてください。'
    prompt  = (
        '今からあなたに質問します。また、マニュアルからEmbedding処理を掛けてその質問と類似度の高い文章群をお渡します。\n'
        'そのEmbedding文章群を元に、以下のルールに従って回答してください。\n'
        '\n'
        'ルール: """\n'
        '* 以下の回答フォーマットのように回答する。\n'
        '* 質問に200文字以内で回答\n'
        '* 質問と類似度の高いページ番号を最大３つ回答。\n'
        '* 関連する文書が「Embedding文章群」になければ、「分かりません」と回答'
        '"""\n'
        '\n'
        '回答フォーマット: """\n'
        '関連ページ（類似度の高いページ）：●ページ、●ページ、●ページ\n'
        '回答: ●●●\n'
        '"""\n'
        '\n'
    )



    # ベクトルデータの読み込み
    df_vector = mo.load_vector(vecname)
    # プロンプトセット
    mo.set_prompt(prompt)

    # 類似文書の抽出
    txt_ruiji = mo.search_reviews(Q, df_vector, n=10)

    Q_plus = (
        f'{Q}\n'
        '\n'
        'Embedding文章群: """\n'
        '|ドキュメント名|ページ番号|文章|類似度|\n'
        f'{txt_ruiji}\n'
        '"""\n'
    )



    # チャット開始
    conv = mo.load_conversation()
    ans = conv.predict(input=Q_plus)
    print(ans)
    ans = conv.predict(input='関連ページは？')
    print(ans)
    ans = conv.predict(input='Coarse Classingについて教えて')
    print(ans)



def embedding_txt() :
    mo = myopenai('gpt-3.5-turbo')

    # ベクトル化の処理
    file_path = r'C:\temp\Apps\Python\st_toranomaki\Docker_to_Studio.txt'
    # mo.txt_to_vector(file_path)

    # 流れ：質問と類似度の高いドキュメントをシステムメッセージに組み込んで、質問を投げる。なので追加質問は最初の質問に関係しないとワークしないので注意
    # 事前準備
    vecname = 'Docker_to_Studio'
    Q       = 'Dockerfileのサンプルを知りたい'
    prompt  = (
        '今からあなたに質問します。また、マニュアルからEmbedding処理を掛けてその質問と類似度の高い文章群をお渡します。\n'
        'そのEmbedding文章群を元に、以下のルールに従って回答してください。\n'
        '\n'
        'ルール: """\n'
        '* 以下の回答フォーマットのように回答する。\n'
        '* 質問に200文字以内で回答\n'
        '* 質問と類似度の高い行番号を最大３つ回答。\n'
        '* 関連する文書が「Embedding文章群」になければ、「分かりません」と回答'
        '"""\n'
        '\n'
        '回答フォーマット: """\n'
        '関連する行番号（類似度の高い行番号）：●行、●行、●行\n'
        '回答: ●●●\n'
        '"""\n'
        '\n'
    )



    # ベクトルデータの読み込み
    df_vector = mo.load_vector(vecname)
    # プロンプトセット
    mo.set_prompt(prompt)

    # 類似文書の抽出
    txt_ruiji = mo.search_reviews(Q, df_vector, n=10)

    Q_plus = (
        f'{Q}\n'
        '\n'
        'Embedding文章群: """\n'
        '|行番号|文章|類似度|\n'
        f'{txt_ruiji}\n'
        '"""\n'
    )



    # チャット開始
    conv = mo.load_conversation()
    ans = conv.predict(input=Q_plus)
    print(ans)
    ans = conv.predict(input='関連ページは？')
    print(ans)
    ans = conv.predict(input='Coarse Classingについて教えて')
    print(ans)


def image_generate(mo) :
    image_url = mo.image_generate("a white cat", size="256x256", model='dall-e-2', filename="downloaded_image.png")
    print(image_url)

if __name__ == '__main__' :
    mo = myopenai()
    image_generate(mo)
    # mo.pdf_to_vector(r'C:\temp\Apps\Python\st_toranomaki\【御請求書】テスト.pdf')
    # tanjun()
    # embedding_ppt()
    # embedding_txt()

# StudioにDockerをあげる時のTips集