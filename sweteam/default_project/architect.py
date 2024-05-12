import ollama
import json

def main() -> None:
    system_ = "You are a senior software developer that is experienced in Python Machine Learning development."
    model_ = 'codegemma'
    context = my_current_code()
    options_ = {"temperature": 2.5, "top_p": 0.99, "top_k": 100}
    messages_ = [{'role': 'system',
                'content': system_},
                {'role': 'user',
                'content': 'Write a python code that use ollama to ask for software description and save it to a local file.'}
    ]

    chat_args = {
        "model": model_,
        "messages": [messages_],
        "stream": False,
        "options": options_,
        "format": "json",
    }
    response = chat(chat_args)
    try:
        content = response['message']['content']
        code = json.loads(response['message']['content'])
    except:
        print(f"Error parsing JSON. Check response: {response}")

    print(code)

def chat(chat_args: dict) -> dict:
    return ollama.chat(**chat_args)

def my_current_code() -> str:
    base_name = __file__
    with open(base_name, "r") as f:
        code = f.read()
    return code



if __name__ == "__main__":
    main()
