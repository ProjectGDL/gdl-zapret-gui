# gdl-zapret-gui

GUI для обхода замедления YouTube и Discord на Linux. Оборачивает `nfqws` из [zapret](https://github.com/bol-van/zapret).

## Установка

```bash
pip install -r requirements.txt
```

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

## Как это работает

1. Загружаются `nfqws` и стратегии
2. Стратегия разбирается, выделяются параметры для каждого рабочего
3. Создаются правила файрвола (nftables или iptables)
4. Запускается `nfqws` с этими параметрами
5. Останавливается кнопкой "Стоп"

## Требования

- Linux с nftables или iptables
- Python 3.10+
- sudo или polkit для прав root
