"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step ④: ツールを持つ AI（記憶 ＋ ファイル操作）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

③ との違い:
  ③  会話して覚える
  ④  会話して覚える ＋ 現実世界を操作できる

使えるツール:
  download(url)          ウェブからファイル・画像をダウンロード
  zip(フォルダ名)         フォルダを ZIP に圧縮
  unzip(zipファイル名)    ZIP を解凍
  list()                 ダウンロードフォルダの一覧

試してみよう:
  「https://... の画像をダウンロードして」
  「downloads フォルダを圧縮して」
  「xxx.zip を解凍して」
  「今何が入ってる？」
"""

import os
import zipfile
import urllib.request
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

WORK_DIR = Path("downloads")
WORK_DIR.mkdir(exist_ok=True)


# ━━ ツールの実装 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def download(url: str) -> str:
    """ウェブからファイルをダウンロードする"""
    filename = url.split("/")[-1] or "downloaded_file"
    save_path = WORK_DIR / filename
    try:
        urllib.request.urlretrieve(url, save_path)
        size_kb = save_path.stat().st_size // 1024
        return f"保存完了: {save_path}（{size_kb} KB）"
    except Exception as e:
        return f"エラー: {e}"

def zip_folder(folder_name: str) -> str:
    """フォルダを ZIP に圧縮する"""
    target = WORK_DIR / folder_name
    if not target.exists():
        # downloads フォルダ自体を圧縮
        target = WORK_DIR
    zip_path = Path(f"{target.name}.zip")
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in target.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(target.parent))
        size_kb = zip_path.stat().st_size // 1024
        return f"圧縮完了: {zip_path}（{size_kb} KB）"
    except Exception as e:
        return f"エラー: {e}"

def unzip(zip_name: str) -> str:
    """ZIP ファイルを解凍する"""
    zip_path = Path(zip_name)
    if not zip_path.exists():
        zip_path = WORK_DIR / zip_name
    try:
        out_dir = WORK_DIR / zip_path.stem
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(out_dir)
        return f"解凍完了: {out_dir}/ に展開しました"
    except Exception as e:
        return f"エラー: {e}"

def list_files() -> str:
    """ダウンロードフォルダの一覧を返す"""
    files = list(WORK_DIR.iterdir())
    if not files:
        return "downloads フォルダは空です"
    lines = [f"  {'📁' if f.is_dir() else '📄'} {f.name}" for f in sorted(files)]
    return "downloads フォルダの中身:\n" + "\n".join(lines)


# ━━ Gemini にツールを定義として渡す ━━━━━━━━━━━━━━━━━━━

TOOLS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="download",
        description="URL からファイルや画像をダウンロードする",
        parameters=types.Schema(
            type="OBJECT",
            properties={"url": types.Schema(type="STRING", description="ダウンロード URL")},
            required=["url"],
        ),
    ),
    types.FunctionDeclaration(
        name="zip_folder",
        description="フォルダを ZIP ファイルに圧縮する",
        parameters=types.Schema(
            type="OBJECT",
            properties={"folder_name": types.Schema(type="STRING", description="圧縮するフォルダ名")},
            required=["folder_name"],
        ),
    ),
    types.FunctionDeclaration(
        name="unzip",
        description="ZIP ファイルを解凍する",
        parameters=types.Schema(
            type="OBJECT",
            properties={"zip_name": types.Schema(type="STRING", description="解凍する ZIP ファイル名")},
            required=["zip_name"],
        ),
    ),
    types.FunctionDeclaration(
        name="list_files",
        description="downloads フォルダにあるファイルの一覧を返す",
        parameters=types.Schema(type="OBJECT", properties={}),
    ),
])

TOOL_MAP = {
    "download":    lambda a: download(a["url"]),
    "zip_folder":  lambda a: zip_folder(a["folder_name"]),
    "unzip":       lambda a: unzip(a["zip_name"]),
    "list_files":  lambda a: list_files(),
}


# ━━ メインループ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run():
    chat = client.chats.create(
        model="gemini-3.1-flash-lite-preview",
        config=types.GenerateContentConfig(tools=[TOOLS]),
    )

    print("ファイル操作 Agent（記憶あり）（終了: Ctrl+C）")
    print("-" * 40)

    while True:
        user_input = input("YOU: ").strip()
        if not user_input:
            continue

        response = chat.send_message(user_input)

        # ── ツール呼び出しループ ──────────────────────────
        while response.function_calls:
            fc = response.function_calls[0]
            args = dict(fc.args)

            print(f"  [ツール] {fc.name}({args})")
            result = TOOL_MAP[fc.name](args)
            print(f"  [結果]  {result}")

            response = chat.send_message(
                types.Part.from_function_response(name=fc.name, response={"result": result})
            )

        print(f"AI: {response.text}\n")


if __name__ == "__main__":
    run()
