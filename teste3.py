
import csv
import os
import time
import requests

from dotenv import load_dotenv
from tabulate import tabulate

load_dotenv()

TOKEN = "APP_USR-3162136187047456-101816-5cfc7e413a561e1d2fdbed1ae2720b76-3457818443"
USER_ID = USER_ID = "3457818443"

BASE_URL = "https://api.mercadolibre.com"
ARQUIVO_CSV = "relatorio_promocoes.csv"

if not TOKEN or not USER_ID:
    raise RuntimeError(
        "Configure ML_ACCESS_TOKEN e ML_USER_ID no arquivo .env"
    )

SESSION = requests.Session()
SESSION.headers.update({
    "Authorization": f"Bearer {TOKEN}"
})


def get_api(path, params=None):
    """Consulta a API com tratamento simples de erros."""
    url = f"{BASE_URL}{path}"

    for tentativa in range(3):
        resposta = SESSION.get(
            url, params=params, timeout=30
        )

        if resposta.status_code == 429:
            time.sleep(2 * (tentativa + 1))
            continue

        resposta.raise_for_status()
        return resposta.json()

    raise RuntimeError("Limite de requisições atingido.")


def listar_anuncios_ativos():
    """Busca anúncios ativos, inclusive acima de 1.000 itens."""
    path = f"/users/{USER_ID}/items/search"

    pagina = get_api(path, {"status": "active", "limit": 100})
    ids = list(pagina.get("results", []))

    total = pagina.get("paging", {}).get("total", 0)
    print(f"Anúncios encontrados: {len(ids)} de {total}")

    # Para contas grandes, usa scan, conforme a API.
    if total > 1000:
        pagina = get_api(path, {
            "status": "active",
            "search_type": "scan"
        })

        ids = list(pagina.get("results", []))
        scroll_id = pagina.get("scroll_id")

        while scroll_id:
            pagina = get_api(path, {
                "status": "active",
                "search_type": "scan",
                "scroll_id": scroll_id
            })

            novos = pagina.get("results", [])
            if not novos:
                break

            ids.extend(novos)
            scroll_id = pagina.get("scroll_id")

            print(f"Anúncios coletados: {len(ids)}")
            time.sleep(0.15)

    return list(dict.fromkeys(ids))


def dinheiro(valor):
    """Converte valores para reais."""
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def normalizar_preco_promocao(valor, original_raw, preco_atual):
    """
    Algumas respostas de promoções podem usar valores em
    centavos. Compara o preço original retornado com o preço
    do anúncio para detectar essa diferença de escala.
    """
    valor = dinheiro(valor)
    original_raw = dinheiro(original_raw)
    preco_atual = dinheiro(preco_atual)

    if valor is None:
        return None

    if (
        original_raw and preco_atual
        and original_raw / preco_atual > 20
    ):
        return valor / 100

    return valor


def consultar_detalhes(item_id):
    return get_api(f"/items/{item_id}")


def consultar_promocoes(item_id):
    url = f"{BASE_URL}/seller-promotions/items/{item_id}"

    resposta = SESSION.get(
        url,
        params={"app_version": "v2"},
        timeout=30
    )

    if resposta.status_code == 403:
        print(f"\n{'=' * 60}")
        print(f"ACESSO NEGADO — Anúncio: {item_id}")
        print(f"Status HTTP: {resposta.status_code}")
        print("Resposta da API:")
        print(resposta.text[:1500])
        print(f"{'=' * 60}\n")
        return []

    if resposta.status_code == 401:
        print(f"\nToken inválido ou expirado: {item_id}")
        print(resposta.text[:1500])
        return []

    resposta.raise_for_status()
    return resposta.json()


def consultar_tarifa(item, preco):
    """
    Consulta o custo de venda para o preço informado.
    O resultado não inclui necessariamente o frete pago
    pelo vendedor nem todas as compensações promocionais.
    """
    params = {
        "price": round(preco, 2),
        "currency_id": item.get("currency_id", "BRL"),
        "category_id": item.get("category_id"),
        "listing_type_id": item.get("listing_type_id"),
    }

    shipping = item.get("shipping") or {}

    if shipping.get("mode"):
        params["shipping_mode"] = shipping["mode"]

    if shipping.get("logistic_type"):
        params["logistic_type"] = shipping["logistic_type"]

    params = {
        chave: valor
        for chave, valor in params.items()
        if valor is not None
    }

    try:
        dados = get_api(
            "/sites/MLB/listing_prices",
            params
        )

        # A resposta normalmente é uma lista de tarifas.
        if isinstance(dados, list) and dados:
            tarifa = dados[0]
            return dinheiro(tarifa.get("sale_fee_amount"))

        if isinstance(dados, dict):
            return dinheiro(dados.get("sale_fee_amount"))

    except (requests.RequestException, ValueError) as erro:
        print(f"  Não foi possível calcular a tarifa: {erro}")

    return None


