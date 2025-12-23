import regulation_handler
import os

normativa_dir = os.path.join(os.getcwd(), "normativa")
print(f"Checking directory: {normativa_dir}")

if not os.path.exists(normativa_dir):
    print("Directory not found!")
else:
    print("Loading documents...")
    try:
        docs = regulation_handler.load_regulation_text(normativa_dir)
        print(f"Loaded {len(docs)} pages.")
        
        if len(docs) > 0:
            query = "nodi non confinati"
            print(f"Testing query: '{query}'")
            relevant = regulation_handler.retrieve_relevant_context(query, docs)
            print(f"Found {len(relevant)} relevant pages.")
            for doc in relevant:
                print(f"- {doc['file']} (Pag. {doc['page']})")
        else:
            print("No pages loaded. Check PDF files.")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
