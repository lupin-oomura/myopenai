# import google.generativeai as genai
# import os
# import mimetypes
# import time

# messages_gemini_history = []
# genai.configure(api_key=os.environ['GEMINI_API_KEY'])
# AUDIO_FILE_PATH = "speech_sample1.mp3"  # <--- 環境に合わせて変更してください
# model_name = "gemini-1.5-flash"
# client_gemini = genai.GenerativeModel(model_name=model_name)


# # --- システムプロンプト ---
# client_gemini = genai.GenerativeModel(
#     model_name=model_name,
#     system_instruction = "あなたはプロ野球の雑学を熟知しています"
# )
# chat = client_gemini.start_chat(history=[])

# # --- 1回目のターン: テキスト入力 ---
# user_text_1 = "大谷翔平の誕生日は？"
# response_1 = chat.send_message(user_text_1)
# print(f"Assistant: {response_1.text}")

# audio_file_upload = genai.upload_file(path=AUDIO_FILE_PATH, display_name="User Voice Input 2")

# print("ファイルの処理状態を確認中...")
# while audio_file_upload.state.name == "PROCESSING":
#     print("  処理中...")
#     time.sleep(2) # 2秒待機
#     # 最新の状態を取得
#     audio_file_upload = genai.get_file(audio_file_upload.name)
#     if audio_file_upload.state.name == "FAILED":
#         print(f"エラー: ファイル処理に失敗しました。 ({audio_file_upload.name})")
#         exit()

#     if audio_file_upload.state.name == "ACTIVE":
#         print("  ファイルはアクティブです。")
#     else:
#         print(f"エラー: ファイルが有効な状態ではありません ({audio_file_upload.state.name})。")
#         exit()


# print("モデルに音声ファイルを送信中...")
# response_2 = chat.send_message(audio_file_upload)
# print(f"Assistant: {response_2.text}")

# # --- (任意) 後片付け ---
# # アップロードしたファイルが不要になったら削除します
# genai.delete_file(audio_file_upload.name)
# print("\n会話を終了します。")










# import google.generativeai as genai
# import os
# import mimetypes # MIMEタイプを推測するために追加

# # --- 設定 ---
# try:
#     # 環境変数名を GEMINI_API_KEY に変更
#     genai.configure(api_key=os.environ['GEMINI_API_KEY'])
# except KeyError:
#     print("エラー: 環境変数 'GEMINI_API_KEY' が設定されていません。")
#     exit()
# except Exception as e:
#     print(f"APIキーの設定中にエラーが発生しました: {e}")
#     exit()

# # --- 音声ファイルのパス ---
# # ファイル名を speech_sample1.mp3 に変更
# AUDIO_FILE_PATH = "speech_sample1.mp3"  # <--- 環境に合わせて変更してください

# # 音声ファイルが存在するか確認
# if not os.path.exists(AUDIO_FILE_PATH):
#     print(f"エラー: 音声ファイルが見つかりません: {AUDIO_FILE_PATH}")
#     exit()

# # --- モデルの初期化 ---
# try:
#     model = genai.GenerativeModel(model_name="gemini-1.5-flash") # または "gemini-1.5-pro"
# except Exception as e:
#     print(f"モデルの初期化中にエラーが発生しました: {e}")
#     exit()

# # --- 会話セッションの開始 ---
# chat = model.start_chat(history=[])

# print("会話を開始します...")

# try:
#     # --- 1回目のターン: テキスト入力 ---
#     # 質問を「大谷翔平の誕生日は？」に変更
#     user_text_1 = "大谷翔平の誕生日は？"
#     print(f"\nUser (Text): {user_text_1}")

#     # メッセージを送信し、応答を取得
#     response_1 = chat.send_message(user_text_1)
#     print(f"Assistant: {response_1.text}")

#     # --- 2回目のターン: 音声ファイル入力 (直接埋め込み) ---
#     print(f"\nUser (Audio): 音声ファイル '{os.path.basename(AUDIO_FILE_PATH)}' を直接データとして送信します...")

