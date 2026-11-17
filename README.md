# ⌨️ Petruzia USB Studio

<p align="center">
  <strong>Настраивай свою клавиатуру. Без браузера. Без перепрошивки. Без лишних сложностей.</strong>
</p>

<p align="center">
  Windows-приложение для удобного переназначения клавиш PetruziaMini через USB с использованием официального протокола ZMK Studio.
</p>

<p align="center">
  ![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows)
  ![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
  ![ZMK](https://img.shields.io/badge/Firmware-ZMK-8A2BE2?style=for-the-badge)
  ![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
</p>

---

## ✨ О проекте

**Petruzia USB Studio** — небольшая утилита для владельцев механической клавиатуры PetruziaMini.

Приложение позволяет управлять раскладкой клавиатуры прямо с рабочего стола Windows. Больше не нужно открывать браузер или каждый раз перепрошивать устройство ради изменения расположения клавиш.

Подключи клавиатуру через USB, выбери нужную клавишу и назначь ей новую функцию. Изменения можно применить сразу и сохранить непосредственно в память клавиатуры.

## 🚀 Возможности

- **USB-подключение** — автоматический поиск и выбор последовательного порта.
- **Визуальная раскладка** — отображение клавиш с учётом реальных физических координат.
- **Быстрое переназначение** — выбери клавишу и назначь ей новую функцию в пару кликов.
- **Изменения в реальном времени** — применение настроек с проверкой обратным чтением.
- **Сохранение в память** — настройки остаются после отключения питания.
- **Отмена изменений** — возврат к последней сохранённой раскладке.
- **JSON Backup** — создание резервной копии раскладки.
- **Современный интерфейс** — тёмная тема, анимации и необычные визуальные элементы.

## 🖥️ Интерфейс

Приложение создано с упором на простоту: основные действия доступны непосредственно из главного окна.

> Здесь можно добавить скриншоты приложения.

## 📦 Установка и запуск

### Вариант 1. Готовый EXE

1. Открой раздел [Releases](../../releases).
2. Скачай `PetruziaUSBStudio.exe`.
3. Запусти приложение.
4. Подключи клавиатуру через USB.

### Вариант 2. Запуск из исходников

Требуется установленный Python 3.

```bash
git clone https://github.com/Nikilodius/petruzia-usb-studio.git
cd petruzia-usb-studio

py -3 -m pip install -r requirements.txt
run.bat
```

## 🔧 Сборка EXE

Приложение можно собрать самостоятельно с помощью PyInstaller:

```bash
py -3 -m pip install -r requirements.txt pyinstaller

py -3 -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --icon petruzia_usb_studio\icon.ico ^
    --add-data "petruzia_usb_studio\icon.ico;." ^
    --name PetruziaUSBStudio petruzia_usb_studio\app.py
```

Готовый EXE появится в папке `dist`.

Также доступна автоматическая сборка через **GitHub Actions**.

## ⚙️ Требования

- Windows 10 / 11.
- Клавиатура PetruziaMini.
- Контроллер nRF52840 / nice!nano.
- USB-подключение с поддержкой CDC ACM.
- Прошивка ZMK с включённым ZMK Studio.

Необходимые параметры прошивки:

```ini
CONFIG_ZMK_STUDIO=y
```

Также требуется сниппет `studio-rpc-usb-uart`.

## 🧪 Тестирование

Для запуска тестов протокола:

```bash
cd petruzia_usb_studio
py -3 test_protocol.py
```

## 🏗️ Технологии

| Технология | Назначение |
|---|---|
| Python | Основная логика |
| Tkinter | Графический интерфейс |
| ZMK Studio RPC | Обмен данными с клавиатурой |
| Protocol Buffers | Формат сообщений |
| PyInstaller | Сборка Windows EXE |
| GitHub Actions | Автоматическая сборка |

## ❤️ Благодарности и авторство

Особая благодарность автору оригинальной модели корпуса клавиатуры **PetruziaMini — 40% Handwired Mechanical Keyboard**.

- **Автор 3D-модели:** [becedbacad](https://makerworld.com/ru/models/476290-petruziamini-40-handwired-mechanical-keyboard#profileId-2938407)
- **Оригинальная модель:** [PetruziaMini на MakerWorld](https://makerworld.com/ru/models/476290-petruziamini-40-handwired-mechanical-keyboard#profileId-2938407)
- **Прошивка и протокол:** [ZMK Project](https://github.com/zmkfirmware/zmk)

Petruzia USB Studio — отдельный программный инструмент для работы с этой клавиатурой. Авторство оригинальной 3D-модели принадлежит её создателю.

## 📄 Лицензия

Проект распространяется под лицензией **MIT**.

Протокол ZMK Studio и соответствующие компоненты принадлежат проекту ZMK и распространяются на условиях их собственных лицензий.

---

<p align="center">
  <strong>Petruzia USB Studio</strong><br>
  Made for PetruziaMini ❤️
</p>
