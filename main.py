"""Точка входа приложения ValutaTrade Hub."""

from valutatrade_hub.cli.interface import run


def main() -> None:
    """Запускает CLI-интерфейс приложения."""
    run()


if __name__ == "__main__":
    main()
