"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step ③: 記憶を持つ AI（仕組みを可視化）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

② との違い:
  ②  毎回 user_input だけを送る
  ③  毎回「過去の会話全部 ＋ 今の質問」を送る

なぜ覚えられるか？
  LLM 自体は記憶を持たない。
  → 過去の会話を毎回 input に詰めて送るから覚えているように見える

  1ターン目: [Q1]              → 送信
  2ターン目: [Q1, A1, Q2]      → 送信
  3ターン目: [Q1, A1, Q2, A2, Q3] → 送信
  ...どんどん長くなる
"""

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


def run():
    # ここに過去の会話をすべて蓄積する
    history = []

    print("記憶を持つ AI（終了: Ctrl+C）")
    print("-" * 40)

    while True:
        user_input = input("YOU: ").strip()
        if not user_input:
            continue

        # ① 今の質問を履歴に追加
        history.append({"role": "user", "content": user_input})

        # ② LLM に「履歴全部 ＋ 今の質問」を送る（これが記憶の正体）
        print(f"\n  ── LLM に送っている内容（{len(history)} 件） ──")
        for msg in history:
            role = "YOU" if msg["role"] == "user" else " AI"
            print(f"  {role}: {msg['content']}")
        print(f"  ──────────────────────────────────\n")

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=[
                types.Content(role=m["role"], parts=[types.Part(text=m["content"])])
                for m in history
            ],
        )

        reply = response.text

        # ③ AI の返答も履歴に追加（次回送信時に含まれる）
        history.append({"role": "model", "content": reply})

        print(f"AI: {reply}\n")


if __name__ == "__main__":
    run()
