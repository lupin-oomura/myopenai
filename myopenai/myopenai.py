from openai import OpenAI
from dotenv import load_dotenv

import  os
import requests #画像downloadで使用
import threading
import time
import queue
import base64
import json
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
        self.l_cost = []
        if model :
            self.default_model = model

        # pricedata.jsonを読み込む
        current_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(current_dir, 'pricedata.json'), 'r') as f:
            self.d_pricedata = json.load(f)

    def is_running(self) :
        return self.f_running
    def is_running_or_queue(self) :
        time.sleep(0.05) #直後に動かされた時にfalseになるのを防ぐ
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
    
    def add_message(self, msg:str, role:str="user", type:str="text") :
        if type == "text" :
            data = {"role": role, "content": [{"type": "text", "text": msg }]}
        elif type == "audio" :
            data = {"role": role, "audio":{"id": msg}}

        self.messages.append(data)








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
    

    def run(self, model:str=None) -> str :
        self.f_running = True
        if not model :
            model = self.default_model

        completion = self.client.chat.completions.create(
            model       = model,
            messages    = self.messages,
        )
        self.l_cost.append({
            "model"               : completion.model,
            "tokens_input"        : completion.usage.prompt_tokens,
            "tokens_input_cached" : completion.usage.prompt_tokens_details.cached_tokens,
            "tokens_input_audio"  : completion.usage.prompt_tokens_details.audio_tokens,
            "tokens_output"       : completion.usage.completion_tokens,
            "tokens_output_audio" : completion.usage.completion_tokens_details.audio_tokens
        })

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

        self.l_cost.append({
            "model"               : response.model,
            "tokens_input"        : response.usage.prompt_tokens,
            "tokens_input_cached" : response.usage.prompt_tokens_details.cached_tokens,
            "tokens_input_audio"  : response.usage.prompt_tokens_details.audio_tokens,
            "tokens_output"       : response.usage.completion_tokens,
            "tokens_output_audio" : response.usage.completion_tokens_details.audio_tokens
        })
        self.f_running = False
        return response.choices[0].message.parsed


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
        audio_id = completion.choices[0].message.audio.id
        data_txt = completion.choices[0].message.audio.transcript
        self.add_message(data_txt, role="assistant") #assistantに音声を登録すると、そのあとrunでエラーになる
        # self.add_message(audio_id, "assistant", "audio") #こうやって登録することも可能
        data_b64 = completion.choices[0].message.audio.data
        data_wav = base64.b64decode(data_b64)


        self.l_cost.append({
            "model"               : completion.model,
            "tokens_input"        : completion.usage.prompt_tokens,
            "tokens_input_cached" : completion.usage.prompt_tokens_details.cached_tokens,
            "tokens_input_audio"  : completion.usage.prompt_tokens_details.audio_tokens,
            "tokens_output"       : completion.usage.completion_tokens,
            "tokens_output_audio" : completion.usage.completion_tokens_details.audio_tokens
        })

        self.f_running = False

        return data_wav

    def run_stream(self, model:str=None) -> str :
        self.f_running = True
        if not model :
            model = self.default_model

        stream = self.client.chat.completions.create(
            model          = model,
            messages       = self.messages,
            stream         = True,
            stream_options = {"include_usage": True},
        )
        response = ""
        d_cost = {}
        for chunk in stream:
            if chunk.choices:
                if chunk.choices[0].delta.content is not None:
                    token = chunk.choices[0].delta.content
                    response += token
                    self.queue_response_text.put(token)
                    # print(chunk.choices[0].delta.content, end="")
            if chunk.usage:
                self.l_cost.append({
                    "model"               : chunk.model,
                    "tokens_input"        : chunk.usage.prompt_tokens,
                    "tokens_input_cached" : chunk.usage.prompt_tokens_details.cached_tokens,
                    "tokens_input_audio"  : chunk.usage.prompt_tokens_details.audio_tokens,
                    "tokens_output"       : chunk.usage.completion_tokens,
                    "tokens_output_audio" : chunk.usage.completion_tokens_details.audio_tokens
                })

        self.add_message(response, "assistant")
        self.f_running = False
        return response

    def image_generate(self, pmt:str, file_path:str, model:str='dall-e-3', quality:str='standard', size:str='1024x1024', n:int=1) -> str :
        # size(dalle3): 1024x1024, 1024x1792 or 1792x1024 
        # size(dalle2): 256x256, 512x512, 1024x1024 e2とe3で指定できるサイズが違うので注意！
        # model: dall-e-3, dall-e-2
        # quality: standard, hd

        image_url = None
        try:
            response = self.client.images.generate(
                model  = model,
                prompt = pmt,
                size   = size,
                quality=quality,
                n      = n, #dalle2のみ指定できるみたい
            )
            image_url = response.data[0].url
            url_response = requests.get(image_url)
            if url_response.status_code == 200:
                open(file_path, 'wb').write(url_response.content)
            else:
                print("画像のダウンロードに失敗しました。")

            # 料金は、1枚当たりになるそう( https://platform.openai.com/docs/pricing )
            self.l_cost.append({
                "model" : model + "-" + quality,
                "size"  : size
            })
            self.f_running = False

        except Exception as e:
            error_detail = e.response.json()
            print(f"error in image_generate: {e.response.status_code} - {error_detail['error']['message']}")

        return image_url

    def speech_to_text(self, audio_data, model:str="whisper-1", lang:str='ja', prompt:str=None):
        transcription = self.client.audio.transcriptions.create(
            model                   = model,
            language                = lang,
            file                    = audio_data,
            response_format         = "verbose_json",
            timestamp_granularities = ["segment"],
            prompt                  = prompt
        )

        d_whisper_result = {}
        d_whisper_result["text"] = transcription.text
        d_whisper_result["duration"] = transcription.duration
        d_whisper_result["segments"] = []
        for segment in transcription.segments:
            res_text = {
                "text"  : segment.text, 
                "start" : segment.start, 
                "end"   : segment.end
            }
            d_whisper_result["segments"].append(res_text)

        # 料金は、時間当たりになるそう( https://platform.openai.com/docs/pricing )
        self.l_cost.append({
            "model"     : model,
            "duration"  : transcription.duration
        })
        self.f_running = False
        return d_whisper_result
    
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

        # 料金は、1M文字で15ドルとのこと（ https://openai.com/ja-JP/api/pricing/ https://platform.openai.com/docs/pricing )
        # 日本語のような全角文字の扱いはイマイチ不明。日本語でも1文字1カウントという記事が多い。
        self.l_cost.append({
            "model"             : model,
            "text_length_input" : len(text)
        })
        self.f_running = False

    def get_cost_all(self) :
        return sum([self.get_cost(item) for item in self.l_cost])

    def get_cost(self, item:dict=None) :
        d_pricedata = self.d_pricedata
        if not item :
            item = self.l_cost[-1]

        k = item["model"]
        v = item
        if "whisper" in k :
            unitcost = d_pricedata[k]["transcription"]["cost_per_minute"] / 60
            cost = v["duration"] * unitcost
        elif "tts-" in k :
            unitcost = d_pricedata[k]["speech_generation"]["cost_per_1m_characters"]  / 1000000
            cost = v["text_length_input"] * unitcost
        elif "dall-e" in k :
            cost = d_pricedata[k]["image_generation"][f"price_{v['size']}"]
        else :
            pricedata = d_pricedata[k]
            tokens_input_text_cached = v["tokens_input_cached"] if "tokens_input_cached" in v and v["tokens_input_cached"] is not None else 0
            tokens_input_audio = v["tokens_input_audio"] if "tokens_input_audio" in v and v["tokens_input_audio"] is not None else 0
            tokens_input_text = v["tokens_input"] if "tokens_input" in v and v["tokens_input"] is not None else 0
            tokens_input_text = tokens_input_text - tokens_input_audio - tokens_input_text_cached

            tokens_output_text_cached = v["tokens_output_cached"] if "tokens_output_cached" in v and v["tokens_output_cached"] is not None else 0
            tokens_output_audio       = v["tokens_output_audio" ] if "tokens_output_audio"  in v and v["tokens_output_audio" ] is not None else 0
            tokens_output_text        = v["tokens_output"       ] if "tokens_output"        in v and v["tokens_output"       ] is not None else 0
            tokens_output_text        = tokens_output_text - tokens_output_audio - tokens_output_text_cached


            unitcost_input_text   = (pricedata["text_tokens" ]["input_tokens" ] if "text_tokens"  in pricedata and "input_tokens"  in pricedata["text_tokens" ] else 0) / 1000000
            unitcost_input_audio  = (pricedata["audio_tokens"]["input_tokens" ] if "audio_tokens" in pricedata and "input_tokens"  in pricedata["audio_tokens"] else 0) / 1000000
            unitcost_input_cached = (pricedata["text_tokens" ]["cached_input_tokens"] if "text_tokens"  in pricedata and "cached_input_tokens" in pricedata["text_tokens" ] and pricedata["text_tokens" ]["cached_input_tokens"] is not None else 0) / 1000000

            unitcost_output_text  = (pricedata["text_tokens" ]["output_tokens"] if "text_tokens"  in pricedata and "output_tokens" in pricedata["text_tokens" ] else 0) / 1000000
            unitcost_output_audio = (pricedata["audio_tokens"]["output_tokens"] if "audio_tokens" in pricedata and "output_tokens" in pricedata["audio_tokens"] else 0) / 1000000
            unitcost_output_cached = (pricedata["text_tokens" ]["cached_output_tokens"] if "text_tokens"  in pricedata and "cached_output_tokens" in pricedata["text_tokens" ] and pricedata["text_tokens" ]["cached_output_tokens"] is not None else 0) / 1000000

            cost_input = unitcost_input_text * tokens_input_text + unitcost_input_audio * tokens_input_audio + unitcost_input_cached * tokens_input_text_cached
            cost_output = unitcost_output_text * tokens_output_text + unitcost_output_audio * tokens_output_audio + unitcost_output_cached * tokens_output_text_cached
            cost = cost_input + cost_output

        return cost





