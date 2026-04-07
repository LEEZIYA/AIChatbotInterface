import ollama

def debug(message, prefix="DEBUG"):
    print(f"    \033[2m[{prefix}] {message}\033[0m")

def ollamaModel(query) -> str:
    debug(query)
    response = ollama.generate(model='gemma3:1b', prompt=query)
    debug(response["response"])
    return response["response"]
