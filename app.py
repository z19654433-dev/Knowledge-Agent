from chatbot.chatbot import chat


while True:

    user_input = input("你: ")

    if user_input == "exit":
        print("AI: 再见！")
        break

    answer = chat(user_input)

    print("AI:", answer)