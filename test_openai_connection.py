import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

api_key = os.getenv("OPENAI_API_KEY")
project_id = os.getenv("OPENAI_PROJECT")

print(f"API Key found: {'Yes' if api_key else 'No'}")
if api_key:
    print(f"API Key start: {api_key[:5]}...")

if not api_key or "inserisci-qui" in api_key:
    print("ERROR: Invalid or missing API Key in .env file.")
    print("Please update .env with your actual OpenAI API Key.")
else:
    try:
        print("Attempting to connect to OpenAI...")
        client = OpenAI(api_key=api_key, project=project_id)
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Hello, this is a connection test."}
            ],
            max_tokens=10
        )
        print("Connection SUCCESSFUL!")
        print("Response from OpenAI:", response.choices[0].message.content)
    except Exception as e:
        print("Connection FAILED.")
        print("Error:", str(e))
