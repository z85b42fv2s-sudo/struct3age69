import os
import stripe
import pandas as pd
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Carica variabili ambiente
load_dotenv()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
USERS_FILE = "users.csv"

stripe.api_key = STRIPE_SECRET_KEY

app = Flask(__name__)

@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('stripe-signature')
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    # Gestisci evento pagamento riuscito
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email")
        if customer_email:
            try:
                df = pd.read_csv(USERS_FILE)
                if customer_email in df["email"].values:
                    df.loc[df["email"] == customer_email, "abbonato"] = True
                else:
                    # Se non esiste, aggiungi nuovo utente abbonato
                    df = pd.concat([
                        df,
                        pd.DataFrame({"email": [customer_email], "data_registrazione": [pd.Timestamp.now().strftime("%Y-%m-%d")], "abbonato": [True]})
                    ], ignore_index=True)
                df.to_csv(USERS_FILE, index=False)
            except Exception as e:
                return jsonify({'error': f'Errore aggiornamento utenti: {e}'}), 500
    return jsonify({'status': 'success'})

if __name__ == "__main__":
    app.run(port=4242)
