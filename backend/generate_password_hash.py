"""
generate_password_hash.py
One-off helper: run this once to generate the bcrypt hash you paste
into .env — ADMIN_PASSWORD_HASH (counter operator login),
MASTER_PASSWORD_HASH (master console login), SCANNER_PASSWORD_HASH
(entrance scanner login), or ADMIN_MARTDAYS_PASSWORD_HASH (Mart Days
badge desk operator login). Never put the plaintext password in
.env — only the hash.

Usage:
    ./venv/bin/python generate_password_hash.py
"""

import getpass

from utils.auth import hash_password


def main():
    print("Which login is this password for?")
    print("  1) Admin / counter operator      -> ADMIN_PASSWORD_HASH")
    print("  2) Master console                -> MASTER_PASSWORD_HASH")
    print("  3) Entrance scanner               -> SCANNER_PASSWORD_HASH")
    print("  4) Mart Days badge desk operator -> ADMIN_MARTDAYS_PASSWORD_HASH")
    choice = input("Enter 1, 2, 3, or 4: ").strip()

    if choice == "2":
        env_key = "MASTER_PASSWORD_HASH"
        prompt_label = "master"
    elif choice == "3":
        env_key = "SCANNER_PASSWORD_HASH"
        prompt_label = "scanner"
    elif choice == "4":
        env_key = "ADMIN_MARTDAYS_PASSWORD_HASH"
        prompt_label = "Mart Days badge desk"
    else:
        env_key = "ADMIN_PASSWORD_HASH"
        prompt_label = "admin"

    password = getpass.getpass(f"Enter the {prompt_label} password to hash: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords didn't match — try again.")
        return

    if not password:
        print("Password can't be empty.")
        return

    print("\nAdd this line to your .env file:\n")
    print(f"{env_key}={hash_password(password)}")


if __name__ == "__main__":
    main()