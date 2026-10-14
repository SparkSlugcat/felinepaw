' ============================================================
'  felinepaw 无窗口启动器 —— 双击本文件打开图形界面
'
'  为什么需要它：双击 .bat 时，那一下必须由 cmd.exe 去解析，命令行
'  窗口一定会出现（哪怕里面立刻 start 了 pythonw，也会闪）。想让
'  窗口彻底不出现，入口就不能是 .bat —— 本文件由 wscript.exe 执行，
'  而 wscript 是 GUI 子系统程序，自己不带控制台。
'
'  做法：先以「隐藏窗口」跑同目录的 启动.bat silent；它返回非 0
'        （说明启动自检没过）就再用「可见窗口」跑一次 启动.bat，
'        把报错和 pause 摆到眼前。
'        隐藏模式下的失败是**看不见**的，那才是最麻烦的情况，
'        所以这里一定要兜住"失败了要让你知道"。
' ============================================================
Option Explicit

Dim fso, sh, here, bat, rc
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")

here = fso.GetParentFolderName(WScript.ScriptFullName)
bat  = here & "\启动.bat"

If Not fso.FileExists(bat) Then
    MsgBox "找不到 启动.bat ——它得和本文件放在同一个目录：" & vbCrLf & bat, 16, "felinepaw"
    WScript.Quit 1
End If

' Run(命令, 窗口样式, 是否等它结束)
'   0    = 隐藏窗口
'   True = 等它跑完（不等就拿不到退出码）
' 路径带空格和中文，所以整条命令两头各加一个双引号
' （VBS 里一个双引号要写成两个，"""" 就是四个）。
rc = sh.Run("""" & bat & """" & " silent", 0, True)

If rc <> 0 Then
    ' 1 = 正常显示窗口。这一次不传 silent，所以 启动.bat 会 pause，
    ' 用户能看到失败的真正原因，而不是"双击了没反应"。
    sh.Run """" & bat & """", 1, True
End If
