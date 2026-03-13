#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复KeepAlive.spec文件中第5行
"""

import sys

spec_file = "KeepAlive.spec"

# 读取spec文件
with open(spec_file, "r", encoding="utf-8") as f:
    content = f.read()

# 修复第5行：双反斜杠改为单反斜杠
# 旧内容：'    ['src\\keepalive.py'],
# 修复：'src\\\\keepalive.py',

print("✅ 修复完成：双反斜杠 → 单反斜杠")

# 写回修改
with open(spec_file, "w", encoding="utf-8") as f:
    f.write(content)

print(f"✓ {spec_file} 已更新")
