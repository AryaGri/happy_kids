"""
Единое десктопное приложение для всех ролей.
Экран настроек (адрес сервера) → веб-интерфейс (логин).
После входа пользователь попадает на свою панель (админ / врач / родитель / ребёнок) — 1:1 с вебом.
"""
import json
import os
import sys
from pathlib import Path

DEFAULT_BASE_URL = "https://happy-kids-iu6.ru"


def _get_base_dir() -> Path:
    """Папка для конфига: рядом с exe при сборке, иначе — папка скрипта."""
    if getattr(sys, "frozen", False):
        return Path(os.path.dirname(sys.executable))
    return Path(__file__).resolve().parent


CONFIG_PATH = _get_base_dir() / "app_config.json"


def _load_config():
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"base_url": DEFAULT_BASE_URL}


def _save_config(base_url: str):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"base_url": base_url.rstrip("/")}, f, indent=2)
    except Exception:
        pass


def _check_connection(base_url: str) -> tuple[bool, str]:
    try:
        import requests
        r = requests.get(f"{base_url.rstrip('/')}/", timeout=3)
        return True, "Сервер доступен"
    except requests.exceptions.ConnectionError:
        return False, "Не удалось подключиться. Проверьте адрес и запущен ли сервер (python manage.py runserver)."
    except requests.exceptions.Timeout:
        return False, "Превышено время ожидания"
    except Exception as e:
        return False, str(e)


def _show_launcher():
    try:
        import customtkinter as ctk
    except ImportError:
        print("Установите customtkinter: pip install customtkinter")
        sys.exit(1)

    ctk.set_appearance_mode("light")
    config = _load_config()

    root = ctk.CTk()
    root.title("Платформа")
    root.geometry("480x280")
    root.resizable(False, False)

    main = ctk.CTkFrame(root, fg_color="transparent")
    main.pack(fill="both", expand=True, padx=24, pady=24)

    ctk.CTkLabel(main, text="Платформа", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(0, 20))
    ctk.CTkLabel(main, text="Адрес сервера:", font=ctk.CTkFont(size=12)).pack(anchor="w")
    url_var = ctk.StringVar(value=config.get("base_url", DEFAULT_BASE_URL))
    url_entry = ctk.CTkEntry(main, textvariable=url_var, width=380, height=36, font=ctk.CTkFont(size=12))
    url_entry.pack(pady=(4, 12))

    status_var = ctk.StringVar(value="")
    status_lbl = ctk.CTkLabel(main, textvariable=status_var, font=ctk.CTkFont(size=11), text_color="gray")
    status_lbl.pack(anchor="w", pady=(0, 12))

    def check():
        url = url_var.get().strip()
        if not url:
            status_var.set("Укажите адрес сервера")
            return
        if not url.startswith("http"):
            url = "http://" + url
            url_var.set(url)
        ok, msg = _check_connection(url)
        status_var.set("✓ " + msg if ok else "✗ " + msg)
        status_lbl.configure(text_color="#198754" if ok else "#dc3545")

    def start():
        url = url_var.get().strip()
        if not url:
            status_var.set("Укажите адрес сервера")
            return
        if not url.startswith("http"):
            url = "http://" + url
            url_var.set(url)
        ok, _ = _check_connection(url)
        if not ok:
            status_var.set("Сначала проверьте подключение")
            return
        _save_config(url)
        root.destroy()
        _run_webview(url)

    btn_row = ctk.CTkFrame(main, fg_color="transparent")
    btn_row.pack(fill="x")
    ctk.CTkButton(btn_row, text="Проверить подключение", command=check, width=180, height=36).pack(side="left", padx=(0, 12))
    ctk.CTkButton(btn_row, text="Войти", command=start, width=160, height=36, fg_color="#0d6efd").pack(side="left")

    root.mainloop()


def _run_webview(base_url: str):
    try:
        import webview
    except ImportError:
        print("Установите pywebview: pip install pywebview")
        sys.exit(1)

    url = f"{base_url.rstrip('/')}/login/"
    webview.create_window(
        "Платформа",
        url,
        width=1280,
        height=800,
        min_size=(1000, 700),
        resizable=True,
    )
    webview.start()


def main():
    args = sys.argv[1:]
    if "--launcher" in args:
        _show_launcher()
        return
    config = _load_config()
    base_url = config.get("base_url", DEFAULT_BASE_URL)
    if _check_connection(base_url)[0]:
        _run_webview(base_url)
    else:
        _show_launcher()


if __name__ == "__main__":
    main()
