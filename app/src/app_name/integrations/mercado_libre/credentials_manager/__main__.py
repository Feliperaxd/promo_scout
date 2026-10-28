from .server import CredentialsSetup
 
 
def main() -> None:
    tokens = CredentialsSetup().run()
    print("Token generated and credentials saved.")
    print(f"Valid for {tokens.get('expires_in')} seconds.")
 
 
if __name__ == "__main__":
    main()
    