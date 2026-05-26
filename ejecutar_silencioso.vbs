Set WshShell = CreateObject("WScript.Shell")
Dim comando
comando = "cmd /c cd /d ""C:\Users\HP\Documents\Trenes España"" && " & _
            "set PYTHONIOENCODING=utf-8 && " & _
            "C:\Python314\python.exe main.py >> log.txt 2>&1"
WshShell.Run comando, 0, False
Set WshShell = Nothing
