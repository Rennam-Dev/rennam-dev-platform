from getpass import getpass

from app.core.security import hash_password


def main() -> None:
    password = getpass("Nova senha do painel: ")
    confirmation = getpass("Repita a senha: ")
    if not password or password != confirmation:
        raise SystemExit("As senhas estão vazias ou não coincidem.")
    print(hash_password(password))


if __name__ == "__main__":
    main()
