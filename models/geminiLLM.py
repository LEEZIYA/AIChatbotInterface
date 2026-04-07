
import os
from dotenv import load_dotenv
from crewai import LLM

# Load environment variables from .env file
load_dotenv()



# Install Ollama: ollama.ai
# Run a model: ollama run llama3
# uv add 'crewai[litellm]'
from crewai import LLM
def debug(message, prefix="DEBUG"):
    print(f"    \033[2m[{prefix}] {message}\033[0m")

def getGeminiLLM():
    # debug(query)
    # response = ollama.generate(model='gemma3:1b', prompt=query)
# Initialize LLM with API key from environment
    llm = LLM(
    model="gemini/gemini-2.0-flash",
    api_key=os.getenv("GEMINI_API_KEY"),  # Reads from .env file
    temperature=0.7
    )
    print("✓ gemini LLM initialized")
    return llm
    # debug(response["response"])
    # return response["response"]

if __name__ == "__main__":
    getGeminiLLM()
