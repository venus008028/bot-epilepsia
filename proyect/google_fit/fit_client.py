from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import datetime
import os

# Alcances que se usan para acceder a Google Fit
SCOPES = ['https://www.googleapis.com/auth/fitness.heart_rate.read', 'https://www.googleapis.com/auth/fitness.activity.read']

def get_google_fit_service():
    creds = None
    # Si ya existe el archivo de credenciales, lo usamos
    if os.path.exists("google_fit/token.json"):
        creds = Credentials.from_authorized_user_file("google_fit/token.json", SCOPES)
    else:
        # Si no, pedimos autorización y guardamos el archivo token.json
        CLIENT_SECRET_FILE = os.path.join(os.path.dirname(__file__), 'client_secret.json')
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        os.makedirs("google_fit", exist_ok=True)
        with open("google_fit/token.json", "w") as token:
            token.write(creds.to_json())
    return build('fitness', 'v1', credentials=creds)

# Función para obtener el ritmo cardíaco de la última hora
def get_heart_rate_last_hour(service):
    now = datetime.datetime.utcnow()
    five_minutes_ago = now - datetime.timedelta(minutes=5)

    dataset = f"{int(five_minutes_ago.timestamp()*1e9)}-{int(now.timestamp()*1e9)}"
    data_source = "derived:com.google.heart_rate.bpm:com.google.android.gms:merge_heart_rate_bpm"

    response = service.users().dataSources().datasets().get(userId="me", dataSourceId=data_source, datasetId=dataset).execute()

    points = response.get("point", [])
    if points:
        last_point = max(points, key=lambda p: int(p['startTimeNanos']))
        for value in last_point.get("value", []):
            return value.get("fpVal")
    return None


