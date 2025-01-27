from openai import OpenAI
from dotenv import load_dotenv

import  os
import requests #画像downloadで使用
import threading
import time
import queue
import base64

from pydantic import BaseModel, Field
from typing import List

class myopenai :

    client = None 
    default_model = None

    def __init__(self, model:str=None) :
        self.client = OpenAI()
        self.queue_response_text = queue.Queue()
        self.f_running = True
        self.messages = []
        if model :
            self.default_model = model

    def is_running(self) :
        return self.f_running
    def is_running_or_queue(self) :
        return self.f_running or not self.is_queue_empty()
    
    def is_queue_empty(self) :
        return self.queue_response_text.empty()

    def get_messages(self) :
        return self.messages

    def delete_all_messages(self) :
        self.messages = []

    def get_text_from_message(self, msg:dict=None) :
        if not msg :
            msg = self.messages[-1]
        for c in msg["content"] :
            if c["type"] == "text" :
                return c["text"]
    def get_audio_from_message(self, msg:dict=None) :
        if not msg :
            msg = self.messages[-1]
        for c in msg["content"] :
            if c["type"] == "input_audio" :
                data_wav = base64.b64decode(c["input_audio"]["data"])
                return data_wav
    
    # def set_systemprompt(self, txt:str):
    #     self.messages.append(
    #         {
    #             "role": "system", 
    #             "content": [{"type": "text", "text": txt }]
    #         }
    #     )
    def add_message(self, msg:str, role:str="user") :
        self.messages.append(
            {
                "role": role, 
                "content": [{"type": "text", "text": msg }]
            }
        )

    def add_audiodata(self, audiodata, format, text:str=None, role:str="user") :
        data_b64 = base64.b64encode(audiodata).decode('utf-8')
        content = [{
                "type": "input_audio",
                "input_audio": {
                    "data": data_b64,
                    "format": format
                }
        }]
        if text :
            content.append({"type": "text", "text": text})

        self.messages.append(
            {
                "role": role,
                "content": content
            }
        )
    def add_audio_fromfile(self, file_path, role:str="user") :
        audio_data = open(file_path, "rb").read()
        ext = os.path.splitext(file_path)[1].replace(".","")
        self.add_audiodata(audio_data, ext, role)

    def get_queue(self) -> str :
        token = ""
        while not self.queue_response_text.empty() :
            token += self.queue_response_text.get(timeout=0.1)
        return token
    
    def run_to_audio(self, model:str=None) :
        self.f_running = True
        if not model :
            model = self.default_model

        completion = self.client.chat.completions.create(
            model       = model,
            modalities  = ["text", "audio"],
            audio       = {"voice": "alloy", "format": "wav"},
            messages    = self.messages
        )

        data_txt = completion.choices[0].message.audio.transcript
        self.add_message(data_txt, role="assistant") #assistantに音声を登録すると、そのあとrunでエラーになる
        data_b64 = completion.choices[0].message.audio.data
        data_wav = base64.b64decode(data_b64)
        # self.add_audiodata(data_wav, "wav", data_txt, role="assistant") #assistantに音声を登録すると、そのあとrunでエラーになる
        return data_wav

    def run_stream(self, model:str=None) -> str :
        self.f_running = True
        if not model :
            model = self.default_model

        stream = self.client.chat.completions.create(
            model       = model,
            messages    = self.messages,
            stream      = True,
        )
        response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                token = chunk.choices[0].delta.content
                response += token
                self.queue_response_text.put(token)
                # print(chunk.choices[0].delta.content, end="")
        self.add_message(response, "assistant")
        self.f_running = False
        return response

    def run(self, model:str=None) -> str :
        self.f_running = True
        if not model :
            model = self.default_model

        completion = self.client.chat.completions.create(
            model       = model,
            messages    = self.messages,
        )

        response = completion.choices[0].message.content
        self.add_message(response, "assistant")
        self.f_running = False
        return response

    def run_so(self, ResponseStep, model:str=None) :
        self.f_running = True
        if not model :
            model = self.default_model

        response = self.client.beta.chat.completions.parse(
            model           = model,
            # temperature     = 0,
            messages        = self.messages,
            response_format = ResponseStep,
        )
        self.add_message(response.choices[0].message.content, "assistant")
        self.f_running = False
        return response.choices[0].message.parsed

        # try:
        # except Exception as e:
        #     print(f"エラー：{e}")
        #     return None

    def image_generate(self, pmt:str, file_path:str, model:str='dall-e-3', size:str='1024x1024', n:int=1) -> str :
        # size(dalle3): 1024x1024, 1024x1792 or 1792x1024 
        # size(dalle2): 256x256, 512x512, 1024x1024 e2とe3で指定できるサイズが違うので注意！
        # model: dall-e-3, dall-e-2

        image_url = None
        try:
            response = self.client.images.generate(
                model  = model,
                prompt = pmt,
                size   = size,
                quality="standard",
                n      = n, #dalle2のみ指定できるみたい
            )
            image_url = response.data[0].url
            url_response = requests.get(image_url)
            if url_response.status_code == 200:
                open(file_path, 'wb').write(url_response.content)
            else:
                print("画像のダウンロードに失敗しました。")

        except Exception as e:
            error_detail = e.response.json()
            print(f"error in image_generate: {e.response.status_code} - {error_detail['error']['message']}")

        return image_url

    def speech_to_text(self, audio_data, model:str="whisper-1", lang:str='ja'):
        transcription = self.client.audio.transcriptions.create(
            model    = model,
            language = lang,
            file     = audio_data,
        )
        return transcription.text
    def speech_to_text_from_file(self, file_path, model:str="whisper-1", lang:str='ja'):
        audio_data = open(file_path, "rb")
        return self.speech_to_text(audio_data, model, lang)

    def text_to_speech(self, text:str, file_path:str, voice:str="alloy", model:str='tts-1') -> str :
        """
        alloy : アナウンサー的な男性
        echo : 渋い声のアナウンサー的な男性
        fable : 高い声のアナウンサー的な男性
        onyx : かなり低い俳優的な男性
        nova : アナウンサー的な女性
        shimmer : 低めの声の女性
        """
        response = self.client.audio.speech.create(
            model   = model,
            voice   = f"{voice}",
            input   = text,
        )
        if os.path.exists(file_path) :
            os.remove(file_path) #ファイル削除
        with open(file_path, "wb") as file:
            file.write(response.content)
    

