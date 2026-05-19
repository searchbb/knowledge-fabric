<template>
  <section class="trace-panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">Traceability Map</div>
        <p>从现有资产计算证据、洞察、选项、验证计划、决策、材料和领导汇报之间的显式引用关系。这里是只读审计视图。</p>
      </div>
      <button type="button" class="btn-secondary" :disabled="loading" @click="$emit('refresh')">
        刷新
      </button>
    </div>

    <p v-if="error" class="inline-error">{{ error }}</p>
    <div v-if="loading" class="state-line">正在计算追踪图...</div>

    <template v-else>
      <div class="filter-row">
        <label>
          <span>Briefing</span>
          <select :value="filters.briefing_id" @change="updateFilter('briefing_id', $event.target.value)">
            <option value="">全部</option>
            <option v-for="briefing in briefingNodes" :key="briefing.asset_id" :value="briefing.asset_id">
              {{ briefing.title }}
            </option>
          </select>
        </label>
        <label>
          <span>Asset type</span>
          <select :value="filters.asset_type" @change="updateFilter('asset_type', $event.target.value)">
            <option value="">全部</option>
            <option v-for="type in assetTypes" :key="type" :value="type">{{ type }}</option>
          </select>
        </label>
        <label>
          <span>Issue severity</span>
          <select :value="filters.issue_severity" @change="updateFilter('issue_severity', $event.target.value)">
            <option value="">全部</option>
            <option value="blocking">blocking</option>
            <option value="warning">warning</option>
            <option value="info">info</option>
          </select>
        </label>
      </div>

      <div class="summary-grid">
        <div><strong>{{ summary.node_count || 0 }}</strong><span>Nodes</span></div>
        <div><strong>{{ summary.edge_count || 0 }}</strong><span>Edges</span></div>
        <div><strong>{{ summary.blocking_issue_count || 0 }}</strong><span>Blocking</span></div>
        <div><strong>{{ summary.warning_issue_count || 0 }}</strong><span>Warnings</span></div>
        <div><strong>{{ summary.orphan_node_count || 0 }}</strong><span>Orphans</span></div>
        <div><strong>{{ readiness }}</strong><span>Readiness</span></div>
      </div>

      <div v-if="!map.nodes?.length" class="empty-state">暂无可追踪资产</div>
      <template v-else>
        <div class="lane-grid">
          <section v-for="lane in map.lanes || []" :key="lane.lane_id" class="lane-column">
            <h3>{{ lane.title }}</h3>
            <article
              v-for="node in nodesByLane[lane.lane_id] || []"
              :key="node.node_id"
              class="node-card"
            >
              <div class="asset-topline">
                <span class="status-pill">{{ node.asset_type }}</span>
                <span v-if="node.status" class="status-pill">{{ node.status }}</span>
                <span v-if="node.readiness" class="status-pill">{{ node.readiness }}</span>
                <span v-if="node.issue_counts?.blocking" class="status-pill danger">B {{ node.issue_counts.blocking }}</span>
                <span v-if="node.issue_counts?.warning" class="status-pill warn">W {{ node.issue_counts.warning }}</span>
              </div>
              <h4>{{ node.title }}</h4>
              <p>{{ node.asset_id }}</p>
            </article>
          </section>
        </div>

        <div class="split-grid">
          <section class="table-card">
            <h3>References</h3>
            <table>
              <thead>
                <tr>
                  <th>From</th>
                  <th>Relation</th>
                  <th>To</th>
                  <th>Field</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="edge in map.edges || []" :key="edge.edge_id">
                  <td>{{ edge.from_node_id }}</td>
                  <td>{{ edge.relation_type }}</td>
                  <td>{{ edge.to_node_id }}</td>
                  <td>{{ edge.source_field }}</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section class="table-card">
            <h3>Issues</h3>
            <div v-if="!(map.issues || []).length" class="empty-state">无追踪问题</div>
            <article v-for="issue in map.issues || []" :key="issue.issue_id" class="issue-row">
              <div class="asset-topline">
                <span class="status-pill" :class="{ danger: issue.severity === 'blocking', warn: issue.severity === 'warning' }">{{ issue.severity }}</span>
                <span class="status-pill">{{ issue.issue_type }}</span>
              </div>
              <strong>{{ issue.asset_type }} · {{ issue.asset_id }}</strong>
              <p>{{ issue.message }}</p>
            </article>
          </section>
        </div>
      </template>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  map: { type: Object, default: () => ({ nodes: [], edges: [], issues: [], lanes: [], summary: {} }) },
  filters: { type: Object, default: () => ({ briefing_id: '', asset_type: '', issue_severity: '' }) },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['update-filter', 'refresh'])

const summary = computed(() => props.map?.summary || {})
const readiness = computed(() => props.map?.traceability_readiness || 'ready')
const briefingNodes = computed(() => (props.map?.nodes || []).filter((node) => node.asset_type === 'leadership_briefing'))
const assetTypes = computed(() => Array.from(new Set((props.map?.nodes || []).map((node) => node.asset_type))).sort())
const nodesByLane = computed(() => {
  const grouped = {}
  for (const node of props.map?.nodes || []) {
    grouped[node.lane_id] = grouped[node.lane_id] || []
    grouped[node.lane_id].push(node)
  }
  return grouped
})

function updateFilter(key, value) {
  emit('update-filter', { ...props.filters, [key]: value })
}
</script>

<style scoped>
.trace-panel {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  border-radius: 8px;
  padding: 14px;
  margin-top: 16px;
}

.panel-head,
.asset-topline,
.filter-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.panel-head {
  justify-content: space-between;
}

.panel-title {
  font-size: 12px;
  font-weight: 800;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 6px;
}

.panel-head p,
.node-card p,
.issue-row p {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.5;
}

.filter-row {
  margin-top: 12px;
}

.filter-row label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 180px;
  flex: 1;
}

.filter-row span {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 700;
}

.filter-row select {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-surface-2);
  color: var(--text-primary);
  padding: 8px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.summary-grid div,
.lane-column,
.node-card,
.table-card,
.empty-state,
.state-line,
.issue-row {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-surface-2);
}

.summary-grid div,
.lane-column,
.node-card,
.table-card,
.empty-state,
.state-line,
.issue-row {
  padding: 12px;
}

.summary-grid strong {
  display: block;
  font-size: 18px;
}

.summary-grid span {
  color: var(--text-muted);
  font-size: 12px;
}

.lane-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.lane-column h3,
.table-card h3 {
  margin: 0 0 10px;
  font-size: 14px;
}

.node-card,
.issue-row {
  margin-top: 8px;
}

.node-card h4 {
  margin: 8px 0 4px;
  font-size: 13px;
  line-height: 1.35;
}

.split-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: 10px;
  margin-top: 14px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th,
td {
  border-bottom: 1px solid var(--border-default);
  padding: 8px 6px;
  text-align: left;
  vertical-align: top;
  word-break: break-word;
}

th {
  color: var(--text-muted);
  font-size: 11px;
}

.status-pill.warn {
  border-color: rgba(194, 128, 32, 0.45);
  color: #9a5a00;
}

@media (max-width: 1100px) {
  .summary-grid,
  .lane-grid,
  .split-grid {
    grid-template-columns: 1fr;
  }
}
</style>
