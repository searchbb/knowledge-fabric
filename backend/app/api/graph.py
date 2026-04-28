"""
图谱相关API路由
采用项目上下文机制，服务端持久化状态
"""

import os
import traceback
import threading
from flask import request, jsonify

from . import graph_bp
from ..config import Config
from ..services.ontology_generator import OntologyGenerator
from ..services.reading_structure_extractor import ReadingStructureExtractor
from ..services.graph_builder import BuildCancelledError
from ..services.graph_builder_factory import (
    get_graph_builder,
    get_graph_builder_provider,
    validate_graph_builder_config,
)
from ..services.workspace.phase1_build_support import (
    _build_phase1_completion_decision,
    _build_phase1_task_result,
    _merge_duplicate_nodes,
    _normalize_phase1_build_outcome,
    _normalize_phase1_diagnostics,
    _normalize_phase1_reading_structure_status,
    _write_summaries_to_neo4j,
    _write_supplement_to_neo4j,
)
from ..services.graph_access_service import (
    GRAPH_BACKEND_LOCAL,
    delete_graph_by_backend,
    load_graph_data_by_backend,
    normalize_graph_backend,
)
from ..services.text_processor import TextProcessor
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..utils.pipeline_profiler import PipelineProfiler, set_profiler, stage
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager, ProjectStatus

# 获取日志器
logger = get_logger('mirofish.api')


def allowed_file(filename: str) -> bool:
    """检查文件扩展名是否允许"""
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


# ============== 项目管理接口 ==============

@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """
    获取项目详情
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": f"项目不存在: {project_id}"
        }), 404
    
    return jsonify({
        "success": True,
        "data": project.to_dict()
    })


@graph_bp.route('/project/<project_id>/text', methods=['GET'])
def get_project_text(project_id: str):
    """
    获取项目提取后的原文文本
    """
    project = ProjectManager.get_project(project_id)

    if not project:
        return jsonify({
            "success": False,
            "error": f"项目不存在: {project_id}"
        }), 404

    text = ProjectManager.get_extracted_text(project_id)
    if text is None:
        return jsonify({
            "success": False,
            "error": f"项目尚未保存提取文本: {project_id}"
        }), 404

    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "text": text,
            "char_count": len(text),
        }
    })


@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    """
    列出所有项目
    """
    limit = request.args.get('limit', 50, type=int)
    projects = ProjectManager.list_projects(limit=limit)
    
    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in projects],
        "count": len(projects)
    })


@graph_bp.route('/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """
    删除项目
    """
    success = ProjectManager.delete_project(project_id)
    
    if not success:
        return jsonify({
            "success": False,
            "error": f"项目不存在或删除失败: {project_id}"
        }), 404
    
    return jsonify({
        "success": True,
        "message": f"项目已删除: {project_id}"
    })


@graph_bp.route('/project/<project_id>/reset', methods=['POST'])
def reset_project(project_id: str):
    """
    重置项目状态（用于重新构建图谱）
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": f"项目不存在: {project_id}"
        }), 404
    
    # 重置到本体已生成状态
    if project.ontology:
        project.status = ProjectStatus.ONTOLOGY_GENERATED
    else:
        project.status = ProjectStatus.CREATED
    
    project.graph_id = None
    project.graph_build_task_id = None
    project.phase1_task_result = None
    project.reading_structure = None
    project.error = None
    ProjectManager.save_project(project)
    
    return jsonify({
        "success": True,
        "message": f"项目已重置: {project_id}",
        "data": project.to_dict()
    })


# ============== 接口1：上传文件并生成本体 ==============

