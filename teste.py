import requests

ACCESS_TOKEN = "APP_USR-3162136187047456-101815-a2b6759427fc0973633f31f062d15801-3457818443"

response = requests.get(
    "https://api.mercadolibre.com/users/me",
    headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
    timeout=30
)

print("Status:", response.status_code)

if response.ok:
    usuario = response.json()
    print("Vendedor:", usuario["nickname"])
    print("ID:", usuario["id"])
else:
    print(response.text)