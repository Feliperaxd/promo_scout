from .server.credentials_setup import CredentialsSetup


def main() -> None:
    tokens = CredentialsSetup().run()
    print("Token gerado e credenciais salvas.")
    print(f"Válido por {tokens.get('expires_in')} segundos.")


if __name__ == "__main__":
    main()
    