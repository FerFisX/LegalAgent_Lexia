@echo off
REM ═══════════════════════════════════════════════════════════════
REM  Script de compilacion de la tesis LexIA
REM  Uso: doble clic en compilar.bat   o   ejecutar en CMD
REM ═══════════════════════════════════════════════════════════════

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   Compilando tesis LexIA...                  ║
echo  ╚══════════════════════════════════════════════╝
echo.

REM -- Verificar que pdflatex existe
where pdflatex >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] pdflatex no encontrado.
    echo  Instala MiKTeX desde: https://miktex.org/download
    echo  O ejecuta:  winget install MiKTeX.MiKTeX
    pause
    exit /b 1
)

REM -- Verificar que biber existe
where biber >nul 2>&1
if %errorlevel% neq 0 (
    echo  [AVISO] biber no encontrado. Instalando via MiKTeX...
    mpm --install=biber
)

echo  [1/4] Primera pasada pdflatex...
pdflatex -interaction=nonstopmode -halt-on-error main.tex
if %errorlevel% neq 0 goto :error

echo  [2/4] Procesando bibliografia con biber...
biber main
if %errorlevel% neq 0 (
    echo  [AVISO] biber fallo. Continuando sin bibliografia...
)

echo  [3/4] Segunda pasada pdflatex (referencias)...
pdflatex -interaction=nonstopmode -halt-on-error main.tex

echo  [4/4] Tercera pasada pdflatex (indice final)...
pdflatex -interaction=nonstopmode -halt-on-error main.tex

echo.
echo  ══════════════════════════════════════════════
echo   Compilacion completada!  Abriendo main.pdf...
echo  ══════════════════════════════════════════════
echo.

start main.pdf
goto :end

:error
echo.
echo  [ERROR] La compilacion fallo. Revisa main.log para detalles.
pause
exit /b 1

:end
echo  Listo.
pause
