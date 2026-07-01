$ErrorActionPreference = "Stop"

$python = "C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
$pythonRoot = Split-Path $python -Parent

& $python -m PyInstaller `
    -y `
    --clean `
    --onefile `
    --windowed `
    --runtime-tmpdir . `
    --name ATmega4809_UPDI_Programmer `
    --hidden-import _tkinter `
    --add-data "avrdude.exe;." `
    --add-data "avrdude.conf;." `
    --add-data "$pythonRoot\Lib\tkinter;tkinter" `
    --add-data "$pythonRoot\tcl\tcl8.6;_tcl_data" `
    --add-data "$pythonRoot\tcl\tk8.6;_tk_data" `
    --add-binary "$pythonRoot\DLLs\tcl86t.dll;." `
    --add-binary "$pythonRoot\DLLs\tk86t.dll;." `
    .\updi_programmer.py

Write-Host ""
Write-Host "Build complete: .\dist\ATmega4809_UPDI_Programmer.exe"
