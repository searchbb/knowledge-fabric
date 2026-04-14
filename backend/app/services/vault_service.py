"""Obsidian vault 集成服务。

职责:
- 扫描 vault 一级主题目录,供前端下拉选择
- 校验用户提供的相对路径未越出 vault(防目录遍历攻击)
- 解析最终写入的绝对路径,返回给调用方

零 fallback 原则:
- vault 未配置 / 路径无效 / 不可写 → 抛 VaultError,不偷偷回退 backend/uploads
- 调用方(ProjectManager)根据 Config.OBSIDIAN_VAULT_PATH 是否为 None 自行决定是否调用本服务
"""

import os
from dataclasses import dataclass
from typing import List, Optional

from ..config import Config


class VaultError(Exception):
    """Vault 操作类错误的基类。错误码对应前端可展示的语义。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# 扫描 vault 时跳过的系统/特殊目录
_SKIP_DIRS = {
    '.obsidian',
    '.trash',
    '.DS_Store',
    '_Archived Items',
    '图片',  # 顶层 图片/ 目录只放资源,不放 md
}


@dataclass
class VaultTheme:
    """Vault 下一个可作为 md 落地的主题目录。

    relative_path 是相对 vault 根的路径(用 POSIX 分隔符),
    label 是展示名,has_notes_subdir 提示前端"建议选 笔记库 子目录"。
    """

    label: str
    relative_path: str
    has_notes_subdir: bool

    def to_dict(self):
        return {
            "label": self.label,
            "relative_path": self.relative_path,
            "has_notes_subdir": self.has_notes_subdir,
        }


class VaultService:
    """Obsidian vault 读写操作的统一入口。"""

    @classmethod
    def is_enabled(cls) -> bool:
        """Config 里配了 vault 路径就算启用(有效性由 Config.validate 启动时兜底)。"""
        return bool(Config.OBSIDIAN_VAULT_PATH)

    @classmethod
    def vault_root(cls) -> str:
        """返回 vault 绝对根路径。未配置则抛 VaultError。"""
        root = Config.OBSIDIAN_VAULT_PATH
        if not root:
            raise VaultError("VAULT_NOT_CONFIGURED", "OBSIDIAN_VAULT_PATH 未配置")
        if not os.path.isdir(root):
            raise VaultError("VAULT_NOT_READY", f"vault 目录不存在: {root}")
        return root

    @classmethod
    def list_themes(cls) -> List[VaultTheme]:
        """列出 vault 下的主题候选。

        策略:
        - 只扫 vault 根一级目录,跳过系统/归档目录
        - 若主题下有 `笔记库` 子目录,同时产出主题和 主题/笔记库 两条,
          让用户自由选择"扔主题根"还是"按 OB 习惯扔 笔记库"
        - 返回按 label 排序的列表
        """
        root = cls.vault_root()
        themes: List[VaultTheme] = []

        for entry in sorted(os.listdir(root)):
            if entry.startswith('.') or entry in _SKIP_DIRS:
                continue
            entry_path = os.path.join(root, entry)
            if not os.path.isdir(entry_path):
                continue

            notes_dir = os.path.join(entry_path, '笔记库')
            has_notes = os.path.isdir(notes_dir)
            themes.append(
                VaultTheme(
                    label=entry,
                    relative_path=entry,
                    has_notes_subdir=has_notes,
                )
            )
            if has_notes:
                themes.append(
                    VaultTheme(
                        label=f"{entry} / 笔记库",
                        relative_path=f"{entry}/笔记库",
                        has_notes_subdir=False,
                    )
                )

        return themes

    @classmethod
    def resolve_target_dir(cls, relative_path: str) -> str:
        """把前端传入的相对路径解析成 vault 下的绝对目录。

        强校验:
        - 非空
        - normalize 后仍在 vault 根下(防 `../` 越权)
        - 最终目录存在且可写
        """
        if not relative_path or not relative_path.strip():
            raise VaultError("VAULT_PATH_EMPTY", "vault 目标路径为空")

        root = cls.vault_root()
        # normpath 处理 `a//b`, `a/./b`, `a/b/../c` 等
        normalized = os.path.normpath(relative_path.strip())
        if normalized.startswith('..') or os.path.isabs(normalized):
            raise VaultError(
                "VAULT_PATH_ESCAPE",
                f"非法 vault 目标路径(越出 vault 或绝对路径): {relative_path}",
            )

        abs_target = os.path.realpath(os.path.join(root, normalized))
        abs_root = os.path.realpath(root)
        # realpath 后做 prefix 检查,防符号链接跳出 vault
        if not (abs_target == abs_root or abs_target.startswith(abs_root + os.sep)):
            raise VaultError(
                "VAULT_PATH_ESCAPE",
                f"解析后的 vault 目标路径越出 vault 根: {relative_path}",
            )

        if not os.path.isdir(abs_target):
            raise VaultError(
                "VAULT_TARGET_MISSING",
                f"vault 目标目录不存在: {normalized} (请先在 Obsidian 里创建)",
            )
        if not os.access(abs_target, os.W_OK):
            raise VaultError(
                "VAULT_NOT_WRITABLE",
                f"vault 目标目录不可写: {normalized}",
            )

        return abs_target

    @classmethod
    def to_relative_path(cls, abs_path: Optional[str]) -> Optional[str]:
        """把 vault 下的绝对路径转成相对 vault 根的路径(POSIX 分隔符)。

        如果路径不在 vault 下返回 None(表示这不是 vault 源,可能是旧项目的 backend/uploads)。
        """
        if not abs_path:
            return None
        try:
            root = cls.vault_root()
        except VaultError:
            return None

        try:
            abs_target = os.path.realpath(abs_path)
            abs_root = os.path.realpath(root)
        except OSError:
            return None

        if not (abs_target == abs_root or abs_target.startswith(abs_root + os.sep)):
            return None

        rel = os.path.relpath(abs_target, abs_root)
        return rel.replace(os.sep, '/')
