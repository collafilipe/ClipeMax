"""
Aviso na tela quando um corte chega para a decisao do CEO.

A vigia roda sem janela, entao quem nao esta com a tela de aprovacao aberta nao fica sabendo que tem
corte esperando, e no lancamento o tempo entre o corte ficar pronto e ser postado e o que decide as views.
O aviso e a notificacao comum do Windows (canto da tela e central de notificacoes); clicar nela abre a
tela de aprovacao. Fora do Windows, ou se o sistema recusar, nada acontece: aviso nunca derruba a vigia.
"""
import os
import subprocess
import sys
from xml.sax.saxutils import escape

# Identidade do PowerShell no Windows: notificacao so aparece em nome de um programa registrado no sistema
_APP = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
# O texto vai por variavel de ambiente, nao colado no comando: titulo de corte tem aspas e cifrao
_SCRIPT = (
    "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
    "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null;"
    "$x = New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml($env:CLIPEMAX_AVISO);"
    "$t = New-Object Windows.UI.Notifications.ToastNotification $x;"
    "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:CLIPEMAX_APP).Show($t)"
)


def montar(titulo, texto, link=""):
    """O XML da notificacao. Com `link`, clicar no aviso abre esse endereco no navegador."""
    abrir = f' activationType="protocol" launch="{escape(link, {chr(34): "&quot;"})}"' if link else ""
    return (f"<toast{abrir}><visual><binding template=\"ToastGeneric\">"
            f"<text>{escape(titulo[:80])}</text><text>{escape(texto[:200])}</text></binding></visual></toast>")


def texto_dos_cortes(subiram, aguardando):
    """(titulo, texto) do aviso de cortes que chegaram a mesa do CEO."""
    titulo = "1 corte novo para aprovar" if subiram == 1 else f"{subiram} cortes novos para aprovar"
    return titulo, f"{aguardando} aguardando a sua decisão. Clique para abrir a tela de aprovação."


def avisar(titulo, texto, link="", rodar=subprocess.run, plataforma=sys.platform):
    """Mostra a notificacao. Devolve True se o sistema aceitou; nunca levanta erro."""
    if plataforma != "win32":
        return False
    try:
        r = rodar(["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT],
                  env={**os.environ, "CLIPEMAX_AVISO": montar(titulo, texto, link), "CLIPEMAX_APP": _APP},
                  capture_output=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