if __name__ == "__main__" :
    load_dotenv()
    mo = myopenai("gpt-4o-mini")

    #-----------------------------------------
    # 使い方あれこれ
    #-----------------------------------------
    #単純照会
    mo.add_message("あなたはアメリカメジャーリーグのスペシャリストです。", role="system")
    mo.add_message("大谷翔平の誕生日は？")
    res = mo.run()
    print(res)
    print(mo.get_cost_all())

    #ストリーミング表示
    mo.add_message("結婚してる？")
    run_thread = threading.Thread(target=mo.run_stream, kwargs={})
    run_thread.start()
    while mo.is_running_or_queue():
        print(mo.get_queue(), end="", flush=True)
        time.sleep(0.1)
    print("\n")
    run_thread.join()

    #--- 音声で回答させるサンプル --------
    # 文章で質問->音声で回答
    mo.add_message("性別は？")
    wav = mo.run_to_audio(model="gpt-4o-mini-audio-preview") #音声が入っている場合は、このモデルがマスト
    open("回答.wav", "wb").write(wav)

    # 準備
    # mo.text_to_speech("出身地についても教えて", "speech_sample1.mp3")
    # mo.text_to_speech("奥さんの名前は？", "speech_sample2.mp3")

    # 音声で質問->音声で回答
    mo.add_audio_fromfile("speech_sample1.mp3")
    wav = mo.run_to_audio(model="gpt-4o-mini-audio-preview") #音声が入っている場合は、このモデルがマスト
    open("回答.wav", "wb").write(wav)

    # 音声で質問->テキストで回答（多分早い）
    mo.add_audio_fromfile("speech_sample2.mp3")
    response = mo.run(model="gpt-4o-mini-audio-preview") #音声が入っている場合は、このモデルがマスト
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

    # Whisper(Speech to Text)
    text = mo.speech_to_text_from_file("speech_sample1.mp3")
    print(text)

    #-----------------------------------------
    # 料金計算
    #-----------------------------------------
    print(mo.get_cost_all())
