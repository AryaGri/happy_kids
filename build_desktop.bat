@echo off
cd /d "%~dp0"
echo Установка PyInstaller...
pip install pyinstaller -q
echo.
echo Сборка приложения...
pyinstaller --noconfirm desktop_client\platform.spec
echo.
if exist "dist\Платформа\Платформа.exe" (
    echo Готово: dist\Платформа\
    echo Запуск: dist\Платформа\Платформа.exe
    echo.
    echo Для раздачи: заархивируйте папку dist\Платформа в ZIP.
) else (
    echo Ошибка сборки. Проверьте вывод выше.
)
pause
