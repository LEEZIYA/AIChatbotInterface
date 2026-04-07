import ollama


# Install Ollama: ollama.ai
# Run a model: ollama run llama3
# uv add 'crewai[litellm]'
from crewai import LLM
def debug(message, prefix="DEBUG"):
    print(f"    \033[2m[{prefix}] {message}\033[0m")

def getOllamaLLM():
    # debug(query)
    # response = ollama.generate(model='gemma3:1b', prompt=query)
    llm = LLM(
    model="ollama/gemma3:1b",
    base_url="http://localhost:11434")
    return llm
    # debug(response["response"])
    # return response["response"]
