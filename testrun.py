# pip install git+https://github.com/lupin-oomura/myfunc.git

from myfunc import myopenai
from myfunc import mywhisper
from dotenv import load_dotenv
load_dotenv()



def text_generate(mo) :
    mo.create_thread()
    msg = "大谷翔平の誕生日はいつですか"
    mo.create_message(msg)
    mo.run(True)


def image_generate(mo) :
    image_url = mo.image_generate("a white cat", size="256x256", model='dall-e-2', filename="downloaded_image.png")
    print(image_url)




def main():
    mo = myopenai.myopenai()

    #文章生成
    # text_generate(mo)
    #画像生成
    # image_generate(mo)

    # #リアルタイム文字起こし
    # transcriber = mywhisper.mywhisper(mo, energy=300, pause=0.1, dynamic_energy=False, save_file=False)
    # result_queue = transcriber.start_transcribing()

    # print("Recording... Press Ctrl+C to stop.")
    # try:
    #     while not transcriber.stop_event.is_set():
    #         say = result_queue.get()
    #         print(f"You said: {say}")
    #         if "処理を終了してください" in say:
    #             transcriber.stop_event.set()
    #             transcriber.stop_listening(wait_for_stop=True)
    #             break
    # except KeyboardInterrupt:
    #     transcriber.stop_event.set()
    #     transcriber.stop_listening(wait_for_stop=True)
    #     print("Stopped by user")

    audiofile = mo.mytexttospeech("テストをしています")
    print(audiofile)
    
    # mo.pdf_to_vector(r'C:\temp\Apps\Python\st_toranomaki\【御請求書】テスト.pdf')
    # tanjun()
    # embedding_ppt()
    # embedding_txt()




if __name__ == "__main__":
    main()




