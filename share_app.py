import os
import sys
import time
from pyngrok import ngrok
from dotenv import load_dotenv
import subprocess

# Load environment variables
load_dotenv()

def share_app():
    print("--- Structural 3age Sharing Tool ---")
    
    # Check for NGROK_AUTHTOKEN
    auth_token = os.getenv("NGROK_AUTHTOKEN")
    if not auth_token:
        print("\n[!] ATTENZIONE: Manca il token di ngrok.")
        print("1. Vai su https://dashboard.ngrok.com/signup e crea un account gratuito.")
        print("2. Copia il tuo Authtoken dalla dashboard.")
        print("3. Incolla il token qui sotto e premi Invio:")
        auth_token = input("> ").strip()
        if not auth_token:
            print("Token non valido. Uscita.")
            return
        
        # Save to .env for future use
        with open(".env", "a") as f:
            f.write(f"\nNGROK_AUTHTOKEN={auth_token}\n")
        print("Token salvato in .env!")

    # Set auth token
    ngrok.set_auth_token(auth_token)

    # Start Streamlit in the background
    print("\n[+] Avvio di Structural 3age in background...")
    streamlit_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Give it a moment to start
    time.sleep(3)

    # Open Tunnel
    try:
        print("[+] Creazione del tunnel pubblico...")
        public_url = ngrok.connect(8501).public_url
        print("\n" + "="*60)
        print(f"   LINK PUBBLICO: {public_url}")
        print("="*60)
        print("\nInvia questo link a chi vuoi far provare l'app.")
        print("Tieni questa finestra APERTA per mantenere il link attivo.")
        print("Premi CTRL+C per chiudere tutto.")
        
        # Keep alive
        streamlit_process.wait()
    except KeyboardInterrupt:
        print("\nChiusura in corso...")
        ngrok.kill()
        streamlit_process.terminate()
        print("Fatto.")
    except Exception as e:
        print(f"\nErrore: {e}")
        streamlit_process.terminate()

if __name__ == "__main__":
    share_app()
