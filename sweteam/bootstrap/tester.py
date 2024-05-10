import ollama
import json

def main() -> None:
    system_ = ("You are a senior product manager that is experienced in Python Machine Learning projects,"
    "you are great at prompt engineering, discuss software requirements with the users via user interface,"
    "discuss software architecture with the architect, discuss software testing with software developers,"
    "and discuss software test cases with the tester. The key of your job is to ask user for their requirements"
    "ask for clarification questions, then discuss with architect, developer and tester to come up with a "
    "software specification description so that the developer can implement it correctly.")
    model_ = 'codegemma'
    context = my_current_code()
    options_ = {"temperature": 2.5, "top_p": 0.99, "top_k": 100}
    message_ = "Write a python code that use ollama to ask for software description and save it to a local file."
    messages_ = [{'role': 'system',
                'content': system_},
                {'role': 'user',
                'content': message_}
    ]

    chat_args = {
        "model": model_,
        "messages": messages_,
        "stream": False,
        "options": options_,
        "format": "json",
    }

    generate_args = {
        "model": model_,
        "system": system_,
        "context": context,
        "prompt": messages_,
        "stream": False,
        "options": options_,
        "format": "json",
    }
    response = chat(chat_args)
    try:
        content = response['message']['content']
        code = json.loads(content)
    except:
        print(f"Error parsing JSON. Check response: {response}")

    print(code)

def chat(chat_args: dict) -> dict:
    return ollama.chat(**chat_args)

def generate(generate_args: dict) -> dict:
    return ollama.generate(**generate_args)


def my_current_code() -> str:
    base_name = __file__
    with open(base_name, "r") as f:
        code = f.read()
    return code


if __name__ == "__main__":
    main()
