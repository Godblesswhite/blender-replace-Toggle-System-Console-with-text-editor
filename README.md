# blender-replace-Toggle-System-Console-with-text-editor

切换逻辑可以概括为 4 步：

保存原始输出流
启用时先缓存当前的 sys.stdout 和 sys.stderr（通常是系统终端/Blender 默认输出对象），以便后续恢复。

创建一个“类文件”写入器
实现一个对象（writer），至少提供 write() 和 flush()：

write() 把收到的字符串追加写入 bpy.data.texts["PY_STDOUT.txt"]

可选：同时把同样的内容再转发给原始 stdout（用于保留系统控制台输出）

全局替换 stdout/stderr
把：

sys.stdout = writer

sys.stderr = writer
从这一刻起，所有走 Python 标准输出/错误的内容（print()、很多 traceback、warnings）都会进入该 Text。

禁用/卸载时恢复
关闭插件或卸载时：

先 flush() 写入器（把缓冲内容写完）

再把 sys.stdout/sys.stderr 设回你在第 1 步保存的原始对象

在 Blender 5.0 里，为了避免“启用时 prefs 未就绪导致没生效”，我们把第 2–3 步 延迟到下一帧（timer）执行，确保插件偏好与 Blender 上下文准备完成后再安装重定向。
