# -*- coding: utf-8 -*-
import sys, io, re
sys.stdout.reconfigure(encoding="utf-8")
import net

URLS = [
    ("jb51_dingge_kadian", "https://www.jb51.net/softjc/821033.html"),
    ("jingyan_dingge", "https://jingyan.baidu.com/article/29697b917add56ea21de3c31.html"),
    ("pconline_dingge", "https://g.pconline.com.cn/x/156/15612638.html"),
    ("sohu_dingge", "https://m.sohu.com/a/816626870_122054911/"),
]

for name, u in URLS:
    print("\n" + "=" * 70)
    print("### %s  %s" % (name, u))
    try:
        b = net.raw(u)
        t = net.text_of(b)
        print(t[:5000])
    except Exception as e:
        print("FAIL", type(e).__name__, e)