#     # 1. MIMEタイプを推測
#     mime_type, _ = mimetypes.guess_type(AUDIO_FILE_PATH)
#     if not mime_type:
#         # MIMEタイプが推測できない場合のフォールバック (必要に応じて調整)
#         # MP3ファイルなので 'audio/mpeg' を指定
#         print(f"警告: {AUDIO_FILE_PATH} のMIMEタイプを推測できませんでした。'audio/mpeg' を使用します。")
#         mime_type = 'audio/mpeg' # ファイル形式が違う場合は 'audio/wav' などに変更
#     print(f"検出されたMIMEタイプ: {mime_type}")

#     # 2. 音声ファイルをバイナリデータとして読み込む
#     print("音声ファイルを読み込み中...")
#     try:
#         with open(AUDIO_FILE_PATH, 'rb') as f:
#             audio_bytes = f.read()
#         print(f"音声ファイル ({len(audio_bytes)} bytes) の読み込み完了。")
#     except FileNotFoundError:
#         print(f"エラー: 音声ファイルが見つかりません: {AUDIO_FILE_PATH}")
#         exit()
#     except Exception as e:
#         print(f"音声ファイルの読み込み中にエラーが発生しました: {e}")
#         exit()

#     # 3. 音声データを直接 prompt に含めて送信
#     #    {'mime_type': ..., 'data': ...} の形式で渡す
#     print("モデルに音声データを送信中...")
#     audio_blob = {'mime_type': mime_type, 'data': audio_bytes}
#     response_2 = chat.send_message(audio_blob) # 辞書形式で渡す

#     # 応答を表示
#     print(f"Assistant: {response_2.text}")

#     # --- 後片付けは不要 ---
#     # ファイルアップロードを使用していないため、削除処理は不要です

# except Exception as e:
#     print(f"\n会話の処理中にエラーが発生しました: {e}")
#     # ファイル削除処理は不要なので削除

# print("\n会話を終了します。")



import google.generativeai as genai
import os
import mimetypes
import time

messages_gemini_history = []
genai.configure(api_key=os.environ['GEMINI_API_KEY'])
AUDIO_FILE_PATH = "speech_sample1.mp3"  # <--- 環境に合わせて変更してください
model_name = "gemini-1.5-flash"
client_gemini = genai.GenerativeModel(model_name=model_name)


# --- システムプロンプト ---
client_gemini = genai.GenerativeModel(
    model_name=model_name,
    system_instruction = "あなたはプロ野球の雑学を熟知しています"
)

# --- 1回目のターン: テキスト入力 ---
user_text_1 = "大谷翔平の誕生日は？"
user_content_1 = {'role': 'user', 'parts': [{'text': user_text_1}]}
messages_gemini_history.append(user_content_1)
response = client_gemini.generate_content(
    model_name=model_name,
    contents=messages_gemini_history # 更新された全履歴を渡す
)
print(response.candidates[0].content.parts[0].text)

model_content_1 = {'role': 'model', 'parts': [{'text': "大谷翔平の誕生日は、**1994年7月5日**です。"}]}
messages_gemini_history.append(model_content_1)

mime_type, _ = mimetypes.guess_type("aaa.mp3")
with open(AUDIO_FILE_PATH, 'rb') as f:
    audio_bytes = f.read()
audio_part = {'inline_data': {'mime_type': mime_type, 'data': audio_bytes}}

user_content_2 = {'role': 'user', 'parts': [audio_part]} # 音声パートをリストに入れる
messages_gemini_history.append(user_content_2) # self.messages_gemini.append(...) に相当

response_2 = client_gemini.generate_content(
    contents=messages_gemini_history # 更新された全履歴を渡す
)
assistant_text_2 = response_2.candidates[0].content.parts[0].text
print(f"Assistant: {assistant_text_2}")