@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """
    接口1：上传文件，分析生成本体定义
    
    请求方式：multipart/form-data
    
    参数：
        files: 上传的文件（PDF/MD/TXT），可多个
        simulation_requirement: 模拟需求描述（必填）
        project_name: 项目名称（可选）
        additional_context: 额外说明（可选）
        
    返回：
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "ontology": {
                    "entity_types": [...],
                    "edge_types": [...],
                    "analysis_summary": "..."
                },
                "files": [...],
                "total_text_length": 12345
            }
        }
    """
    try:
        logger.info("=== 开始生成本体定义 ===")
        
        # 获取参数
        simulation_requirement = request.form.get('simulation_requirement', '')
        project_name = request.form.get('project_name', 'Unnamed Project')
        additional_context = request.form.get('additional_context', '')
        # vault_relative_dir: 用户选择的 Obsidian vault 子目录(相对 vault 根)。
        # 空字符串表示不走 vault,沿用 backend/uploads(向后兼容,供未配置 vault 的环境使用)。
        vault_relative_dir = (request.form.get('vault_relative_dir') or '').strip() or None
        domain = request.form.get('domain', 'auto')
        if domain not in {"tech", "methodology", "auto"}:
            return jsonify({"error": f"invalid domain {domain!r}"}), 400

        logger.debug(f"项目名称: {project_name}")
        logger.debug(f"模拟需求: {simulation_requirement[:100]}...")
        if vault_relative_dir:
            logger.info(f"上传目标:Obsidian vault / {vault_relative_dir}")

        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": "请提供模拟需求描述 (simulation_requirement)"
            }), 400

        # 获取上传的文件
        uploaded_files = request.files.getlist('files')
        if not uploaded_files or all(not f.filename for f in uploaded_files):
            return jsonify({
                "success": False,
                "error": "请至少上传一个文档文件"
            }), 400

        # 创建项目
        project = ProjectManager.create_project(name=project_name, domain=domain)
        project.simulation_requirement = simulation_requirement
        logger.info(f"创建项目: {project.project_id}")

        # 保存文件并提取文本
        document_texts = []
        all_text = ""

        # vault 写入失败直接报错(零 fallback),并删除已创建的项目目录
        from ..services.vault_service import VaultError

        for file in uploaded_files:
            if file and file.filename and allowed_file(file.filename):
                try:
                    file_info = ProjectManager.save_file_to_project(
                        project.project_id,
                        file,
                        file.filename,
                        vault_relative_dir=vault_relative_dir,
                    )
                except VaultError as ve:
                    ProjectManager.delete_project(project.project_id)
                    logger.error(f"vault 写入失败 [{ve.code}]: {ve.message}")
                    return jsonify({
                        "success": False,
                        "error_code": ve.code,
                        "error": f"Obsidian vault 写入失败:{ve.message}",
                    }), 400
                project.files.append({
                    "filename": file_info["original_filename"],
                    "size": file_info["size"],
                    "source_backend": file_info["source_backend"],
                    "source_md_path": file_info["source_md_path"],
                    "vault_relative_dir": file_info["vault_relative_dir"],
                })

                # 提取文本(FileParser 直接读真源路径,vault 或 uploads 透明)
                text = FileParser.extract_text(file_info["path"])
                text = TextProcessor.preprocess_text(text)
                document_texts.append(text)
                all_text += f"\n\n=== {file_info['original_filename']} ===\n{text}"
        
        if not document_texts:
            ProjectManager.delete_project(project.project_id)
            return jsonify({
                "success": False,
                "error": "没有成功处理任何文档，请检查文件格式"
            }), 400
        
        # 保存提取的文本
        project.total_text_length = len(all_text)
        ProjectManager.save_extracted_text(project.project_id, all_text)
        logger.info(f"文本提取完成，共 {len(all_text)} 字符")
        
        # 生成本体
        logger.info("调用 LLM 生成本体定义...")
        from ..services.extraction.ontology_dispatcher import (
            get_ontology_generator, resolve_project_domain,
        )
        from ..services.llm_mode_service import get_pipeline_llm_params
        from ..utils.llm_client import LLMClient

        llm_params = get_pipeline_llm_params()
        ontology_llm_client = LLMClient(
            api_key=llm_params["api_key"],
            base_url=llm_params["base_url"],
            model=llm_params["model"],
        )
        logger.info(
            "本体生成使用 LLM provider=%s mode=%s model=%s",
            llm_params.get("provider"),
            llm_params.get("mode"),
            llm_params.get("model"),
        )

        # Resolve 'auto' to a concrete domain. Use the first document text
        # as the classifier input when available.
        article_text_for_classifier = (
            document_texts[0] if document_texts else ""
        )
        resolved_domain = resolve_project_domain(
            project.to_dict(),
            article_text=article_text_for_classifier or None,
            llm_client=ontology_llm_client,
        )
        generator = get_ontology_generator(
            resolved_domain,
            llm_client=ontology_llm_client,
        )

        # Interface compatibility: tech OntologyGenerator has
        # simulation_requirement as required positional; methodology has
        # it as optional kwarg. Call with explicit kwargs either way.
        if resolved_domain == "tech":
            ontology = generator.generate(
                document_texts,
                simulation_requirement,
                additional_context if additional_context else None,
            )
        else:
            ontology = generator.generate(
                document_texts=document_texts,
                simulation_requirement=simulation_requirement,
                additional_context=additional_context if additional_context else None,
            )

        # Record the resolved domain on the project so downstream stages know.
        project.domain = resolved_domain

        # 保存本体到项目
        entity_count = len(ontology.get("entity_types", []))
        edge_count = len(ontology.get("edge_types", []))
        logger.info(f"本体生成完成: {entity_count} 个实体类型, {edge_count} 个关系类型")

        project.ontology = {
            "entity_types": ontology.get("entity_types", []),
            "edge_types": ontology.get("edge_types", [])
        }
        project.ontology_metadata = ontology.get("metadata", {})
        if project.ontology_metadata is None:
            project.ontology_metadata = {}
        project.ontology_metadata["resolved_domain"] = resolved_domain
        project.ontology_metadata["llm_mode"] = llm_params.get("mode")
        project.ontology_metadata["llm_provider"] = llm_params.get("provider")
        project.ontology_metadata["llm_model"] = llm_params.get("model")
        project.analysis_summary = ontology.get("analysis_summary", "")
        project.status = ProjectStatus.ONTOLOGY_GENERATED
        ProjectManager.save_project(project)
        logger.info(f"=== 本体生成完成 === 项目ID: {project.project_id}")
        
        return jsonify({
            "success": True,
            "data": {
                "project_id": project.project_id,
                "project_name": project.name,
                "ontology": project.ontology,
                "ontology_metadata": project.ontology_metadata,
                "analysis_summary": project.analysis_summary,
                "files": project.files,
                "total_text_length": project.total_text_length
            }
        })

    except Exception as e:
        logger.error(f"本体生成失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 接口2：构建图谱 ==============

@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """
    接口2：根据project_id构建图谱
    
    请求（JSON）：
        {
            "project_id": "proj_xxxx",  // 必填，来自接口1
            "graph_name": "图谱名称",    // 可选
            "chunk_size": 500,          // 可选，默认500
            "chunk_overlap": 50         // 可选，默认50
        }
        
    返回：
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "task_id": "task_xxxx",
                "message": "图谱构建任务已启动"
            }
        }
    """
    try:
        logger.info("=== 开始构建图谱 ===")

        provider = get_graph_builder_provider()

        # 检查配置
        errors = validate_graph_builder_config(provider)
        if errors:
            logger.error("图谱构建配置错误(provider=%s): %s", provider, errors)
            return jsonify({
                "success": False,
                "error": "配置错误: " + "; ".join(errors)
            }), 500
        
        # 解析请求
        data = request.get_json() or {}
        project_id = data.get('project_id')
        logger.debug(f"请求参数: project_id={project_id}")
        
        if not project_id:
            return jsonify({
                "success": False,
                "error": "请提供 project_id"
            }), 400
        
        # 获取项目
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"项目不存在: {project_id}"
            }), 404
        
        # 检查项目状态
        force = data.get('force', False)  # 强制重新构建
        
        if project.status == ProjectStatus.CREATED:
            return jsonify({
                "success": False,
                "error": "项目尚未生成本体，请先调用 /ontology/generate"
            }), 400
        
        if project.status == ProjectStatus.GRAPH_BUILDING and not force:
            return jsonify({
                "success": False,
                "error": "图谱正在构建中，请勿重复提交。如需强制重建，请添加 force: true",
                "task_id": project.graph_build_task_id
            }), 400
        
        # 如果强制重建，重置状态
        if force and project.status in [ProjectStatus.GRAPH_BUILDING, ProjectStatus.FAILED, ProjectStatus.GRAPH_COMPLETED]:
            project.status = ProjectStatus.ONTOLOGY_GENERATED
            project.graph_id = None
            project.graph_build_task_id = None
            project.phase1_task_result = None
            project.reading_structure = None
            project.error = None
        
        # 获取配置
        graph_name = data.get('graph_name', project.name or 'Knowledge Fabric Center Graph')
        chunk_size = data.get('chunk_size', project.chunk_size or Config.DEFAULT_CHUNK_SIZE)
        chunk_overlap = data.get('chunk_overlap', project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP)
        
        # 更新项目配置
        project.chunk_size = chunk_size
        project.chunk_overlap = chunk_overlap
        
        # 获取提取的文本
        text = ProjectManager.get_extracted_text(project_id)
        if not text:
            return jsonify({
                "success": False,
                "error": "未找到提取的文本内容"
            }), 400
        
        # 获取本体
        ontology = project.ontology
        if not ontology:
            return jsonify({
                "success": False,
                "error": "未找到本体定义"
            }), 400
        
        # 创建异步任务
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            f"构建图谱: {graph_name}",
            metadata={"project_id": project_id},
        )
        logger.info(f"创建图谱构建任务: task_id={task_id}, project_id={project_id}")
        
        # 更新项目状态
        project.status = ProjectStatus.GRAPH_BUILDING
        project.graph_build_task_id = task_id
        project.phase1_task_result = None
        ProjectManager.save_project(project)
        
        # 启动后台任务
        def build_task():
            build_logger = get_logger('mirofish.build')

            # === Wall-clock profiling (opt-in via PROFILE_BUILD_OUT env var). ===
            # When unset, the stage() context manager below is a no-op; zero overhead.
            _profile_path = os.environ.get("PROFILE_BUILD_OUT")
            _profile = None
            if _profile_path:
                _profile = PipelineProfiler(
                    run_id=task_id,
                    extra={
                        "project_id": project_id,
                        "graph_name": graph_name,
                        "provider": provider,
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                    },
                )
                set_profiler(_profile)

            try:
                build_logger.info(f"[{task_id}] 开始构建图谱(provider={provider})...")
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    message=f"初始化图谱构建服务 ({provider})..."
                )

                with stage("init_builder"):
                    builder = get_graph_builder(provider)

                task_manager.update_task(
                    task_id,
                    message="文本分块中...",
                    progress=5
                )
                with stage("chunk_split"):
                    chunks = TextProcessor.split_text(
                        text,
                        chunk_size=chunk_size,
                        overlap=chunk_overlap
                    )
                total_chunks = len(chunks)

                task_manager.update_task(
                    task_id,
                    message="创建图谱...",
                    progress=10
                )
                with stage("create_graph"):
                    graph_id = builder.create_graph(name=graph_name)

                project.graph_id = graph_id
                ProjectManager.save_project(project)

                task_manager.update_task(
                    task_id,
                    message="设置本体定义...",
                    progress=15
                )
                with stage("set_ontology"):
                    builder.set_ontology(graph_id, ontology)

                task_manager.update_task(
                    task_id,
                    message="检查存储兼容性...",
                    progress=18
                )
                with stage("ensure_storage_compat"):
                    try:
                        dropped_constraints = builder.ensure_phase1_storage_compatibility(graph_id)
                    except AttributeError:
                        dropped_constraints = []
                        build_logger.debug(f"[{task_id}] builder does not support ensure_phase1_storage_compatibility, skip")

                def add_progress_callback(msg, progress_ratio):
                    progress = 18 + int(progress_ratio * 37)  # 18% - 55%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )

                def cancel_check() -> bool:
                    return task_manager.is_cancel_requested(task_id)

                task_manager.update_task(
                    task_id,
                    message=f"开始添加 {total_chunks} 个文本块...",
                    progress=18
                )
                # Read batch_size from the currently-active LLM mode snapshot.
                # local → Config.GRAPHITI_BATCH_SIZE; bailian →
                # Config.BAILIAN_BATCH_SIZE. Graphiti batches serialize across
                # batches, so the provider-specific snapshot owns this tuning.
                try:
                    from ..services.llm_mode_service import get_graphiti_llm_params
                    _active_params = get_graphiti_llm_params()
                    _active_batch_size = max(int(_active_params.get('batch_size') or 1), 1)
                except Exception:
                    _active_batch_size = Config.GRAPHITI_BATCH_SIZE
                build_logger.info(
                    f"[{task_id}] 使用 batch_size={_active_batch_size} 走 add_text_batches..."
                )
                with stage(
                    "add_text_batches",
                    n_chunks=total_chunks,
                    batch_size=_active_batch_size,
                ):
                    episode_uuids = builder.add_text_batches(
                        graph_id,
                        chunks,
                        batch_size=_active_batch_size,
                        progress_callback=add_progress_callback,
                        cancel_check=cancel_check,
                    )

                task_manager.update_task(
                    task_id,
                    message="等待图谱处理完成...",
                    progress=55
                )

                def wait_progress_callback(msg, progress_ratio):
                    progress = 55 + int(progress_ratio * 35)  # 55% - 90%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )

                with stage("wait_for_episodes", n_episodes=len(episode_uuids or [])):
                    builder._wait_for_episodes(
                        episode_uuids,
                        progress_callback=wait_progress_callback
                    )

                diagnostics = _normalize_phase1_diagnostics(
                    getattr(builder, "get_build_diagnostics", lambda: {})(),
                    provider=provider,
                    chunk_count=total_chunks,
                )
                if (
                    diagnostics.get("processed_chunk_count", 0) == 0
                    and diagnostics.get("aborted_due_to_rate_limit")
                ):
                    raise RuntimeError("All chunks failed due to rate limiting")

                task_manager.update_task(
                    task_id,
                    message="清理图谱噪声...",
                    progress=92
                )
                with stage("prune_invalid_edges"):
                    try:
                        builder._run_async(builder.prune_invalid_edges_async(graph_id))
                    except AttributeError:
                        build_logger.debug(f"[{task_id}] builder does not support prune_invalid_edges_async, skip")

                task_manager.update_task(
                    task_id,
                    message="获取图谱数据...",
                    progress=95
                )
                with stage("get_graph_data"):
                    graph_data = builder.get_graph_data(graph_id)
                diagnostics = _normalize_phase1_diagnostics(
                    getattr(builder, "get_build_diagnostics", lambda: {})(),
                    provider=provider,
                    chunk_count=total_chunks,
                    dropped_constraints=dropped_constraints,
                )

                node_count = graph_data.get("node_count", 0)
                edge_count = graph_data.get("edge_count", 0)

                # === 质量检查与定向补抽 ===
                if provider == "local" and node_count > 0:
                    try:
                        from ..services.graph_quality_gate import GraphQualityGate
                        quality_gate = GraphQualityGate()
                        with stage("quality_gate_assess"):
                            assessment = quality_gate.assess(graph_data, ontology, text)
                        if assessment.should_supplement:
                            task_manager.update_task(
                                task_id,
                                message=f"质量检查: 补充抽取 {', '.join(assessment.missing_types)}...",
                                progress=93,
                            )
                            with stage(
                                "quality_gate_supplement",
                                missing_types=list(assessment.missing_types),
                            ):
                                supplement = quality_gate.supplement(
                                    missing_types=assessment.missing_types,
                                    document_text=text,
                                    ontology=ontology,
                                    existing_nodes=graph_data.get("nodes", []),
                                )
                                if supplement.new_nodes:
                                    # 写入 Neo4j
                                    _write_supplement_to_neo4j(
                                        builder, graph_id, supplement
                                    )
                                    # 重新获取图谱数据
                                    graph_data = builder.get_graph_data(graph_id)
                                    node_count = graph_data.get("node_count", 0)
                                    edge_count = graph_data.get("edge_count", 0)
                                    build_logger.info(
                                        f"[{task_id}] 补抽后: {node_count} 节点, {edge_count} 边 "
                                        f"(补充了 {len(supplement.new_nodes)} 节点, {len(supplement.new_edges)} 边)"
                                    )
                    except Exception as gate_exc:
                        build_logger.warning(f"[{task_id}] 质量检查/补抽失败(不影响原图谱): {gate_exc}")

                # === 节点去重：合并名称高度相似的节点 ===
                if provider == "local" and node_count > 0:
                    task_manager.update_task(
                        task_id,
                        message="合并相似节点...",
                        progress=95,
                    )
                    try:
                        from ..services.graph_quality_gate import GraphQualityGate as _DedupGate
                        with stage("dedup_find_near_duplicates"):
                            dupes = _DedupGate.find_near_duplicates(graph_data, threshold=0.70)
                        if dupes:
                            build_logger.info(
                                f"[{task_id}] 发现 {len(dupes)} 对近似重复节点，开始合并"
                            )
                            with stage("dedup_merge_duplicates", n_pairs=len(dupes)):
                                _merge_duplicate_nodes(builder, graph_id, dupes, build_logger=build_logger)
                                graph_data = builder.get_graph_data(graph_id)
                                node_count = graph_data.get("node_count", 0)
                                edge_count = graph_data.get("edge_count", 0)
                    except Exception as dedup_exc:
                        build_logger.warning(f"[{task_id}] 节点去重失败(不影响原图谱): {dedup_exc}")

                # === Summary 回填：为空 summary 节点补充描述 ===
                summary_backfill_meta = {
                    "summary_backfill_requested": 0,
                    "summary_backfill_completed": 0,
                    "summary_backfill_missing": [],
                    "summary_backfill_error": "",
                }
                if provider == "local" and node_count > 0:
                    task_manager.update_task(
                        task_id,
                        message="回填节点摘要...",
                        progress=96,
                    )
                    try:
                        from ..services.graph_quality_gate import GraphQualityGate as _SummaryGate
                        _sg = _SummaryGate()

                        def summary_progress_callback(message: str) -> None:
                            task_manager.update_task(
                                task_id,
                                message=message,
                                progress=96,
                            )

                        with stage("summary_backfill"):
                            backfilled = _sg.backfill_summaries(
                                graph_data=graph_data,
                                document_text=text,
                                progress_callback=summary_progress_callback,
                            )
                        meta = dict(getattr(_sg, "last_summary_backfill_meta", {}) or {})
                        summary_backfill_meta["summary_backfill_requested"] = max(
                            int(meta.get("requested") or 0), 0
                        )
                        summary_backfill_meta["summary_backfill_completed"] = max(
                            int(meta.get("completed") or 0), 0
                        )
                        summary_backfill_meta["summary_backfill_missing"] = list(
                            meta.get("missing") or []
                        )
                        if backfilled:
                            task_manager.update_task(
                                task_id,
                                message=f"写回节点摘要... {len(backfilled)} 个",
                                progress=96,
                            )
                            with stage("summary_write_neo4j", n_nodes=len(backfilled)):
                                _write_summaries_to_neo4j(builder, graph_id, backfilled)
                            graph_data = builder.get_graph_data(graph_id)
                            node_count = graph_data.get("node_count", 0)
                            edge_count = graph_data.get("edge_count", 0)
                            remaining_empty_names = [
                                (node.get("name") or "").strip()
                                for node in graph_data.get("nodes", [])
                                if not (node.get("summary") or "").strip()
                            ]
                            summary_backfill_meta["summary_backfill_missing"] = [
                                name for name in remaining_empty_names if name
                            ]
                            summary_backfill_meta["summary_backfill_completed"] = max(
                                summary_backfill_meta["summary_backfill_requested"]
                                - len(summary_backfill_meta["summary_backfill_missing"]),
                                0,
                            )
                            build_logger.info(
                                f"[{task_id}] summary 回填: {len(backfilled)} 个节点"
                            )
                    except Exception as sf_exc:
                        summary_backfill_meta["summary_backfill_error"] = str(sf_exc)[:300]
                        build_logger.warning(f"[{task_id}] summary 回填失败: {sf_exc}")

                diagnostics.update(summary_backfill_meta)
                diagnostics = _normalize_phase1_diagnostics(
                    diagnostics,
                    provider=provider,
                    chunk_count=total_chunks,
                    dropped_constraints=dropped_constraints,
                )

                completion_decision = _normalize_phase1_build_outcome(
                    _build_phase1_completion_decision(diagnostics, graph_data)
                )
                if diagnostics.get("summary_backfill_error"):
                    completion_decision = dict(completion_decision)
                    completion_decision.setdefault("warnings", [])
                    completion_decision["warnings"].append(
                        f"summary 回填失败: {diagnostics['summary_backfill_error']}"
                    )
                    if completion_decision["status"] == "completed":
                        completion_decision["status"] = "completed_with_warnings"
                elif diagnostics.get("summary_backfill_missing"):
                    completion_decision = dict(completion_decision)
                    completion_decision.setdefault("warnings", [])
                    completion_decision["warnings"].append(
                        "summary 回填未覆盖 "
                        f"{len(diagnostics['summary_backfill_missing'])}/"
                        f"{diagnostics.get('summary_backfill_requested', 0)} 个节点"
                    )
                    if completion_decision["status"] == "completed":
                        completion_decision["status"] = "completed_with_warnings"

                reading_structure_status = {
                    "status": "not_started",
                    "reason": "",
                }

                if completion_decision["can_generate_reading_structure"]:
                    task_manager.update_task(
                        task_id,
                        message="整理阅读骨架...",
                        progress=97
                    )
                    try:
                        extractor = ReadingStructureExtractor()
                        # Prefer the resolved domain from ontology_metadata (what
                        # the classifier chose), fallback to project.domain, then
                        # 'tech' for legacy safety.
                        metadata = project.ontology_metadata or {}
                        reading_domain = metadata.get("resolved_domain") or project.domain or "tech"
                        if reading_domain == "auto":
                            reading_domain = "tech"
                        with stage("reading_structure"):
                            reading_structure = extractor.extract(
                                project_name=project.name or graph_name,
                                document_text=text,
                                analysis_summary=project.analysis_summary or "",
                                ontology=ontology,
                                graph_data=graph_data,
                                simulation_requirement=project.simulation_requirement or "",
                                domain=reading_domain,
                            )
                        project.reading_structure = reading_structure
                        reading_structure_status = _normalize_phase1_reading_structure_status(
                            dict(getattr(extractor, "last_result_meta", {}) or {})
                        )
                        ProjectManager.save_project(project)
                    except Exception as reading_exc:
                        reading_structure_status = {
                            "status": "failed",
                            "reason": str(reading_exc)[:300],
                        }
                        build_logger.warning(f"[{task_id}] 阅读骨架提取失败，将继续保留图谱结果: {reading_exc}")
                else:
                    reading_structure_status = {
                        "status": "skipped",
                        "reason": completion_decision["reason"] or "图谱完整度不足，跳过阅读骨架生成",
                    }
                    project.reading_structure = None
                    ProjectManager.save_project(project)

                reading_structure_status = _normalize_phase1_reading_structure_status(reading_structure_status)
                if reading_structure_status.get("status") != "generated":
                    completion_decision = dict(completion_decision)
                    completion_decision.setdefault("warnings", [])
                    completion_decision["warnings"].append(
                        f"阅读骨架状态: {reading_structure_status.get('status', 'unknown')}"
                    )
                    if completion_decision["status"] == "completed":
                        completion_decision["status"] = "completed_with_warnings"

                if completion_decision["status"] == "failed":
                    raise RuntimeError(completion_decision["reason"])

                project.status = ProjectStatus.GRAPH_COMPLETED
                project.error = None
                ProjectManager.save_project(project)

                build_logger.info(f"[{task_id}] 图谱构建完成: graph_id={graph_id}, 节点={node_count}, 边={edge_count}")

                phase1_result = _build_phase1_task_result(
                    provider=provider,
                    project_id=project_id,
                    graph_id=graph_id,
                    chunk_count=total_chunks,
                    node_count=node_count,
                    edge_count=edge_count,
                    diagnostics=diagnostics,
                    build_outcome=completion_decision,
                    reading_structure_status=reading_structure_status,
                    dropped_constraints=dropped_constraints,
                )

                project.phase1_task_result = phase1_result
                ProjectManager.save_project(project)

                task_manager.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    message=(
                        "图谱构建完成"
                        if completion_decision["status"] == "completed"
                        else "图谱构建完成（有告警）"
                    ),
                    progress=100,
                    result=phase1_result,
                )
            except BuildCancelledError as cancel_exc:
                build_logger.info(
                    f"[{task_id}] 图谱构建被取消(provider={provider}): {cancel_exc}"
                )
                project.status = ProjectStatus.FAILED
                project.error = f"cancelled: {cancel_exc}"
                ProjectManager.save_project(project)

                cancel_result = _build_phase1_task_result(
                    provider=provider,
                    project_id=project_id,
                    graph_id=project.graph_id,
                    chunk_count=locals().get("total_chunks", 0),
                    node_count=locals().get("node_count", 0),
                    edge_count=locals().get("edge_count", 0),
                    diagnostics=locals().get("diagnostics")
                    or getattr(locals().get("builder"), "get_build_diagnostics", lambda: {})(),
                    build_outcome={
                        "status": "cancelled",
                        "reason": str(cancel_exc),
                        "success_ratio": (
                            cancel_exc.processed_chunks / cancel_exc.total_chunks
                            if cancel_exc.total_chunks
                            else 0.0
                        ),
                        "can_generate_reading_structure": False,
                        "warnings": [],
                    },
                    reading_structure_status=locals().get("reading_structure_status"),
                    dropped_constraints=locals().get("dropped_constraints"),
                )
                project.phase1_task_result = cancel_result
                ProjectManager.save_project(project)
                task_manager.mark_cancelled(task_id, reason=str(cancel_exc))
            except Exception as e:
                build_logger.error(f"[{task_id}] 图谱构建失败(provider={provider}): {str(e)}")
                build_logger.debug(traceback.format_exc())

                project.status = ProjectStatus.FAILED
                project.error = str(e)
                ProjectManager.save_project(project)

                failure_result = _build_phase1_task_result(
                    provider=provider,
                    project_id=project_id,
                    graph_id=project.graph_id,
                    chunk_count=locals().get("total_chunks", 0),
                    node_count=locals().get("node_count", 0),
                    edge_count=locals().get("edge_count", 0),
                    diagnostics=locals().get("diagnostics")
                    or getattr(locals().get("builder"), "get_build_diagnostics", lambda: {})(),
                    build_outcome=locals().get("completion_decision")
                    or {
                        "status": "failed",
                        "reason": str(e),
                        "success_ratio": 0.0,
                        "can_generate_reading_structure": False,
                        "warnings": [],
                    },
                    reading_structure_status=locals().get("reading_structure_status"),
                    dropped_constraints=locals().get("dropped_constraints"),
                )

                project.phase1_task_result = failure_result
                ProjectManager.save_project(project)

                task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    message=f"构建失败: {str(e)}",
                    error=traceback.format_exc(),
                    result=failure_result,
                )
            finally:
                # === Profile teardown (no-op when profiling was disabled). ===
                if _profile is not None:
                    try:
                        from pathlib import Path as _PPath
                        _profile.write_json(_PPath(_profile_path))
                        _profile.print_summary()
                        build_logger.info(
                            f"[{task_id}] profile written → {_profile_path}"
                        )
                    except Exception as prof_exc:  # never fail the build for profiling
                        build_logger.warning(
                            f"[{task_id}] failed to write profile: {prof_exc}"
                        )
                    finally:
                        set_profiler(None)

        # 启动后台线程
        thread = threading.Thread(target=build_task, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "task_id": task_id,
                "message": "图谱构建任务已启动，请通过 /task/{task_id} 查询进度"
            }
        })

    except Exception as e:
        logger.error(f"构建图谱接口异常: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 任务查询接口 ==============

@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """
    查询任务状态
    """
    task = TaskManager().get_task(task_id)

    if not task:
        return jsonify({
            "success": False,
            "error": f"任务不存在: {task_id}"
        }), 404

    return jsonify({
        "success": True,
        "data": task.to_dict()
    })


@graph_bp.route('/task/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id: str):
    """Cooperative cancel for a long-running task.

    The graph build runs in a daemon thread we cannot safely kill from
    the outside. This endpoint instead sets a ``cancel_requested`` flag
    on the task record. The worker checks the flag at each chunk
    boundary and exits voluntarily, leaving the in-flight LLM call to
    finish before the thread returns.

    Request body (optional): ``{"reason": "..."}``

    Returns 200 with ``{"success": true, "cancel_requested": true}``
    when the flag was set, 404 when the task is unknown, and 409 when
    the task is already in a terminal state.
    """
    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip()

    manager = TaskManager()
    task = manager.get_task(task_id)
    if task is None:
        return jsonify({
            "success": False,
            "error": f"任务不存在: {task_id}",
        }), 404

    if not manager.request_cancel(task_id, reason=reason):
        return jsonify({
            "success": False,
            "error": f"任务无法取消（当前状态: {task.status.value}）",
            "data": task.to_dict(),
        }), 409

    refreshed = manager.get_task(task_id)
    return jsonify({
        "success": True,
        "data": refreshed.to_dict() if refreshed else None,
    })


@graph_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """
    列出所有任务
    """
    tasks = TaskManager().list_tasks()
    
    return jsonify({
        "success": True,
        "data": tasks,
        "count": len(tasks)
    })


# ============== 图谱数据接口 ==============

@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    """
    获取图谱数据（节点和边）
    """
    try:
        backend = normalize_graph_backend(request.args.get("backend", GRAPH_BACKEND_LOCAL))
    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400

    try:
        graph_data = load_graph_data_by_backend(graph_id, backend=backend)
        
        return jsonify({
            "success": True,
            "data": graph_data,
            "backend": backend,
        })

    except Exception as e:
        logger.error(f"获取图谱数据失败 graph_id={graph_id} backend={backend}: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@graph_bp.route('/delete/<graph_id>', methods=['DELETE'])
def delete_graph(graph_id: str):
    """
    删除图谱
    """
    try:
        backend = normalize_graph_backend(request.args.get("backend", GRAPH_BACKEND_LOCAL))
    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400

    try:
        delete_graph_by_backend(graph_id, backend=backend)
        
        return jsonify({
            "success": True,
            "message": f"图谱已删除: {graph_id}",
            "backend": backend,
        })

    except Exception as e:
        logger.error(f"删除图谱失败 graph_id={graph_id} backend={backend}: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
