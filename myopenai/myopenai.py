import  openai
from openai import OpenAI

import  os
import datetime
import json
import re #正規表現チェック用
import uuid
from collections import deque
import requests #画像downloadで使用
import threading
import time

#ハンドラー用
from typing_extensions import override
from openai import AssistantEventHandler

import queue


class myopenai :
    #------------------------------------------------------------#
    #--- ストリーミング表示用の、イベントハンドラークラス -----------#
    #------------------------------------------------------------#
    class EventHandler(AssistantEventHandler):
        assistant_reply     = ""
        reply_placeholder   = None
        token_queue         = None  #GPTの回答がどしどし入る箱
        f_print             = True  #コンソールにテケテケ出力する場合、True

        def __init__(self, myst=None):
            super().__init__()  # 親クラスの初期化メソッドを呼び出す
            self.token_queue = queue.Queue()

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
            self.token_queue.put(delta.value)

            if self.reply_placeholder is None :
                if self.f_print :
                    print(delta.value, end="", flush=True)
            else :
                self.assistant_reply += delta.value
                self.reply_placeholder.markdown(self.assistant_reply)

        def set_printflag(self, f_print) :
            self.f_print = f_print 

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
    unique_id    = None     #ユーザー固有のID（音声ファイルとかの名前になる）
    gpts         = None     #mygptsクラスのインスタンス
    f_running    = False    #Run処理が回っている場合Trueになる
    handler      = None     #Runが回っている間、EventHandlerが入る
    msgs         = []    #self.messagesから重要な要素だけ抜き出したローカルメッセージーズ

    def __init__(self, myst=None, model:str="gpt-4o", systemmessage:str="") :
        self.unique_id = str(uuid.uuid4())
        self.client = OpenAI()
        self.f_running = False
        self.mystreamlit = myst
        self.msgs        = []

        self.assistant = self.client.beta.assistants.create(
            # name="感謝と半生",
            instructions=systemmessage,
            tools=[{"type": "code_interpreter"}],
            model=model,
        )

        print(f"assistant id = {self.assistant.id}")

        self.gpts = self.mygpts(self)

    def set_systemprompt(self, txt:str):
        self.assistant = self.client.beta.assistants.update(
            assistant_id=self.assistant.id,
            instructions=txt,
        )

    def create_thread(self) :
        self.thread = self.client.beta.threads.create() 
        return self.thread

    def get_threadid(self) :
        return self.thread.id

    def set_thread(self, threadid) :
        self.thread = self.client.beta.threads.retrieve(threadid)

    def create_message(self, msg:str, threadid=None) :
        tid = self.thread.id if threadid is None else threadid

        self.client.beta.threads.messages.create(
            thread_id = tid,
            content   = msg,
            role="user",
        )

    #--- テケテケ表示に欠かせない関数 -----------------#
    def get_queue(self)->deque :
        token = ""
        while self.handler.token_queue.qsize() > 0 :
            token += self.handler.token_queue.get()
        return token
    
    # def set_queue(self, txt:str) :
    #     self.token_queue.append(txt)

    # def reset_queue(self) :
    #     self.token_queue.clear()
    
    def is_running(self) :
        return self.f_running
    
    def __get_and_save_file(self, file_id, file_name) :
        retrieve_file = self.client.files.with_raw_response.content(file_id)
        content: bytes = retrieve_file.content
        with open(file_name, 'wb') as f:
            f.write(content)

    def run(self, thread_id=None, f_stream:bool=True, f_print:bool=True) -> str :
        self.f_running = True
        if thread_id is None :
            thread_id = self.thread.id

        self.handler = self.EventHandler(self.mystreamlit)
        print(f"print flag is [{f_print}]")
        self.handler.set_printflag(f_print)

        errmsg = None
        if f_stream :
            with self.client.beta.threads.runs.stream(
                thread_id     = thread_id,
                assistant_id  = self.assistant.id,
                event_handler = self.handler,
            ) as stream:
                stream.until_done()
            print('\n')
            #最後のキュー取得とかしなきゃいけないので、まだHandlerは閉じない

            #エラーチェック
            runs = self.client.beta.threads.runs.list(
                thread_id = thread_id,
            )
            errmsg = runs.data[0].last_error
            if errmsg is not None :
                errmsg = errmsg.message

        else :
            run = self.client.beta.threads.runs.create_and_poll(
                thread_id    = thread_id,
                assistant_id = self.assistant.id,
            )

            if run.status != 'completed': 
                errmsg = run.last_error.message

        if errmsg is not None :
            print(f"error !!! : {errmsg}")
            return None

        self.messages = self.client.beta.threads.messages.list(
            thread_id = thread_id,
        )


        response = self.get_lastmsg()
        print(f"response = {response}")

        # msgsに取り込み
        len_msgs_prev = len(self.msgs) 
        for index, msg in enumerate(self.messages.data) :
            if index >= len(self.messages.data) - len_msgs_prev :
                break
            itm = {}
            for cont in msg.content :
                if type(cont) is openai.types.beta.threads.text_content_block.TextContentBlock :
                    print("Text")
                    itm["text"] = cont.text.value

                elif type(cont) is openai.types.beta.threads.image_file_content_block.ImageFileContentBlock :
                    file_id = cont.image_file.file_id
                    fn = f"{file_id}.png"
                    self.__get_and_save_file(file_id, fn)
                    itm["image"] = fn

            # #一度attachmentsに画像が入ってたことがあったけど、1度しか出なかったのでとりあえずスルー。原則attachmentはユーザーがブツを投げるためのもの
            # for at in msg.attachments :
            #     print(at.file_id)
            #     file_id = at.file_id
            #     fn = f"{file_id}.png"
            #     self.__get_and_save_file(file_id, fn)
            #     itm["image"] = fn

            self.msgs.insert(index, itm)

        self.f_running = False
        return response 
    
    #テケテケ表示させる場合のサンプル（threadingで実行する必要あり）
    # mo = myopenai.myopenai()
    # mo.set_prompt("")
    # mo.create_thread()
    # mo.create_message("大谷翔平の誕生日は？")

    # thread = threading.Thread(target=mo.run, kwargs={'f_stream':True, 'f_print':False})
    # thread.start()
    # time.sleep(0.1) #これがないと、is_runningが立つ前に処理が走ってすぐに終わってしまう。
    # while mo.is_running() :
    #     time.sleep(0.1)
    #     token = mo.get_queue()
    #     if token :
    #         print(f"token: [{token}]")
    # #最後の残りかすトークン
    # token = mo.get_queue()
    # if token :
    #     print(f"token: [{token}]")
    
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
            

    def transcribe_audio(self, audio_file, model:str="whisper-1", lang:str='ja'):
        return self.client.audio.transcriptions.create(
            model    = model,
            language = lang,
            file     = audio_file,
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


    def myjson(self, response:str, f_print:bool=False)->dict :
        if not response :
            return None
        
        # JSON形式の文字列をPythonのリストに変換
        if '```json' in response :
            pattern = r"```json(.*?)```"                
        elif '```' in response :
            pattern = r"```(.*?)```"                
        else :
            return None

        matches = re.findall(pattern, response, re.DOTALL)
        nakami = matches[-1].strip()
        nakami = re.sub(r',\s*([\]\}])', r'\1', nakami) # 余分なカンマを取り除く
        try :
            jsondata = json.loads(nakami)
        except json.decoder.JSONDecodeError:
            jsondata = None
            if f_print :
                print("---NO JSON DATA ------------------")
                print(nakami)
                print("----------------------------------")

        return jsondata




    #-------------------------------------------------#
    #--- 議事録要約用のクラス --------------------------#
    #-------------------------------------------------#
    class giji_rocker:
        mo        = None
        l_minutes = [] #改行区切りで議事録文字起こしデータが入る
        l_youyaku = [] #要約結果データ
        l_topic_segments = [] #大量の文字起こしデータをどこで切るかの情報が入っている({開始行id,終了行id,トピックタイトル})

        def __init__(self, mo):
            self.mo = mo        
            self.l_minutes = [] 
            self.l_youyaku = [] 
            self.l_topic_segments = [] 

        def set_mojiokoshi(self, txt, matomegyou:int=1) :
            #matomegyou: 2行で1つのデータ（時間と発言とか）の場合、2にする。
            l_lines = txt.split("\n")
            self.l_minutes = ['|'.join(l_lines[i:i+matomegyou]) for i in range(0, len(l_lines), matomegyou)]
            #idを付与する。0スタートの連番
            self.l_minutes = [f"{i}|{x}" for i, x in enumerate(self.l_minutes)]
            #デフォルト値をセット（全体を１つに）
            self.l_topic_segments = [ { "開始行id":0, "終了行id":len(self.l_minutes), "トピックタイトル":"" } ]

        def get_minutes(self) :
            return self.l_minutes
        
        #--- トピック分割 ----------------------#
        def split_mojiokoshi(self, splitsize:int=18000) :
            # splitsizeが30000だと、出力込みで制限に引っ掛かることが多いので、余裕をもって18000で分割。（デフォルトは）
            self.l_topic_segments = self.__get_topics_from_minutes(splitsize=splitsize)

        def get_topic_segments(self) :
            return self.l_topic_segments
        def save_topic_segments(self, fn:str) :
            with open(fn, "w", encoding='utf-8') as f:
                json.dump(self.l_topic_segments, f, ensure_ascii=False, indent=4)
        def load_topic_segments(self, fn:str) :
            with open(fn, "r", encoding='utf-8') as f:
                self.l_topic_segments = json.load(f)
                
        def youyaku_minutes(self) :
            self.l_youyaku = []
            for i, l in enumerate(self.l_topic_segments) :
                id_from = l["開始行id"]
                id_to   = l["終了行id"]
                txt_minutes = '\n'.join(self.l_minutes[id_from:id_to+1])
                txt_minutes = f"id|talk\n{txt_minutes}"

                kobetsu_msg = f"[processing: {i}/{len(self.l_topic_segments)}]"
                res = self.__youyaku_minutes(txt_minutes, kobetsu_msg)
                res['開始行id'] = id_from
                res['終了行id'] = id_to
                self.l_youyaku.append(res)
            return self.l_youyaku

        def get_youyaku(self) :
            return self.l_youyaku
        def save_youyaku(self, fn:str) :
            with open(fn, "w", encoding='utf-8') as f:
                json.dump(self.l_youyaku, f, ensure_ascii=False, indent=4)
        def load_youyaku(self, fn:str) :
            with open(fn, "r", encoding='utf-8') as f:
                self.l_youyaku = json.load(f)
            

        def __get_topics_from_minutes(self, splitsize:int) :
            """
            議事録からトピックをまとめ、そのトピックの開始行と終了行を取得する。
            ループでチェックするので、結構時間がかかる。
            議事録をsplitsize文字で分割してチェックする。30000文字で10トピックくらい。
            議事録は、改行で分割されたリスト型。
            """

            # #↓一番きめ細かいが、ループがかなり多くて出力がかさみ、Token上限に引っ掛かるので、いったんパス
            # prompt_group1 = '''あなたに会議の文字起こしデータを渡します。
            # 非常に長い議論であったため、議論の内容ごとにトピック分割したいと思います。
            # 次のステップに従って文字起こしデータを複数ブロックに分割してください。

            # #Step1: 会話のトピックごとにブロック分割する
            # 各行の内容を把握し、同一トピックの会話がされている行はまとめてください。この作業を経て、複数のブロック（１つのブロックでは同一トピックで会話されている）を作ってください。
            # 同じトピックの会話が複数行にまたがっている場合は、そこで切らないように注意してください。
            # また、最後のブロックが他のブロックに比べて大幅に行数が多くなる傾向にあります。それぞれのブロックの文字数に偏りが出ないように注意してください。
            # 出力フォーマット: "開始行id":x, "終了行id":y, "トピックタイトル":""
            # ※「Step1」と出力し、その後出力フォーマットの内容だけを出力してください。出力フォーマットの内容以外は一切不要です。

            # #Step2: ブロックの統合
            # ブロックの数が10個を超えるようなら、各ブロックごとの内容を理解して内容の近しいブロックを統合してください。
            # 注意点として、最後のブロックが他のブロックに比べて大幅に行数が多くなる傾向にあります。それぞれのブロックの文字数に偏りが出ないように注意してください。
            # 出力フォーマット: "開始行id":x, "終了行id":y, "トピックタイトル":""
            # ※「Step2」と出力し、その後出力フォーマットの内容だけを出力してください。出力フォーマットの内容以外は一切不要です。

            # #Step3: 結果の確認
            # Step2の結果、ブロックの数が10個を超えるようなら、「Step3の結果：10個を超えているのでStep2に戻ります」と出力し、Step2に戻る。
            # ブロック数が10個以内になったら、「Step3の結果：OK」と言って、以下の出力フォーマットで結果を出力してください。
            # 出力フォーマット: json{{ [ {{ "開始行id":x, "終了行id":y, "トピックタイトル":"" }} ] }}

            # 文字起こしデータ: """
            # {txt_minutes}
            # """
            # '''

            #↓簡易版。ループは2回で済む
            prompt_group1 = '''あなたに会議の文字起こしデータを渡します。
非常に長い議論であったため、議論の内容ごとにトピック分割したいと思います。
次のステップに従って文字起こしデータを複数ブロックに分割してください。

#Step1: 会話のトピックごとにブロック分割する
各行の内容を把握し、同一トピックの会話がされている行はまとめてください。この作業を経て、複数のブロック（１つのブロックでは同一トピックで会話されている）を作ってください。
同じトピックの会話が複数行にまたがっている場合は、そこで切らないように注意してください。
また、最後のブロックが他のブロックに比べて大幅に行数が多くなる傾向にあります。それぞれのブロックの文字数に偏りが出ないように注意してください。
出力フォーマット: "開始行id":x, "終了行id":y, "トピックタイトル":""
※「Step1」と出力し、その後出力フォーマットの内容だけを出力してください。出力フォーマットの内容以外は一切不要です。

#Step2: ブロックの統合
ブロックの数が{n_group}個を超えるようなら、各ブロックごとの内容を理解して内容の近しいブロックを統合してください。
そして、ブロック数が{n_group}個になるまで統合処理を続けてください。
注意点として、最後のブロックが他のブロックに比べて大幅に行数が多くなる傾向にあります。それぞれのブロックの文字数に偏りが出ないように注意してください。

ブロック数が{n_group}個になったら、「Step2」と出力し、その後以下の出力をしてください。
出力フォーマットの内容以外は一切不要です。

出力フォーマット: ```json [ {{ "開始行id":x, "終了行id":y, "トピックタイトル":"" }}, ] ```

文字起こしデータ: """
{txt_minutes}
"""
'''

            #30000万文字で分割
            l_minutes_split = self.__split_list_by_length(self.l_minutes, splitsize)

            #30000文字ごとに、どこで区切るかをGPTに見てもらう
            l_topic_segments_all = []
            l_lastgroup = [] #切れ目の調整グループ
            for n_loop, l in enumerate(l_minutes_split) :
                l_adjust =l_lastgroup + l
                txt_minutes = '\n'.join(l_adjust)
                txt_minutes = f"id|talk\n{txt_minutes}"
                len_minutes = len(txt_minutes)
                n_group = int( len_minutes / 30000 * 10 + 0.5) #簡易的な四捨五入

                #GPT照会(スレッドは毎回新しく。そうしないと文字制限くらう)
                pmt1 = prompt_group1.format(n_group=n_group, txt_minutes=txt_minutes)
                self.mo.set_systemprompt("")
                self.mo.create_thread()
                self.mo.create_message(pmt1)
                response = None
                while response is None :
                    response = self.mo.run()
                    if response == None :
                        print("GPTエラー。おそらくトークン上限。1分まつ")
                        time.sleep(60)
                    else :
                        l_topic_segments = self.mo.myjson(response)
                        if l_topic_segments is None :
                            #大体はトークン制限に引っ掛かってる。1分ウェイトを掛ける
                            print("JSONがNone。再実行。")
                            time.sleep(1)
                            self.mo.set_systemprompt("")
                            self.mo.create_thread()
                            self.mo.create_message(pmt1)
                            response = None

                #最後のグループは、次のグループに含める
                if n_loop >= len(l_minutes_split)-1 :
                    l_topic_segments_all.extend( l_topic_segments )
                    l_lastgroup = []
                else :
                    l_topic_segments_all.extend( l_topic_segments[:-1] )
                    #最後のグループ調整
                    id_lastgroup_from = int( l_topic_segments[-1]["開始行id"] )
                    id_lastgroup_to   = int( l_topic_segments[-1]["終了行id"] )
                    l_lastgroup = self.l_minutes[id_lastgroup_from:id_lastgroup_to+1]

            return l_topic_segments_all


        def __split_list_by_length(self, l_list, max_length):
            """
            文字列リストを、リストの文字数で分割する。
            議事録など膨大なテキストを分割するためのもの。
            改行でリストを作り、そのリストをこの関数に入れて、3万文字ごとに分割するなどに使う。
            """
            result = []
            current_list = []
            current_length = 0

            for string in l_list:
                if current_length + len(string) > max_length:
                    result.append(current_list)
                    current_list = []
                    current_length = 0
                current_list.append(string)
                current_length += len(string)
            
            if current_list:
                result.append(current_list)
            
            return result


        def __youyaku_minutes(self, txt_minutes, kobetsu_msg:str=None)->dict :
            # txt_minutes(議事録データ)を要約する。
            # `id|talk\n0|あいう\n1|えお\n`というフォーマット
            # 戻り値は、辞書型

            prompt_youyaku = '''以下の会議文字起こしについて、どのようなことが議論されたかを要約してください。
また、タスクや宿題があれば、それも抽出してください。宿題は、あなたの推測で書き出すのではなく、「〇〇します」「〇〇してください」「後で〇〇する」「〇〇をリストアップする」「これは宿題ですね」といった発言がある場合にのみ抽出してください。

出力形式: """
```json
{{ 
    "トピックタイトル":"", 
    "要約":[
        {{ "要約内容": "", "発言元id": [] }},
    ], 
    "宿題":[ 
        {{ "宿題内容": "", "宿題に関するポイントやメモ": [], "発言元id": [] }},
    ] 
}}
```
"""

会議文字起こし: """
{txt_minutes}
"""
'''
            if kobetsu_msg is not None :
                prompt_youyaku = f"まず最初に、`{kobetsu_msg}`と言ってください。その後、次の処理を行ってください。\n{prompt_youyaku}"

            #GPT照会(スレッドは毎回新しく。そうしないと文字制限くらう)
            self.mo.set_systemprompt("あなたは、優秀なライターです。会議で議論された主要なトピックと決定事項を要約して、わかりやすいメモを作成することができます。")
            self.mo.create_thread()

            pmt1 = prompt_youyaku.format(txt_minutes=txt_minutes)
            self.mo.create_message(pmt1)
            response = self.mo.run()

            j = self.mo.myjson(response)
            return j


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


    #-------------------------------------------------#
    #--- My GPTs in myopenai -------------------------#
    #-------------------------------------------------#
    class mygpts:
        def __init__(self, mo):
            self.currstep = 0
            self.nextstep = 0           # 次の質問。ifだと、stepと同じ値が入る
            self.f_userturn = False     # このフラグが立っていたら、ユーザーメッセージを入れる
            self.f_if_ng = True         # type=ifでNGになった場合、フラグが立つ(特に使ってないけど、いずれ何かに使いそう)
            self.f_running = False      # post_registered_questionが動いているかどうか
            self.mo = mo                # myopenaiのインスタンス
            self.qlist              = []
            self.log                = []
            self.currentcmd         = ""        #どのコマンドが直前で流れたかを保持
            self.token_queue_gpts   = queue.Queue()   #gptsのpost_commandでもテケテケ表示できるように
            self.imgcount           = 0                 #ダリで作った画像の連番
            self.f_goto             = False             #gotoコマンドで変化球になった場合
            self.que_msg_autochat   = queue.Queue()     #autochatで使うキュー
        
        def __get_qdata(self, id: int) -> dict:
            return next(item for item in self.qlist if item["id"] == id)

        def __adjust_q(self, q: str) -> str:
            # フォーマット : {jsonresult:A,B} AはQID、BはItemName
            # 例：あいう{jsonresult:7,prompt}えお→{}の中が、id7のJSONDATAのpromptに置換される
            if '{jsonresult:' in q:
                pattern = r"\{(.*?)\}"
                command = re.findall(pattern, q)[0]  # 正規表現で抽出

                qid = command.split(":")[1].split(",")[0].strip()
                itemname = command.split(":")[1].split(",")[1].strip()
                targetresult = [x["msg"] for x in self.log if x["role"] == 'assistant' and x["baseqid"] == int(qid)]
                
                jsondata = self.mo.myjson(targetresult[-1])  # -1=最新の結果
                msg = re.sub(pattern, jsondata[itemname], q)  # {}部分を置換


            else:
                msg = q

            # ||で囲まれたコマンド部分をつぶす。
            pattern = r"\|(.*?)\|"
            msg = re.sub(pattern, "", msg)

            return msg
        
        def __get_dalle_option(self, q) :
            # |"dall-e-3":7|を抽出
            pattern = r"\|dalle:(.*?)\|"
            command = re.findall(pattern, q)  # 正規表現で抽出
            model = None
            size  = None
            for c in command : 
                model = c.split(",")[0].strip()
                size  = c.split(",")[1].strip()
                break #複数あっても、最初の１つだけ

            return model, size

        def __set_nextstep(self, basenext: int, msg: str, idx: int = 0) -> int:
            # |goto:7|を抽出
            pattern = r"\|goto:(.*?)\|"
            command = re.findall(pattern, msg)  # 正規表現で抽出
            nextstep = basenext
            self.f_goto = False
            for c in command : 
                no = int(c.split(",")[idx])
                nextstep = no
                self.f_goto = True
                break #複数あっても、最初の１つだけ

            self.nextstep = nextstep        
            return nextstep

        def get_log(self) :
            return self.log
        
        def get_currentcommand(self) :
            return self.currentcmd

        def get_nextcommand(self) :
            q = self.__get_qdata(self.nextstep)
            return q['type']

        def is_passcase(self) :
            #今がif/gotonextで、かつ次のステップに進もうとしている場合は、JSON出力とかなので、スルー
            flg = False 
            if self.currentcmd == "if" and self.f_if_ng == False :
                flg = True
            elif self.currentcmd == "gotonext_without_response" :
                flg = True
            elif self.currentcmd == "dalle" :
                flg = True
            else :
                flg = False

            print(f"passcase: current command={self.currentcmd}, currstep={self.currstep}, nextstep={self.nextstep}")

            return flg
        
        def is_eoq(self):
            return self.currstep is None

        def is_userturn(self):
            return self.f_userturn

        def set_questions(self, fn: str):
            """
            normal: その文章をGPTに投げて回答を受け取った後、ユーザーからのインプットを待つ
            if: その文章をGPTに投げて得られた回答にJSON文が含まれていたら、次のQにステップを進める（投げる）
            gotonext: その文章をGPTに投げて回答を得た後、ユーザーメッセージを受け取らずに次の質問に移る
            gotonext_without_response: その文章をGPTに投げて回答を得た後、ユーザーメッセージを受け取らずに次の質問に移る。しかもGPTの出力もしない
            """
            qlist = []
            with open(fn, "r", encoding='utf-8') as f:
                l_txt = [part.strip() for part in f.read().split("==========") if part.strip()]
                for s in l_txt:
                    l = s.split('----------')
                    if len(l) == 3:
                        qlist.append({"id": int(l[0]), "type": l[2].strip(), "q": l[1].strip()})
                    else:
                        print("スクリプトファイルがおかしいかも？")
                        exit(0)

            qlist = [
                {**item, "nextid": qlist[i + 1]["id"] if i + 1 < len(qlist) else None}
                for i, item in enumerate(qlist)
            ]

            # 重複チェック
            l_id = [x['id'] for x in qlist]
            l_id_dup = set(x for x in l_id if l_id.count(x) > 1)
            if l_id_dup:
                print(f"idが重複しています {l_id_dup}")
                exit(0)

            # IDチェック（intかどうか）
            if not all(isinstance(item, int) for item in l_id):
                print(f"IDがint型じゃないものがあります。 {l_id}")
                exit(0)

            self.currstep = qlist[0]['id']
            self.nextstep = self.currstep  # 一番初めは、同じ値をセットしておく
            self.qlist = qlist





        def post_registered_question(self, f_printlog:bool=False, f_stream:bool=False) -> str:
            self.token_queue_gpts = queue.Queue() #念のためトークンをクリアしとく
            self.f_running = False 

            print(f"f_stream={f_stream}")
            if self.f_userturn:
                print("ユーザーの入力を先にしてください。")
                return None
    
            self.currstep = self.nextstep
            if self.currstep is None:
                print("設定質問は以上です")
                return None

            q = self.__get_qdata(self.currstep)
            origmsg = q['q']
            msg = self.__adjust_q(origmsg)
            self.currentcmd = q['type']
            print(f"msg=[{msg}], cmd=[{self.currentcmd}]")


            if self.currentcmd not in ['dalle']: # dalleは画像生成するので、プロンプトを投げない
                self.mo.create_message(msg)
                print(f"gpts --- no={self.currstep}, cmd={self.currentcmd}")
                if f_stream :
                    thread = threading.Thread(target=self.mo.run, kwargs={'f_stream':True, 'f_print':f_printlog})
                    thread.start()
                    time.sleep(0.1)
                    while self.mo.is_running() :
                        time.sleep(0.1)
                        token = self.mo.get_queue()
                        if token :
                            self.token_queue_gpts.put(token)
                    #最後の残りかすトークン
                    token = self.mo.get_queue()
                    if token :
                        self.token_queue_gpts.put(token)
                    self.token_queue_gpts.put('[[end]]') #終了サイン
                else :
                    response = self.mo.run(f_stream=False)
                    self.token_queue_gpts.put(response) #Threading実行されてることもあるし、念のためトークンキューにも入れておく
                    self.token_queue_gpts.put("[[end]]")

                response = self.mo.get_lastmsg()
                self.log.append({"role": "assistant", "msg":response, "baseqid": self.currstep})
            else:
                # dalleではresponseはないので、空を作っておく
                response = ""

            if self.get_nextcommand() == 'dalle' :
                self.token_queue_gpts.put("[[next dalle]]")


            if q['type'] == 'normal':
                self.f_userturn = True
                self.__set_nextstep(q['nextid'], origmsg)

            elif q['type'] == 'if':
                j = self.mo.myjson(response)
                if j is not None:
                    self.f_if_ng = False
                    self.f_userturn = False  # 判定OKなら、次の質問を流す
                    self.__set_nextstep(q['nextid'], origmsg, 0)
                else:
                    self.f_if_ng = True
                    self.f_userturn = True  # NGの場合は、修正回答をユーザーからもらう
                    self.__set_nextstep(self.currstep, origmsg, 1)
                    #もし移動先指定があったら、userturnはFalseになる
                    if self.currstep != self.nextstep : #通常は、NGの場合はcurrstepとnextstepが一緒になる
                        self.f_userturn = False

            elif q['type'] in ['gotonext', "gotonext_without_response"]:
                self.f_userturn = False
                self.__set_nextstep(q['nextid'], origmsg)

            elif q['type'] == 'dalle':
                # 画像生成処理
                unique_id = uuid.uuid4()
                filename = f"gazou_{unique_id}.png"
                model, size = self.__get_dalle_option(origmsg)
                if f_printlog :
                    print(f"model=[{model}], size=[{size}], filename=[{filename}], msg=[{msg}]")
                self.mo.image_generate(
                    msg,
                    size=size,
                    model=model,
                    filename=filename,
                )
                response = filename
                self.imgcount += 1
                self.token_queue_gpts.put(f"dalle:{filename}, {str(self.imgcount)}") #Threading実行されてるとき用
                self.token_queue_gpts.put('[[end]]') #これがないとThreading実行の時に無限ループに陥る
                self.log.append({"role": "dalle", "msg": filename, "baseqid": self.currstep})
                self.f_userturn = False
                self.__set_nextstep(q['nextid'], origmsg) 
            else:
                print(f"type設定がおかしいかも？ : qno = {q['id']}")
                exit(0)

            self.f_running = False 
            return response

        def is_running(self) :
            return self.f_running
        
        #--- テケテケ表示に欠かせない関数(GPTs版) -----------------#
        def get_gpts_queue(self)->str :
            token = ""
            if self.token_queue_gpts.qsize() > 0 :
                token = self.token_queue_gpts.get() #[[end]]を切り分けたいので、合体ループは使わない
            return token
        

        def set_usermessage(self, msg: str):
            self.mo.create_message(msg)
            self.log.append({"role": "user", "msg": msg, "baseqid": None})
            self.f_userturn = False


        def autochat(self, f_stream:bool=True) :
            while self.is_userturn() == False :
                if self.is_eoq() :
                    break
                
                thread = threading.Thread(target=self.post_registered_question, kwargs={'f_stream':f_stream,'f_printlog':True})
                thread.start()

                res = ""
                while True :
                    fff = thread.is_alive()
                    nnn = self.token_queue_gpts.qsize() 
                    if fff == False and nnn == 0 :
                        break

                    token = self.get_gpts_queue()
                    if token == "" :
                        time.sleep(0.1)
                    elif token == "[[end]]" :
                        if self.is_passcase() == True :
                            res = ""
                        else :
                            self.que_msg_autochat.put(f"response:{res}")
                            res = ""
                    elif token[:6] == "dalle:" :
                        #画像生成の時の処理
                        self.que_msg_autochat.put(token)
                        res = ""
                    elif token == "[[next dalle]]" :
                        self.que_msg_autochat.put(token)
                    else :
                        res += token
                        self.que_msg_autochat.put(f"stream:{res}")

                thread.join() #念のためthreadが閉じたことを確認

        def get_autochat_response(self) -> str :
            res = ""
            if self.que_msg_autochat.qsize() > 0 :
                res = self.que_msg_autochat.get()
            return res

        def get_autochat_queuecount(self) -> int :
            return self.que_msg_autochat.qsize()


#-------------------------------------------------#
#-------------------------------------------------#
#-------------------------------------------------#
from dotenv import load_dotenv
load_dotenv()

# thread_id = mo.get_threadid()
# print(f"thread_id = {thread_id}")



# def tanjun() :
#     mo = myopenai('gpt-3.5-turbo')

#     mo.set_prompt('あなたは精神科医です。私の悩みを聞いて、適切にアドバイスをしてください。')
#     conv = mo.load_conversation()
#     ans = conv.predict(input='上司と反りが合わずに悩んでいる。')
#     print(ans)
#     ans = conv.predict(input='別のアドバイスありますか？')
#     print(ans)
#     print(conv.memory)


# def embedding_ppt() :
#     mo = myopenai('gpt-3.5-turbo')

#     # ベクトル化の処理
#     # file_path = r'C:\Users\大村真ShinOOMURA\Documents\大村\スコアカード虎の巻\スコアカード虎の巻.pptx'
#     # mo.ppt_to_vector(file_path)

#     # 流れ：質問と類似度の高いドキュメントをシステムメッセージに組み込んで、質問を投げる。なので追加質問は最初の質問に関係しないとワークしないので注意
#     # 事前準備
#     vecname = 'スコアカード虎の巻'
#     Q       = 'ダミー化について教えてください。'
#     prompt  = (
#         '今からあなたに質問します。また、マニュアルからEmbedding処理を掛けてその質問と類似度の高い文章群をお渡します。\n'
#         'そのEmbedding文章群を元に、以下のルールに従って回答してください。\n'
#         '\n'
#         'ルール: """\n'
#         '* 以下の回答フォーマットのように回答する。\n'
#         '* 質問に200文字以内で回答\n'
#         '* 質問と類似度の高いページ番号を最大３つ回答。\n'
#         '* 関連する文書が「Embedding文章群」になければ、「分かりません」と回答'
#         '"""\n'
#         '\n'
#         '回答フォーマット: """\n'
#         '関連ページ（類似度の高いページ）：●ページ、●ページ、●ページ\n'
#         '回答: ●●●\n'
#         '"""\n'
#         '\n'
#     )



#     # ベクトルデータの読み込み
#     df_vector = mo.load_vector(vecname)
#     # プロンプトセット
#     mo.set_prompt(prompt)

#     # 類似文書の抽出
#     txt_ruiji = mo.search_reviews(Q, df_vector, n=10)

#     Q_plus = (
#         f'{Q}\n'
#         '\n'
#         'Embedding文章群: """\n'
#         '|ドキュメント名|ページ番号|文章|類似度|\n'
#         f'{txt_ruiji}\n'
#         '"""\n'
#     )



#     # チャット開始
#     conv = mo.load_conversation()
#     ans = conv.predict(input=Q_plus)
#     print(ans)
#     ans = conv.predict(input='関連ページは？')
#     print(ans)
#     ans = conv.predict(input='Coarse Classingについて教えて')
#     print(ans)



# def embedding_txt() :
#     mo = myopenai('gpt-3.5-turbo')

#     # ベクトル化の処理
#     file_path = r'C:\temp\Apps\Python\st_toranomaki\Docker_to_Studio.txt'
#     # mo.txt_to_vector(file_path)

#     # 流れ：質問と類似度の高いドキュメントをシステムメッセージに組み込んで、質問を投げる。なので追加質問は最初の質問に関係しないとワークしないので注意
#     # 事前準備
#     vecname = 'Docker_to_Studio'
#     Q       = 'Dockerfileのサンプルを知りたい'
#     prompt  = (
#         '今からあなたに質問します。また、マニュアルからEmbedding処理を掛けてその質問と類似度の高い文章群をお渡します。\n'
#         'そのEmbedding文章群を元に、以下のルールに従って回答してください。\n'
#         '\n'
#         'ルール: """\n'
#         '* 以下の回答フォーマットのように回答する。\n'
#         '* 質問に200文字以内で回答\n'
#         '* 質問と類似度の高い行番号を最大３つ回答。\n'
#         '* 関連する文書が「Embedding文章群」になければ、「分かりません」と回答'
#         '"""\n'
#         '\n'
#         '回答フォーマット: """\n'
#         '関連する行番号（類似度の高い行番号）：●行、●行、●行\n'
#         '回答: ●●●\n'
#         '"""\n'
#         '\n'
#     )



#     # ベクトルデータの読み込み
#     df_vector = mo.load_vector(vecname)
#     # プロンプトセット
#     mo.set_prompt(prompt)

#     # 類似文書の抽出
#     txt_ruiji = mo.search_reviews(Q, df_vector, n=10)

#     Q_plus = (
#         f'{Q}\n'
#         '\n'
#         'Embedding文章群: """\n'
#         '|行番号|文章|類似度|\n'
#         f'{txt_ruiji}\n'
#         '"""\n'
#     )



#     # チャット開始
#     conv = mo.load_conversation()
#     ans = conv.predict(input=Q_plus)
#     print(ans)
#     ans = conv.predict(input='関連ページは？')
#     print(ans)
#     ans = conv.predict(input='Coarse Classingについて教えて')
#     print(ans)


# def image_generate() :
#     mo = myopenai()
#     image_url = mo.image_generate("a white cat", size="256x256", model='dall-e-2', filename="downloaded_image.png")
#     print(image_url)

if __name__ == '__main__' :
    # mo.pdf_to_vector(r'C:\temp\Apps\Python\st_toranomaki\【御請求書】テスト.pdf')
    # tanjun()
    # embedding_ppt()
    # embedding_txt()
    # image_generate()


    #--- 議事録要約サンプル ----------------------------#
    def gijiroku_youyaku() :
        mo = myopenai()
        giji = mo.giji_rocker(mo)

        #議事録データ読み込み & セット
        with open(r"C:\Users\shino\downloads\議事録‗NOK‗20240620.txt", "r", encoding="utf-8") as f :
            txt = f.read()
        giji.set_mojiokoshi(txt, 2)

        # #文字数が多すぎるので、いくつかのトピックに分割。(処理長い)
        # giji.split_mojiokoshi()
        # #いったん保存
        # giji.save_topic_segments(r'C:\Users\shino\downloads\l_topic_segments.json')

        # トピック分割データ読み込み
        giji.load_topic_segments(r'C:\Users\shino\downloads\l_topic_segments.json')

        giji.youyaku_minutes()
        giji.save_youyaku(r'C:\Users\shino\downloads\res_youyaku.json')
        giji.load_youyaku(r'C:\Users\shino\downloads\res_youyaku.json')
        l_youyaku = giji.get_youyaku()


    gijiroku_youyaku() #議事録要約

# StudioにDockerをあげる時のTips集


