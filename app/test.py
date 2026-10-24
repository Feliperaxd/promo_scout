
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from app_name.integrations.mercado_libre.source import MercadoLibreSource
from app_name.integrations.mercado_libre.http import HttpClient

env = {
    "ML_APP_ID": "...",
    "ML_CLIENT_SECRET": "...",
}

client = HttpClient(
    tokens_path=Path("data/tokens/mercado_libre.json"),
    env=env,
)

source = MercadoLibreSource(client)

# 1. Busca o produto pelo código de barras
products = source.find_by_barcode("885911913676")

if not products:
    print("Nenhum produto encontrado para esse código de barras.")
    raise SystemExit

# 2. Consulta os detalhes do primeiro produto
product = products[0]
product_id = product["id"]

details = client.get(f"/products/{product_id}")

print("Produto:", details.get("name"))

# 3. Exibe a oferta vencedora, se existir
winner = details.get("buy_box_winner")

if winner:
    print("-" * 50)
    print("ID do anúncio:", winner.get("item_id"))
    print("Preço: R$", winner.get("price"))
    print("ID do vendedor:", winner.get("seller_id"))
else:
    print("O catálogo não retornou uma oferta vencedora.")


#API não tava retornando o q eu quero, gpt não ta ajudando
perguntar para o claude como eu poderia fazer aqui, e no source, usando o ports tbm e models