# Petruzia USB Studio

Нативное Windows-приложение (Python/Tkinter) для живого переназначения клавиш
клавиатуры **PetruziaMini** (nRF52840 / nice!nano) по USB через официальный
протокол **ZMK Studio** — без браузера и без перепрошивки.

![Python](https://img.shields.io/badge/python-3.13-blue) ![Windows](https://img.shields.io/badge/platform-Windows-lightgrey)

## Возможности

- Подключение к клавиатуре по последовательному порту (CDC ACM), например `COM6`.
- Визуальная раскладка слоёв с настоящими координатами клавиш из physical layout.
- Простое переназначение в два клика: **клик по клавише → клик по новой в палитре**.
- Применение правки в реальном времени с проверкой обратным чтением.
- «Сохранить в память» — правки переживают выключение клавиатуры.
- «Отменить правки» — возврат к сохранённой раскладке.
- Резервная копия раскладки в JSON.
- Тёмный интерфейс в стиле Chatterino+ (chat.eblo.id), вирус-куб, живые анимации.

## Сборка EXE

### Вариант 1 — автоматом через GitHub Actions

1. Запусти **Actions → Build Windows EXE → Run workflow** (или запушь тег `v1.0`).
2. Забери готовый `PetruziaUSBStudio.exe` из артефактов задачи
   (а при пушe тега он автоматически прикрепляется к Release).

### Вариант 2 — локально

```bat
py -3 -m pip install -r requirements.txt pyinstaller
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --icon petruzia_usb_studio\icon.ico --add-data "petruzia_usb_studio\icon.ico;." ^
    --name PetruziaUSBStudio petruzia_usb_studio\app.py
```

Готовый файл: `dist\PetruziaUSBStudio.exe`.

## Запуск из исходников

```bat
py -3 -m pip install -r requirements.txt
run.bat
```

## Как пользоваться

1. Подключи клавиатуру по USB, нажми «Обновить» и выбери порт.
2. «Подключить» → «Прочитать клавиатуру».
3. Кликни по клавише на раскладке, потом кликни новую клавишу в палитре справа.
4. «Сохранить в память».

## Требования к прошивке

На клавиатуре должна стоять прошивка ZMK Studio:
см. репозиторий [petruzia-zmk](https://github.com/Nikilodius/petruzia-zmk)
(`CONFIG_ZMK_STUDIO=y`, сниппет `studio-rpc-usb-uart`).

## Структура

```
petruzia_usb_studio/
  app.py            — интерфейс и логика приложения
  protocol.py       — клиент ZMK Studio RPC (framing SoF 0xAB / ESC 0xAC / EoF 0xAD)
  *_pb2.py          — сгенерированные protobuf-модули (zmk official messages)
  proto/zmk/*.proto — оригинальные .proto файлы ZMK
  test_protocol.py  — тесты протокола (framing fixtures из официального репозитория)
  icon.ico          — иконка приложения
```

## Тесты

```bat
cd petruzia_usb_studio
py -3 test_protocol.py
```

## Лицензия

MIT. Протокол ZMK Studio — ZMK Project (MIT).
