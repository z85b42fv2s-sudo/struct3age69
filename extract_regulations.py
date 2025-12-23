import os
from pypdf import PdfReader

KEYWORDS = [
    "Livello di Conoscenza",
    "Fattore di Confidenza",
    "Stato Limite",
    "Vulnerabilità",
    "LC1", "LC2", "LC3",
    "FC",
    "FRP", "Incamiciatura", "Placcaggio", "Dissipazione", "Isolamento", "Betoncino"
]

def extract_info(pdf_path):
    print(f"--- Analyzing: {os.path.basename(pdf_path)} ---")
    try:
        reader = PdfReader(pdf_path)
        text_content = ""
        # Read first 20 pages or all if less
        num_pages = len(reader.pages)
        print(f"Total pages: {num_pages}")
        
        for i in range(min(num_pages, 30)):
            page = reader.pages[i]
            text = page.extract_text()
            if text:
                text_content += text + "\n"
        
        # Simple keyword search context
        found_something = False
        for keyword in KEYWORDS:
            if keyword.lower() in text_content.lower():
                print(f"Found keyword: '{keyword}'")
                # Find occurrences and print context
                lower_text = text_content.lower()
                start_idx = 0
                while True:
                    idx = lower_text.find(keyword.lower(), start_idx)
                    if idx == -1:
                        break
                    
                    # Print context (100 chars before and after)
                    context_start = max(0, idx - 100)
                    context_end = min(len(text_content), idx + 200)
                    print(f"  Context: ...{text_content[context_start:context_end].replace(chr(10), ' ')}...")
                    
                    start_idx = idx + 1
                    # Limit to first 3 occurrences per keyword to avoid spam
                    if start_idx > lower_text.find(keyword.lower(), 0) + 3: 
                         break
                found_something = True
        
        if not found_something:
            print("No specific keywords found in the first 30 pages.")

    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
    print("\n")

def main():
    normativa_dir = os.path.join(os.getcwd(), "normativa")
    if not os.path.exists(normativa_dir):
        print("Normativa directory not found.")
        return

    for filename in os.listdir(normativa_dir):
        if filename.lower().endswith(".pdf"):
            extract_info(os.path.join(normativa_dir, filename))

if __name__ == "__main__":
    main()
