from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
    base_url=os.getenv(
        "NVIDIA_BASE_URL",
        "https://integrate.api.nvidia.com/v1"
    ),
    api_key=os.getenv("NVIDIA_API_KEY"),
)

response = client.chat.completions.create(
    model="z-ai/glm-5.2",
    messages=[
        {
            "role": "user",
            "content": 'Devuelve únicamente este JSON: {"status":"ok"}'
        }
    ],
    temperature=0.1,
    top_p=1,
    max_tokens=100,
    stream=False,
)

print(response.choices[0].message.content)