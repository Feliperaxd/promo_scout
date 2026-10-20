import requests
import csv

ACCESS_TOKEN = "APP_USR-3162136187047456-101815-a2b6759427fc0973633f31f062d15801-3457818443"
USER_ID = "3457818443"

BASE_URL = "https://api.mercadolibre.com"
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}


def listar_ids():
    url = f"{BASE_URL}/users/{USER_ID}/items/search"

    ids = []
    offset = 0
    limite = 100

    while True:
        params = {
            "limit": limite,
            "offset": offset,
            "status": "active"
        }

        resposta = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=30
        )
        resposta.raise_for_status()

        dados = resposta.json()
        resultados = dados.get("results", [])

        ids.extend(resultados)

        total = dados.get("paging", {}).get("total", 0)

        print(f"Encontrados {len(ids)} de {total} anúncios")

        if not resultados or len(ids) >= total:
            break

        offset += len(resultados)

        # A API limita a paginação por offset em volumes grandes.
        if offset >= 1000:
            print("Limite de paginação atingido; há mais anúncios para buscar.")
            break

    return ids


def buscar_detalhes(item_id):
    url = f"{BASE_URL}/items/{item_id}"

    resposta = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )
    resposta.raise_for_status()

    return resposta.json()


def main():
    ids = listar_ids()
    anuncios = []

    for i, item_id in enumerate(ids, start=1):
        try:
            item = buscar_detalhes(item_id)

            anuncios.append({
                "id": item.get("id"),
                "titulo": item.get("title"),
                "preco": item.get("price"),
                "preco_original": item.get("original_price"),
                "estoque": item.get("available_quantity"),
                "status": item.get("status"),
                "link": item.get("permalink"),
                "tipo_anuncio": item.get("listing_type_id"),
                "categoria": item.get("category_id"),
            })

            print(f"[{i}/{len(ids)}] {item.get('title')}")

        except requests.RequestException as erro:
            print(f"Erro no anúncio {item_id}: {erro}")

    if anuncios:
        with open(
            "anuncios_mercadolivre.csv",
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as arquivo:
            campos = anuncios[0].keys()
            escritor = csv.DictWriter(arquivo, fieldnames=campos)
            escritor.writeheader()
            escritor.writerows(anuncios)

        print(f"\nConcluído! {len(anuncios)} anúncios salvos no CSV.")
    else:
        print("Nenhum anúncio foi obtido.")


if __name__ == "__main__":
    main()