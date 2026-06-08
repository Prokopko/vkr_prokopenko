# Smart Contract Audit Studio

Теперь оболочка уже умеет:
- использовать загруженные `etherscan_client.py` и `nocodb_client.py`
- запускать анализ через 3 режима: `stub`, внешний `CLI`, или Python executor
- сохранять результат в NocoDB через текущий формат `result + trust_flag`
- показывать findings и сводку прямо в UI

## Что подключено
Твои файлы скопированы в папку `connectors/`:
- `connectors/nocodb_client.py`
- `connectors/etherscan_client.py`

## Как запустить
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

## Варианты подключения реального сканера

### 1. Через Python-функцию
Если у тебя появится модуль, например `scanner_entry.py` с функцией `run_scan(...)`, укажи в `.env`:
```bash
SCANNER_EXECUTOR_MODULE=scanner_entry
SCANNER_EXECUTOR_FUNCTION=run_scan
```

Ожидаемый формат функции:
```python
def run_scan(address: str, contract_name: str, chain: str, config: dict) -> dict:
    ...
```

### 2. Через внешнюю CLI-команду
Если основной пайплайн запускается из консоли, добавь в `.env`:
```bash
SCANNER_CLI_COMMAND=python your_script.py --address {address}
```

Тогда UI выполнит эту команду и покажет stdout/stderr в findings.

## Ограничение сейчас
Файл `main.py.BAK` только вызывает `cli.executors.execute()`, но сам пакет `cli` не загружен. Поэтому напрямую подключить реальный scanner pipeline пока нельзя: для этого нужен либо сам модуль `cli`, либо точка входа в виде функции/команды.
