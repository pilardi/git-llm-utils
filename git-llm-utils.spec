# -*- mode: python ; coding: utf-8 -*-
import litellm
import os
litellm_dir = os.path.dirname(os.path.abspath(litellm.__file__))

a = Analysis(
    ['src/git_llm_utils/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # see https://github.com/openai/tiktoken/issues/80#issuecomment-1484965176
        (f'{litellm_dir}/litellm_core_utils/tokenizers/anthropic_tokenizer.json', 'litellm/litellm_core_utils/tokenizers'),
        # https://pyinstaller.org/en/v4.1/runtime-information.html#using-file
        (f'src/git_llm_utils/prepare-commit-msg.template', 'git_llm_utils/'),
        (f'src/git_llm_utils/commit-msg.template', 'git_llm_utils/'),
    ],
    hiddenimports=[
        'tiktoken_ext',
        'tiktoken_ext.openai_public',
        'litellm'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='git-llm-utils',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
