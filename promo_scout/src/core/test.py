from auth import Auth


def main() -> None:
    auth = Auth()
    code = auth.open_authorization_url()
    print(f"Código de autorização: {code}")


if __name__ == "__main__":
    main()
    