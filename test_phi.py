from llama_cpp import Llama
import time

llm = Llama(
    model_path="/root/Sherpa/models/Phi-3.5-mini-instruct-Q4_K_M.gguf",
    n_ctx=4096,
    n_threads=2,
    verbose=False
)

print("Model loaded. Testing...\n")

start = time.time()
r = llm.create_chat_completion(
    messages=[
        {"role": "system", "content": "You are Sherpa, an AI Project Manager. Respond in structured format only."},
        {"role": "user", "content": """Pick the best assignee from this team for the ticket below.

Ticket: Payment webhook failing in production, Bug, High priority, FAB project

Team:
- Sakshi (ID 4): 32 tickets in FAB, Bug expert
- Sagar (ID 7): 22 tickets in FAB
- Esha (ID 9): 42 tickets in DocRX (different project)
- Rohit (ID 3): 30 tickets in TaskTracker (different project)

Respond ONLY in this format:
Recommended Assignee: <name>
Reason: <one line>
Alternative: <name and why>"""}
    ],
    max_tokens=200,
    temperature=0.1
)

print(f"Response ({time.time()-start:.1f}s):\n")
print(r["choices"][0]["message"]["content"])
