"""Remet la base à zéro avec les données simulées, avant une répétition (D35).

Usage : python -m pharmasur.reset
"""

from .config import charger_config
from .db import remettre_a_zero


def main() -> None:
    config = charger_config()
    remettre_a_zero(config.db_path, config.numero_pharmacie_baobab)
    print(f"Base remise à zéro avec les données simulées : {config.db_path}")


if __name__ == "__main__":
    main()
