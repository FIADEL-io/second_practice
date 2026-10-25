# Визуализация графа зависимостей Cargo

Инструмент варианта 11 практического занятия по конфигурационному
управлению. Программа строит граф зависимостей пакета Rust (Cargo)
без готовых менеджеров пакетов и библиотек разбора зависимостей.

Сейчас реализован этап 1: минимальное CLI-приложение читает
настройки из YAML, проверяет каждый параметр и печатает их
в виде `ключ: значение`. Граф, порядок загрузки и рисунок
появятся на следующих этапах.

## Настройки

Источник настроек — один YAML-файл. Кодировка UTF-8.
Корень файла — набор параметров, лишние ключи запрещены.

| Параметр | Тип | Правило |
| --- | --- | --- |
| `package_name` | строка | Имя пакета Cargo: латиница, цифры, `-` и `_`, первый символ — буква или цифра, длина от 1 до 64 |
| `repository` | строка | При `test_repository_mode: false` — абсолютный URL со схемой `http` или `https`. При `true` — путь к существующему файлу |
| `test_repository_mode` | логический | Некавыченные `true` или `false`. Строка `"false"` не принимается |
| `graph_image_name` | строка | Имя одного файла с расширением `.png`, без каталога |
| `filter_substring` | строка | Подстрока, по которой позже отбрасываются пакеты. Пустая строка разрешена и означает, что фильтр не задан |

Относительный путь тестового репозитория считается от каталога
конфигурационного файла. В вывод попадает уже абсолютный путь:
так видно, что файл действительно найден.

Проверки идут в таком порядке: неизвестные ключи, имя пакета,
режим тестового репозитория, адрес репозитория, имя рисунка,
подстрока фильтра. Сообщается первая ошибка.

## Функции

- `load_config(path)` читает YAML и возвращает проверенный `AppConfig`
  либо выбрасывает `ConfigError`.
- `AppConfig.as_pairs()` возвращает параметры парами ключ-значение
  в порядке задания.
- `format_parameters(config)` собирает эти пары в текст.
- `main(argv)` разбирает аргумент `--config`, печатает параметры
  в stdout и возвращает код `0`. При ошибке конфигурации текст
  пишется в stderr, код возврата — `1`. Если не передан `--config`,
  argparse завершает процесс с кодом `2`.

## Сборка и тесты

Нужен Python 3.11 или новее.

```bash
python -m pip install -r requirements.txt
```

В зависимостях есть `types-PyYAML`: без него `mypy` считает
импорт PyYAML нетипизированным.

Запуск тестов из корня репозитория:

```bash
python -m unittest discover -s tests -v
```

На Windows то же самое выполняет `python`, путь к исходникам
скрипты запуска выставляют сами.

## Примеры

Успешный запуск, удалённый репозиторий:

```bash
run.bat --config config.yaml
```

```text
package_name: serde
repository: https://github.com/serde-rs/serde
test_repository_mode: false
graph_image_name: serde.png
filter_substring:
```

Тестовый репозиторий:

```bash
run.bat --config examples/test_repository.yaml
```

Ошибки по параметрам (на Linux и macOS — `sh run.sh`):

```bash
run.bat --config examples/errors/empty_package.yaml
run.bat --config examples/errors/bad_url.yaml
run.bat --config examples/errors/missing_test_file.yaml
run.bat --config examples/errors/bad_mode.yaml
run.bat --config examples/errors/bad_image.yaml
run.bat --config examples/errors/bad_filter.yaml
run.bat --config examples/errors/broken.yaml
run.bat --config examples/errors/unknown_key.yaml
```

Каждая команда печатает в stderr строку, которая начинается
с `ошибка конфигурации:` и называет неверный параметр.
Код возврата при этом равен 1.
