import regulation_handler
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)
api_key = os.getenv("OPENAI_API_KEY")
project_id = os.getenv("OPENAI_PROJECT")

if not api_key:
    print("Error: API Key not found.")
    exit()

normativa_dir = os.path.join(os.getcwd(), "normativa")
query = "qual è il passo massimo delle staffe fuori zona critica nelle ultime NTC"

print(f"Query: '{query}'")
print("Loading documents...")

try:
    docs = regulation_handler.load_regulation_text(normativa_dir)
    if not docs:
        print("No documents found.")
    else:
        print(f"Loaded {len(docs)} pages/documents.")
        
        # Retrieve context
        relevant_docs = regulation_handler.retrieve_relevant_context(query, docs)
        print(f"Found {len(relevant_docs)} relevant context chunks.")
        
        with open("debug_context.txt", "w", encoding="utf-8") as f:
            for doc in relevant_docs:
                f.write(f"File: {doc['file']} (Pag. {doc['page']})\n")
                f.write(f"Text snippet: {doc['text'][:200]}...\n\n")
        
        # Ask AI
        print("Asking AI...")
        response = regulation_handler.ask_regulation_assistant(query, relevant_docs, api_key, project_id)
        
        print("\n" + "="*50)
        print("AI RESPONSE:")
        print(response)
        
        with open("response.txt", "w", encoding="utf-8") as f:
            f.write(response)

except Exception as e:
    print(f"Error: {e}")
