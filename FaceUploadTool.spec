# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all('playwright')

# ============================================================
# Packages không dùng — loại ra khỏi bundle để giảm dung lượng
# numpy, psutil, yaml, greenlet là dependency phụ của playwright
# nhưng không được import trực tiếp trong code tool.
# ============================================================
EXCLUDES = [
    # Không dùng trong code
    'numpy', 'numpy.core', 'numpy.linalg', 'numpy.fft', 'numpy.random',
    'psutil',
    'yaml', 'pyyaml',
    # Test/dev packages
    'pytest', 'unittest', 'test', 'tests',
    'setuptools', 'pip', 'pkg_resources',
    # Các module nặng không cần
    'tkinter.test', 'tkinter.tix',
    'sqlite3',
    'html.parser', 'pydoc',
    'doctest', 'argparse',
    'multiprocessing',
]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=playwright_binaries,
    datas=[('acset', 'acset'), *playwright_datas],
    hiddenimports=playwright_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=2,  # Bỏ docstrings + assert (giảm nhẹ .pyc)
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FaceUploadTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # Bỏ strip trên Windows vì gây lỗi FileNotFoundError
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['acset\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,   # Bỏ strip trên Windows
    upx=True,
    upx_exclude=[],
    name='FaceUploadTool',
)
