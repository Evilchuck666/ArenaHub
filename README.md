# ArenaHub

Aplicación de escritorio multiplataforma en Python + Qt6 (PySide6).

## Preparar el entorno

| Sistema   | Comando                                   |
|-----------|-------------------------------------------|
| GNU/Linux | `./scripts/setup_linux.sh`                |
| macOS     | `./scripts/setup_macos.sh`                |
| Windows   | `scripts\setup_windows.bat`               |

El script instala [uv](https://docs.astral.sh/uv/) si falta, un Python gestionado por uv y todas las dependencias en `.venv/`.

## Uso

```bash
uv run arenahub                                        # ejecutar
uv run pytest                                          # tests
uv run pyinstaller ArenaHub.spec --clean --noconfirm   # ejecutable onefile en dist/
```

PyInstaller no hace compilación cruzada: genera el binario para el SO donde se ejecuta.
