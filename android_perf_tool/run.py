import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')

sys.path.insert(0, current_dir)
sys.path.insert(0, src_dir)

print(f"当前目录: {current_dir}")
print(f"源码目录: {src_dir}")
print(f"Python路径: {sys.executable}")

try:
    from android_perf_tool.gui import main
    print("模块导入成功")
    main()
except ImportError as e:
    print(f"导入错误: {e}")
    print("尝试重新导入...")
    try:
        import importlib.util
        gui_path = os.path.join(src_dir, 'android_perf_tool', 'gui.py')
        spec = importlib.util.spec_from_file_location("gui", gui_path)
        gui_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gui_module)
        gui_module.main()
    except Exception as e2:
        print(f"再次尝试失败: {e2}")
        print("请确保已安装依赖:")
        print(f"{sys.executable} -m pip install pandas openpyxl beautifulsoup4")
        input("按回车键退出...")
        sys.exit(1)