def analisar_item(item_id):
    item = consultar_detalhes(item_id)

    preco_atual = dinheiro(item.get("price"))
    titulo = item.get("title", "")
    link = item.get("permalink", "")

    if preco_atual is None:
        return []

    try:
        promocoes = consultar_promocoes(item_id)
    except requests.RequestException as erro:
        print(f"Erro nas promoções de {item_id}: {erro}")
        promocoes = []

    linhas = []

    if not isinstance(promocoes, list):
        promocoes = []

    elegiveis = [
        p for p in promocoes
        if p.get("status") == "candidate"
    ]

    if not elegiveis:
        linhas.append({
            "produto": titulo,
            "item_id": item_id,
            "preco_atual": preco_atual,
            "promocao": "Nenhuma elegível",
            "desconto_maximo_pct": None,
            "preco_minimo_promocao": None,
            "preco_sugerido": None,
            "desconto_sugerido_pct": None,
            "tarifa_estimada": None,
            "liquido_estimado_sem_frete": None,
            "status_calculo": "Sem promoção elegível",
            "link": link,
        })
        return linhas

    for promo in elegiveis:
        original_raw = promo.get("original_price")

        preco_minimo = normalizar_preco_promocao(
            promo.get("min_discounted_price"),
            original_raw,
            preco_atual
        )

        preco_sugerido = normalizar_preco_promocao(
            promo.get("suggested_discounted_price"),
            original_raw,
            preco_atual
        )

        # Se não existir sugestão, usa o menor preço permitido
        # apenas como referência alternativa.
        preco_calculo = preco_sugerido or preco_minimo

        desconto_maximo = (
            (1 - preco_minimo / preco_atual) * 100
            if preco_minimo is not None and preco_atual
            else None
        )

        desconto_sugerido = (
            (1 - preco_sugerido / preco_atual) * 100
            if preco_sugerido is not None and preco_atual
            else None
        )

        tarifa = None
        liquido = None
        status_calculo = "Preço promocional indisponível"

        if preco_calculo is not None:
            tarifa = consultar_tarifa(item, preco_calculo)

            if tarifa is not None:
                liquido = preco_calculo - tarifa
                status_calculo = (
                    "Estimativa sem frete e ajustes promocionais"
                )
            else:
                status_calculo = "Tarifa indisponível"

        linhas.append({
            "produto": titulo,
            "item_id": item_id,
            "preco_atual": preco_atual,
            "promocao": promo.get("type", "Promoção"),
            "desconto_maximo_pct": desconto_maximo,
            "preco_minimo_promocao": preco_minimo,
            "preco_sugerido": preco_sugerido,
            "desconto_sugerido_pct": desconto_sugerido,
            "tarifa_estimada": tarifa,
            "liquido_estimado_sem_frete": liquido,
            "status_calculo": status_calculo,
            "link": link,
        })

    return linhas


def formatar_reais(valor):
    if valor is None:
        return "N/D"

    return f"R$ {valor:,.2f}".replace(
        ",", "X"
    ).replace(".", ",").replace("X", ".")


def main():
    ids = listar_anuncios_ativos()
    relatorio = []

    for indice, item_id in enumerate(ids, 1):
        try:
            linhas = analisar_item(item_id)
            relatorio.extend(linhas)

            print(
                f"[{indice}/{len(ids)}] "
                f"{linhas[0]['produto'] if linhas else item_id}"
            )

        except requests.RequestException as erro:
            print(f"Erro em {item_id}: {erro}")

        time.sleep(0.15)

    if not relatorio:
        print("Nenhum dado encontrado.")
        return

    campos = list(relatorio[0].keys())

    with open(
        ARQUIVO_CSV,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as arquivo:
        escritor = csv.DictWriter(
            arquivo, fieldnames=campos
        )
        escritor.writeheader()
        escritor.writerows(relatorio)

    tabela = []

    for linha in relatorio:
        tabela.append([
            linha["produto"][:35],
            formatar_reais(linha["preco_atual"]),
            linha["promocao"],
            (
                f'{linha["desconto_maximo_pct"]:.1f}%'
                if linha["desconto_maximo_pct"] is not None
                else "N/D"
            ),
            formatar_reais(linha["preco_minimo_promocao"]),
            formatar_reais(linha["preco_sugerido"]),
            formatar_reais(linha["liquido_estimado_sem_frete"]),
        ])

    print("\nRELATÓRIO DE PROMOÇÕES")
    print(tabulate(
        tabela,
        headers=[
            "Produto", "Preço atual", "Promoção",
            "Desc. máximo", "Preço mínimo",
            "Preço sugerido", "Líquido estimado*"
        ],
        tablefmt="rounded_grid"
    ))

    print(f"\nArquivo salvo: {ARQUIVO_CSV}")
    print("* Líquido estimado antes do frete e ajustes da campanha.")


if __name__ == "__main__":
    main()
