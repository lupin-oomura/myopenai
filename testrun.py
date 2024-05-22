# pip install git+https://github.com/lupin-oomura/myfunc.git

from myfunc import myopenai
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

    audiofile = mo.mytexttospeech("テストをしています")
    print(audiofile)
    
    # mo.pdf_to_vector(r'C:\temp\Apps\Python\st_toranomaki\【御請求書】テスト.pdf')
    # tanjun()
    # embedding_ppt()
    # embedding_txt()




if __name__ == "__main__":
    main()




