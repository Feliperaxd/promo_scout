import requests
import urllib.parse
import webbrowser

APP_ID = "3162136187047456"
REDIRECT_URI = "https://www.google.com/"

url = "https://auth.mercadolivre.com.br/authorization?" + urllib.parse.urlencode({
    "response_type": "code",
    "client_id": APP_ID,
    "redirect_uri": REDIRECT_URI,
})

print("Abrindo o Mercado Livre para autorizar...")
webbrowser.open(url)

print("\nDepois de autorizar:")
print("1. O navegador vai abrir o Google.")
print("2. Copie a URL que aparece na barra de endereço.")
print("3. Procure o valor depois de ?code=")
print("4. Use esse código no próximo script.")