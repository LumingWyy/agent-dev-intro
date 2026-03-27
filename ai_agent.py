import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


def run():
    user_input = input("YOU: ").strip()

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=user_input,
    )

    print("AI:", response.text)


if __name__ == "__main__":
    run()
