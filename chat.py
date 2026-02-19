from llama_cpp import Llama

llm = Llama(
    model_path="/root/Sherpa/models/sherpa-q4_k_m.gguf",
    n_ctx=2048,
    n_threads=2,
    verbose=False
)

print("Sherpa Chat (type 'exit' to quit)\n")

while True:
    q = input("You: ")
    if q.lower() in ["exit", "quit"]:
        break
    r = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": "You are Sherpa, an AI Project Manager. /no_think"},
            {"role": "user", "content": q}
        ],
        max_tokens=300,
        temperature=0.7
    )
    print(f"\nSherpa: {r['choices'][0]['message']['content']}\n")
