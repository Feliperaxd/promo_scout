import requests
from urllib.parse import urlparse, parse_qs

APP_ID = "3162136187047456"
CLIENT_SECRET = "xsLEUklEkm7NKd2fxt6rOJqNTHf6tINe"
REDIRECT_URI = "https://www.google.com/"

url_recebida = input("Cole a URL completa do Google: ").strip()
codigo = parse_qs(urlparse(url_recebida).query).get("code", [None])[0]

if not codigo:
    print("Não encontrei o código na URL.")
    raise SystemExit

resposta = requests.post(
    "https://api.mercadolibre.com/oauth/token",
    data={
        "grant_type": "authorization_code",
        "client_id": APP_ID,
        "client_secret": CLIENT_SECRET,
        "code": codigo,
        "redirect_uri": REDIRECT_URI,
    },
    timeout=30,
)

print("Status:", resposta.status_code)

dados = resposta.json()

if resposta.ok:
    print("Token gerado com sucesso!")
    print("ID do vendedor:", dados.get("user_id"))
    print("Access token:", dados.get("access_token"))
    print("Refresh token recebido:", bool(dados.get("refresh_token")))
    print("Expira em:", dados.get("expires_in"), "segundos")
    print("Escopos:", dados.get("scope"))
else:
    print(dados)