if __name__ == "__main__" :
    load_dotenv()
    mo = myopenai("gpt-4o")

    #-----------------------------------------
    # 使い方あれこれ
    #-----------------------------------------
    # プロンプトセット
    mo.add_message("あなたはアメリカメジャーリーグのスペシャリストです。", role="system")
    mo.add_message("大谷翔平の誕生日は？")
    #ストリーミング表示
    run_thread = threading.Thread(target=mo.run_stream, kwargs={})
    run_thread.start()
    while mo.is_running_or_queue():
        print(mo.get_queue(), end="", flush=True)
        time.sleep(0.1)
    run_thread.join()

    # 音声で質問->音声で回答
    mo.text_to_speech("出身地についても教えて", "speech_sample.mp3")
    mo.add_audio_fromfile("speech_sample.mp3")
    wav = mo.run_to_audio(model="gpt-4o-audio-preview") #音声が入っている場合は、このモデルがマスト
    open("回答.wav", "wb").write(wav)

    # 音声で質問->テキストで回答（多分早い）
    mo.text_to_speech("奥さんの名前は？", "speech_sample.mp3")
    mo.add_audio_fromfile("speech_sample.mp3")
    response = mo.run(model="gpt-4o-audio-preview") #音声が入っている場合は、このモデルがマスト
    print(response)

    #-----------------------------------------
    # 構造化データで回答を得る
    #-----------------------------------------
    mo.delete_all_messages()
    mo.add_message("あなたはアメリカメジャーリーグのスペシャリストです。", role="system")
    mo.add_message("大谷翔平と山本由伸の誕生日と出身地を教えて")

    class personal_info(BaseModel) :
        name        : str = Field(...,description="名前")
        birthday    : str = Field(...,description="誕生日")
        syussinchi  : str = Field(...,description="出身地（市まで）") #descは結構重要
    class responsemodel(BaseModel):
        personal_infos : List[personal_info]

    response_data = mo.run_so(responsemodel)
    l_personal_infos = [x.model_dump() for x in response_data.personal_infos]
    print(l_personal_infos)

    #-----------------------------------------
    # その他
    #-----------------------------------------
    # 画像生成
    mo.image_generate("もふもふのわんこ","もふもふわんこ.png")
    text = mo.speech_to_text_from_file("speech_sample.mp3")
