"""
项目上下文管理
用于在服务端持久化项目状态，避免前端在接口间传递大量数据
"""

import os
import json
import re
import uuid
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field, asdict
from ..config import Config
from ..services.vault_service import VaultService, VaultError


class ProjectStatus(str, Enum):
    """项目状态"""
    CREATED = "created"              # 刚创建，文件已上传
    ONTOLOGY_GENERATED = "ontology_generated"  # 本体已生成
    GRAPH_BUILDING = "graph_building"    # 图谱构建中
    GRAPH_COMPLETED = "graph_completed"  # 图谱构建完成
    FAILED = "failed"                # 失败


@dataclass
class Project:
    """项目数据模型"""
    project_id: str
    name: str
    status: ProjectStatus
    created_at: str
    updated_at: str
    
    # 文件信息
    files: List[Dict[str, str]] = field(default_factory=list)  # [{filename, path, size}]
    total_text_length: int = 0
    
    # 本体信息（接口1生成后填充）
    ontology: Optional[Dict[str, Any]] = None
    ontology_metadata: Optional[Dict[str, Any]] = None
    analysis_summary: Optional[str] = None
    reading_structure: Optional[Dict[str, Any]] = None
    
    # 图谱信息（接口2完成后填充）
    graph_id: Optional[str] = None
    graph_build_task_id: Optional[str] = None
    phase1_task_result: Optional[Dict[str, Any]] = None
    
    # 配置
    simulation_requirement: Optional[str] = None
    chunk_size: int = Config.DEFAULT_CHUNK_SIZE
    chunk_overlap: int = Config.DEFAULT_CHUNK_OVERLAP
    
    # Phase 2 人工决策（校验状态）
    review_decisions: Optional[Dict[str, Any]] = None
    concept_decisions: Optional[Dict[str, Any]] = None
    theme_decisions: Optional[Dict[str, Any]] = None
    theme_clusters: Optional[List[Dict[str, Any]]] = None

    # 错误信息
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "status": self.status.value if isinstance(self.status, ProjectStatus) else self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "files": self.files,
            "total_text_length": self.total_text_length,
            "ontology": self.ontology,
            "ontology_metadata": self.ontology_metadata,
            "analysis_summary": self.analysis_summary,
            "reading_structure": self.reading_structure,
            "graph_id": self.graph_id,
            "graph_build_task_id": self.graph_build_task_id,
            "phase1_task_result": self.phase1_task_result,
            "simulation_requirement": self.simulation_requirement,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "review_decisions": self.review_decisions,
            "concept_decisions": self.concept_decisions,
            "theme_decisions": self.theme_decisions,
            "theme_clusters": self.theme_clusters,
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """从字典创建"""
        status = data.get('status', 'created')
        if isinstance(status, str):
            status = ProjectStatus(status)
        
        return cls(
            project_id=data['project_id'],
            name=data.get('name', 'Unnamed Project'),
            status=status,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            files=data.get('files', []),
            total_text_length=data.get('total_text_length', 0),
            ontology=data.get('ontology'),
            ontology_metadata=data.get('ontology_metadata'),
            analysis_summary=data.get('analysis_summary'),
            reading_structure=data.get('reading_structure'),
            graph_id=data.get('graph_id'),
            graph_build_task_id=data.get('graph_build_task_id'),
            phase1_task_result=data.get('phase1_task_result'),
            simulation_requirement=data.get('simulation_requirement'),
            chunk_size=data.get('chunk_size', Config.DEFAULT_CHUNK_SIZE),
            chunk_overlap=data.get('chunk_overlap', Config.DEFAULT_CHUNK_OVERLAP),
            review_decisions=data.get('review_decisions'),
            concept_decisions=data.get('concept_decisions'),
            theme_decisions=data.get('theme_decisions'),
            theme_clusters=data.get('theme_clusters'),
            error=data.get('error')
        )


