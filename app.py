from chef import chat

print("Personal Chef ready. Type your ingredients, or 'quit' to exit.\n")

while True:
    user_input = input("You: ").strip()
    if user_input.lower() in {"quit", "exit"}:
        break
    if not user_input:
        continue
    out = chat(user_input)
    print(f"\nChef: {out['answer']}\n[guard status: {out['status']}]\n")