import myopenai
import json

if __name__ == '__main__' :

    model = "gpt-4o"
    # model = "gpt-4o-mini"
    # model = "gpt-4o-mini-2024-07-18"
    mo = myopenai.myopenai(model=model)
    giji = mo.giji_rocker(mo)

    #議事録データ読み込み & セット
    with open(r"議事録サンプル.txt", "r", encoding="utf-8") as f :
        txt = f.read()
    giji.set_mojiokoshi(txt, 2)



    #文字数が多すぎるので、いくつかのトピックに分割。(処理長い)
    giji.split_mojiokoshi()
    giji.save_topic_segments("l_topic_segments.txt")
    giji.load_topic_segments("l_topic_segments.txt")

    #トピックごとに要約実施
    giji.youyaku_minutes()
    giji.save_youyaku("l_youyaku.txt")
    giji.load_youyaku("l_youyaku.txt")

    #--- データ保存 -------------
    l_youyaku = giji.get_youyaku()
    l_minutes = giji.get_minutes()
    for m in l_youyaku:
        m["文字起こし"] = [
            {"id": t.split("|")[0], "time": t.split("|")[1], "talk": t.split("|")[2]}
            for t in l_minutes[m["開始行id"]:m["終了行id"] + 1]
        ]


    with open("議事録要約結果.txt", "w", encoding="utf-8") as f :
        json.dump(l_youyaku, f, ensure_ascii=False, indent=4)

