@echo off
REM Elimina archivos auxiliares de compilacion LaTeX (mantiene main.tex y main.pdf)
echo Limpiando archivos auxiliares...
del /q *.aux *.log *.toc *.lof *.lot *.out *.bbl *.bcf *.blg *.run.xml *.acn *.acr *.alg *.glg *.glo *.gls *.ist *.fls *.fdb_latexmk 2>nul
echo Listo.
pause
