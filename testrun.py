# pip install git+https://github.com/lupin-oomura/myfunc.git

import myopenai
from dotenv import load_dotenv
load_dotenv()

import threading
import time


# #--------------------------------------------------------#
# #--- 普通のチャット --------------------------------------#
# #--------------------------------------------------------#
# mo = myopenai.myopenai()
# mo.set_prompt("")
# mo.create_thread()
# mo.create_message("大谷翔平の誕生日は？")
# mo.run(f_stream=False)
# mo.create_message("では、性別は？")
# mo.run()

# #--------------------------------------------------------#
# #--- テケテケ表示チャット ---------------------------------#
# #--------------------------------------------------------#
# def threadrun() :
#     thread = threading.Thread(target=mo.run, kwargs={'f_stream':True, 'f_print':False})
#     thread.start()
#     time.sleep(0.1)
#     while mo.is_running() :
#         time.sleep(0.1)
#         token = mo.get_queue()
#         if token :
#             print(f"token: [{token}]")

# mo = myopenai.myopenai()
# mo.set_prompt("")
# mo.create_thread()
# mo.create_message("大谷翔平の誕生日は？")
# threadrun()
# mo.create_message("では、性別は？")
# threadrun()

# # thread_idを保存しておけば、会話を続けられる
# threadid = mo.get_threadid()
# print(threadid) #このthread_idをメモっておいてください

# #--------------------------------------------------------#
# #--- 過去のスレッドを読み込んで、途中から会話開始 -----------#
# #--------------------------------------------------------#
# #一度実行を止めて、上の“普通のチャット”をコメントアウトして始めてください。
# threadid = 'thread_ay7m7qQzGK9pNQyUwVEgPQn5' #上でメモッたthread_idを貼り付ける
# mo2 = myopenai.myopenai()
# mo2.set_prompt("")
# mo2.set_thread(threadid)
# mo2.create_message("ちなみに、何のスポーツの選手？")
# mo2.run()



#--------------------------------------------------------#
#--- My GPTs風に処理する方法 -----------------------------#
#--------------------------------------------------------#

"""
#コマンド設定
コマンドは、==========(イコール10個)で区切る。
1コマンドには3つの要素がある。----------(ハイフン10個)で区切る。
   ID / コマンド / コマンド種類
コマンド種類は、normal / if / gotonext / dalle
    normal : そのコマンドを投げて、GPTが回答を返して、その後ユーザーに入力を求めるモードにする。 (is_userturn() == True)
    if : そのコマンドを投げた後、JSON形式が返ってきていたら、次のステップに移る (is_userturn() == False)。JSON形式が回答になければ、同じ質問を繰り返す。(is_userturn()==True)
        なので、成功した場合はJSON結果を返すようにコマンドに自分で仕込む必要がある。
        ※NGでも、移動先指定が入っていれば、is_userturn() == Falseになる
    gotonext : コマンドを投げて、GPTが回答を返して、その後ユーザーに入力を求めるモードにならない (is_userturn() == False)
    dalle : 画像生成させる。画像生成のオプションは必ず指定する。メッセージ内に書く（|dalle:dall-e-2,256x256|とか|dalle:dall-e-3,1792x1024|とか）
コマンドには、他の回答のJSON結果を使える。
    例：あいう{jsonresult:5,prompt}えお → {***}が、コマンドID5のJSON結果の"prompt"アイテムの値になる。
通常は上から順にコマンドを流すが、行先指定もできる。以下の仕込みを、メッセージ内に入れる（どこでもOK。GPTに投げるメッセージからは消される）
    |goto:9|   → コマンドID9に進む 
    |goto:9,4| → if文の時は、このように2つ指定する必要あり。OKの場合は9番、NGの場合は4番に飛ぶ。NGでもis_userturn()=Falseになるのでその点注意。
"""


commands = """
==========
1
----------
私に、「こんにちわ。赤と白はどちらが好きですか」と質問してください。
|goto:2|
----------
normal
==========
2
----------
私はどちらの色を選びましたか？
もし赤を選んだら、JSON形式で出力してください。
```json
{"選択色": "赤"}
```
もし赤以外を選んでいたら、もう一度質問してください。（赤を選択するまで、同じ質問を繰り返してください。）
----------
if
==========
3
----------
「あなたは、○○の色が好きなんですね」と言ってください。
----------
gotonext
==========
4
----------
「どんなテーマが良いですか？今パッと思いついたことを話してください。」と言ってください。
----------
normal
==========
5
----------
話したテーマに関するイラストを、私の選んだ色をベース色にして生成してもらいたいです。
そのイラスト生成するためのプロンプトを、英語でJSON形式で出力してください。
```json
{"prompt":"prompt for generating an illustration of the message in English"}
```
----------
gotonext
==========
6
----------
{jsonresult:5,prompt}
|dalle:dall-e-2,256x256|
----------
dalle
==========
7
----------
私は今、dalleで生成したイラストを見ています。
そのイラストが気に入ったかどうかを私に聞いてください。
----------
normal
==========
8
----------
私はイラストを気に入っていますか？
気に入っているようなら、以下のように出力してください。
```json
{"イラスト納得":"Yes"}
気に入っていない場合や、追加要望があった場合は、「了解です。」とだけプロンプトに出力してください。それ以外の文章は不要です。
|goto:9,4|
----------
if
==========
9
----------
「お疲れさまでした。」と言ってください。
----------
gotonext
==========
"""
with open("commanddata.txt", "w", encoding="utf-8") as f:
    f.write(commands)


mo = myopenai.myopenai()
mo.set_prompt("あなたは優秀なコピーライターです。今から私にいろいろと質問をし、その回答に基づいてイラストを生成してもらいます。")
mo.create_thread()

def threadrun() :
    thread = threading.Thread(target=mo.gpts.post_registered_question, kwargs={'f_stream':True,})
    thread.start()
    time.sleep(0.1)
    token = ""
    while token != "[[end]]" :
        time.sleep(0.1)
        token = mo.gpts.get_gpts_queue()
        if token :
            print(f"token: [{token}]")

mo.gpts.set_questions("commanddata.txt")

while not mo.gpts.is_eoq():
    threadrun()
    # mo.gpts.post_registered_question()
    if mo.gpts.is_userturn():
        msg = input("msg:")
        mo.gpts.set_usermessage(msg)

        log = mo.gpts.get_log()
        print(log)















# def text_generate(mo) :
#     mo.create_thread()
#     msg = "大谷翔平の誕生日はいつですか"
#     mo.create_message(msg)
#     mo.run(True)


# def image_generate(mo) :
#     image_url = mo.image_generate("a white cat", size="256x256", model='dall-e-2', filename="downloaded_image.png")
#     print(image_url)




# def main():
#     mo = myopenai.myopenai()

#     audiofile = mo.mytexttospeech("テストをしています")
#     print(audiofile)
    
#     # mo.pdf_to_vector(r'C:\temp\Apps\Python\st_toranomaki\【御請求書】テスト.pdf')
#     # tanjun()
#     # embedding_ppt()
#     # embedding_txt()




# if __name__ == "__main__":
#     main()




