"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step ②: 無限に LLM と会話する（記憶なし）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

① との違い:
  ①  1回だけ質問して終わる
  ②  何度でも質問できる（ループ）

③ との違い:
  ②  毎回独立した呼び出し（前の話を覚えない）
  ③  前の会話を覚えている

試してみよう:
  「私の名前は田中です」→「私の名前は？」
  → 覚えていない！（③ と比べると違いが分かる）
"""

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


def run():
    print("記憶なし AI（終了: Ctrl+C）")
    print("-" * 40)

    while True:
        user_input = input("YOU: ").strip()
        if not user_input:
            continue

        # 毎回独立した呼び出し（履歴を渡さない）
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=user_input,
        )

        print("AI:", response.text)
        print()


if __name__ == "__main__":
    run()
