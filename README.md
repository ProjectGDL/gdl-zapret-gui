# gdl-zapret-gui

GUI для обхода замедления YouTube и Discord на Linux. Оборачивает `nfqws` из [zapret](https://github.com/bol-van/zapret).

## Запуск

```bash
python3 main.py
```

Нужны права root. Первый запуск откроет мастер настройки.

## Команды

```bash
python3 main.py --status   # показать статус
python3 main.py --daemon   # запустить фоновый сервис
```

## Структура

Данные хранятся в `~/.local/share/gdl-zapret-gui/`:

- `config.json` — настройки
- `nfqws/` — бинарник
- `strategies/` — стратегии обхода
- `user-lists/` — свои списки доменов

## Требования

- Linux с nftables или iptables
- Python 3.14+
- polkit для прав root
