import regulation_handler
import os

normativa_dir = os.path.join(os.getcwd(), "normativa")
query = "qual è il passo massimo delle staffe fuori zona critica nelle ultime NTC"

print(f"Testing retrieval for query: '{query}'")

# Load docs
docs = regulation_handler.load_regulation_text(normativa_dir)
print(f"Loaded {len(docs)} pages.")

# Retrieve context
relevant = regulation_handler.retrieve_relevant_context(query, docs, top_k=10)
print(f"Retrieved {len(relevant)} chunks.")

found_page_89 = False
for doc in relevant:
    print(f"- {doc['file']} (Pag. {doc['page']}) - Score: {doc.get('score', 'N/A')}")
    if "NTC-2018" in doc['file'] and doc['page'] == 89:
        found_page_89 = True
        print("  *** FOUND TARGET PAGE 89 ***")

with open("debug_result.txt", "w", encoding="utf-8") as f:
    if found_page_89:
        f.write("SUCCESS: Target page was retrieved.\n")
    else:
        f.write("FAILURE: Target page 89 NOT found in top 10.\n")
    
    for doc in relevant:
        f.write(f"- {doc['file']} (Pag. {doc['page']}) - Score: {doc.get('score', 'N/A')}\n")
