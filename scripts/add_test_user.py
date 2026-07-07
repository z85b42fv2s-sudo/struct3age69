import pandas as pd
from datetime import datetime

USERS_FILE = '../users.csv'

def load_users():
    try:
        df = pd.read_csv(USERS_FILE)
        return df
    except Exception:
        df = pd.DataFrame(columns=["email","data_registrazione","abbonato"])
        df.to_csv(USERS_FILE, index=False)
        return df


def save_user(email, abbonato=False):
    df = load_users()
    email = email.strip().lower()
    now = datetime.now().strftime("%Y-%m-%d")
    if email in df["email"].astype(str).str.lower().values:
        df.loc[df["email"].astype(str).str.lower() == email, ["data_registrazione","abbonato"]] = [now, abbonato]
    else:
        df = pd.concat([df, pd.DataFrame({"email":[email],"data_registrazione":[now],"abbonato":[abbonato]})], ignore_index=True)
    df.to_csv(USERS_FILE, index=False)

if __name__ == '__main__':
    save_user('testuser@example.com')
    print('Saved testuser@example.com')
