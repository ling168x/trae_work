"""
程序统一启动入口。
"""

import sys
import os

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# 切换工作目录到项目根，确保 scrapy.cfg 能被找到
os.chdir(PROJECT_ROOT)

# 将 Scrapy 项目路径注册到环境变量（必须在导入 scrapy 之前设置）
os.environ["SCRAPY_SETTINGS_MODULE"] = "scrapy_engine.settings"


if __name__ == "__main__":
    from gui.main_window import main
    main()