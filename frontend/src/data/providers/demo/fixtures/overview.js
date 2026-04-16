// Demo overview fixture.
//
// Three sample projects with plausible numbers so a stranger landing on
// the overview page immediately understands: the product tracks concepts
// across projects, aligns them into a global registry, clusters them by
// theme, and tracks review backlog.
//
// Shape matches the real /api/registry/overview response so the page
// component doesn't need to know it's fake.

export const overviewFixture = {
  success: true,
  data: {
    project_count: 3,
    global_stats: {
      registry_entries: 48,
      global_themes: 7,
      pending_reviews: 5,
    },
    projects: [
      {
        project_id: 'demo-observability-platform',
        project_name: '可观测性平台调研',
        status: 'ready',
        concept_count: 34,
        accepted_concept_count: 28,
        linked_concept_count: 22,
        alignment_coverage: 0.76,
        theme_cluster_count: 4,
        pending_review_count: 2,
      },
      {
        project_id: 'demo-agentic-workflows',
        project_name: 'Agentic Workflows 设计笔记',
        status: 'ready',
        concept_count: 41,
        accepted_concept_count: 33,
        linked_concept_count: 19,
        alignment_coverage: 0.58,
        theme_cluster_count: 5,
        pending_review_count: 3,
      },
      {
        project_id: 'demo-retrieval-benchmarks',
        project_name: '检索增强生成基准对比',
        status: 'building',
        concept_count: 17,
        accepted_concept_count: 11,
        linked_concept_count: 7,
        alignment_coverage: 0.41,
        theme_cluster_count: 2,
        pending_review_count: 0,
      },
    ],
  },
}