class ProjectManager:
    """项目管理器 - 负责项目的持久化存储和检索"""
    
    # 项目存储根目录
    PROJECTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'projects')
    
    @classmethod
    def _ensure_projects_dir(cls):
        """确保项目目录存在"""
        os.makedirs(cls.PROJECTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_project_dir(cls, project_id: str) -> str:
        """获取项目目录路径"""
        return os.path.join(cls.PROJECTS_DIR, project_id)
    
    @classmethod
    def _get_project_meta_path(cls, project_id: str) -> str:
        """获取项目元数据文件路径"""
        return os.path.join(cls._get_project_dir(project_id), 'project.json')
    
    @classmethod
    def _get_project_files_dir(cls, project_id: str) -> str:
        """获取项目文件存储目录"""
        return os.path.join(cls._get_project_dir(project_id), 'files')
    
    @classmethod
    def _get_project_text_path(cls, project_id: str) -> str:
        """获取项目提取文本存储路径"""
        return os.path.join(cls._get_project_dir(project_id), 'extracted_text.txt')
    
    @classmethod
    def create_project(cls, name: str = "Unnamed Project") -> Project:
        """
        创建新项目
        
        Args:
            name: 项目名称
            
        Returns:
            新创建的Project对象
        """
        cls._ensure_projects_dir()
        
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        
        project = Project(
            project_id=project_id,
            name=name,
            status=ProjectStatus.CREATED,
            created_at=now,
            updated_at=now
        )
        
        # 创建项目目录结构
        project_dir = cls._get_project_dir(project_id)
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(files_dir, exist_ok=True)
        
        # 保存项目元数据
        cls.save_project(project)
        
        return project
    
    @classmethod
    def save_project(cls, project: Project, *, touch_updated_at: bool = True) -> None:
        """保存项目元数据"""
        if touch_updated_at:
            project.updated_at = datetime.now().isoformat()
        meta_path = cls._get_project_meta_path(project.project_id)
        
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def get_project(
        cls,
        project_id: str,
        *,
        include_legacy_phase1_backfill: bool = True,
    ) -> Optional[Project]:
        """
        获取项目
        
        Args:
            project_id: 项目ID
            
        Returns:
            Project对象，如果不存在返回None
        """
        meta_path = cls._get_project_meta_path(project_id)
        
        if not os.path.exists(meta_path):
            return None
        
        with open(meta_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        project = Project.from_dict(data)

        if include_legacy_phase1_backfill:
            from .task import TaskManager
            from ..services.workspace.legacy_phase1_snapshot import (
                build_legacy_phase1_snapshot,
                build_orphaned_graph_build_recovery,
            )

            if (
                project.status == ProjectStatus.GRAPH_BUILDING
                and project.graph_build_task_id
                and TaskManager().get_task(project.graph_build_task_id) is None
            ):
                recovered = build_orphaned_graph_build_recovery(project)
                if recovered:
                    project.status = recovered["project_status"]
                    project.graph_build_task_id = None
                    project.phase1_task_result = recovered["phase1_task_result"]
                    project.error = recovered.get("error")
                    cls.save_project(project)

            if not project.phase1_task_result:
                inferred_snapshot = build_legacy_phase1_snapshot(project)
                if inferred_snapshot:
                    project.phase1_task_result = inferred_snapshot

        return project
    
    @classmethod
    def list_projects(cls, limit: int = 50) -> List[Project]:
        """
        列出所有项目
        
        Args:
            limit: 返回数量限制
            
        Returns:
            项目列表，按创建时间倒序
        """
        cls._ensure_projects_dir()
        
        projects = []
        for project_id in os.listdir(cls.PROJECTS_DIR):
            project = cls.get_project(project_id)
            if project:
                projects.append(project)
        
        # 按创建时间倒序排序
        projects.sort(key=lambda p: p.created_at, reverse=True)
        
        return projects[:limit]
    
    @classmethod
    def delete_project(cls, project_id: str) -> bool:
        """
        删除项目及其所有文件
        
        Args:
            project_id: 项目ID
            
        Returns:
            是否删除成功
        """
        project_dir = cls._get_project_dir(project_id)
        
        if not os.path.exists(project_dir):
            return False
        
        shutil.rmtree(project_dir)
        return True
    
    @classmethod
    def save_file_to_project(
        cls,
        project_id: str,
        file_storage,
        original_filename: str,
        *,
        vault_relative_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        保存上传的文件到项目目录。

        若 `vault_relative_dir` 提供且 VaultService 可用,
        - 真源 md 写到 `<vault>/<vault_relative_dir>/<safe_original_name>`
        - 派生物(backend/uploads/projects/<pid>/files/)仅保留一个 .ref 指针,
          以便旧代码路径(FileParser.extract_text 等)不崩溃
        否则沿用原行为:写到 backend/uploads 下。

        Returns:
            {
                original_filename, saved_filename, path, size,
                source_backend: "vault" | "uploads",
                source_md_path: 真源绝对路径,
                vault_relative_dir: 若走 vault 则记录用户选择的相对目录,否则 None
            }
        """
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(files_dir, exist_ok=True)

        ext = os.path.splitext(original_filename)[1].lower()

        use_vault = bool(vault_relative_dir) and VaultService.is_enabled()
        if use_vault:
            # vault 模式:保留原始文件名(OB 会用文件名做双链),冲突时追加 -N
            vault_abs_dir = VaultService.resolve_target_dir(vault_relative_dir)
            vault_filename = cls._sanitize_vault_filename(original_filename)
            vault_path = cls._allocate_unique_path(vault_abs_dir, vault_filename)
            file_storage.save(vault_path)
            file_size = os.path.getsize(vault_path)

            return {
                "original_filename": original_filename,
                "saved_filename": os.path.basename(vault_path),
                "path": vault_path,
                "size": file_size,
                "source_backend": "vault",
                "source_md_path": vault_path,
                "vault_relative_dir": vault_relative_dir,
            }

        # 默认:写 backend/uploads (兼容旧流程)
        safe_filename = f"{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(files_dir, safe_filename)
        file_storage.save(file_path)
        file_size = os.path.getsize(file_path)

        return {
            "original_filename": original_filename,
            "saved_filename": safe_filename,
            "path": file_path,
            "size": file_size,
            "source_backend": "uploads",
            "source_md_path": file_path,
            "vault_relative_dir": None,
        }

    @staticmethod
    def _sanitize_vault_filename(original_filename: str) -> str:
        """清理 vault 文件名:去掉路径分隔符和 OB 保留字符,保留中文/空格。

        OB 的文件名允许大部分 Unicode 字符,但 `/`、`\\`、`:` 等必须去掉。
        """
        base = os.path.basename(original_filename).strip()
        if not base:
            base = f"untitled_{uuid.uuid4().hex[:6]}.md"
        # 替换 OB 忌讳字符为 -
        base = re.sub(r'[\\/:*?"<>|]', '-', base)
        return base

    @staticmethod
    def _allocate_unique_path(target_dir: str, filename: str) -> str:
        """如果 target_dir/filename 已存在,追加 -1 / -2 / ... 直到找到空位。"""
        candidate = os.path.join(target_dir, filename)
        if not os.path.exists(candidate):
            return candidate
        stem, ext = os.path.splitext(filename)
        for i in range(1, 1000):
            candidate = os.path.join(target_dir, f"{stem}-{i}{ext}")
            if not os.path.exists(candidate):
                return candidate
        # 极端情况:继续往上撞,用 uuid 兜底保证不覆盖
        return os.path.join(target_dir, f"{stem}-{uuid.uuid4().hex[:6]}{ext}")
    
    @classmethod
    def save_extracted_text(cls, project_id: str, text: str) -> None:
        """保存提取的文本"""
        text_path = cls._get_project_text_path(project_id)
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)
    
    @classmethod
    def get_extracted_text(cls, project_id: str) -> Optional[str]:
        """获取提取的文本"""
        text_path = cls._get_project_text_path(project_id)
        
        if not os.path.exists(text_path):
            return None
        
        with open(text_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @classmethod
    def get_project_files(cls, project_id: str) -> List[str]:
        """获取项目的所有文件路径"""
        files_dir = cls._get_project_files_dir(project_id)
        
        if not os.path.exists(files_dir):
            return []
        
        return [
            os.path.join(files_dir, f) 
            for f in os.listdir(files_dir) 
            if os.path.isfile(os.path.join(files_dir, f))
        ]
