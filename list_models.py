from dotenv import load_dotenv
from groq import Groq

load_dotenv()
for m in Groq().models.list().data:
    print(m.id)