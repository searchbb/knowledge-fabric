<template>
  <section class="link-section">
    <div class="section-head">
      <h3>{{ title }}</h3>
      <span>{{ links.length }}</span>
    </div>
    <div v-if="!links.length" class="empty-line">暂无关联</div>
    <div v-else class="link-list">
      <article v-for="link in links" :key="link.link_id || `${link.target_type}:${link.target_id}`" class="link-row">
        <div>
          <div class="link-title">{{ link.target_title || link.target_id }}</div>
          <div class="link-meta">
            <span>{{ link.target_id }}</span>
            <span>{{ roleLabel(link.role) }}</span>
            <span :class="['status-pill', `status-${link.status || 'candidate'}`]">
              {{ statusLabel(link.status) }}
            </span>
          </div>
        </div>
        <p v-if="link.rationale" class="rationale">{{ link.rationale }}</p>
        <div v-if="editable" class="link-actions">
          <select :value="link.role || 'candidate'" @change="$emit('update-link', link, { role: $event.target.value })">
            <option value="primary">primary</option>
            <option value="supporting">supporting</option>
            <option value="candidate">candidate</option>
          </select>
          <select :value="link.status || 'candidate'" @change="$emit('update-link', link, { status: $event.target.value })">
            <option value="accepted">accepted</option>
            <option value="candidate">candidate</option>
            <option value="needs_review">needs_review</option>
            <option value="rejected">rejected</option>
          </select>
          <button type="button" class="danger-btn" @click="$emit('remove-link', link)">移除</button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  links: { type: Array, default: () => [] },
  editable: { type: Boolean, default: false },
})

defineEmits(['update-link', 'remove-link'])

function statusLabel(status) {
  const map = {
    accepted: '已确认',
    candidate: '候选',
    needs_review: '待复核',
    rejected: '已拒绝',
  }
  return map[status] || status || '候选'
}

function roleLabel(role) {
  const map = {
    primary: '主入口',
    supporting: '支撑',
    candidate: '候选',
  }
  return map[role] || role || '候选'
}
</script>

<style scoped>
.link-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-default);
  padding-bottom: 8px;
}
.section-head h3 {
  margin: 0;
  font-size: 15px;
}
.section-head span {
  color: var(--text-muted);
  font-size: 12px;
}
.empty-line {
  color: var(--text-muted);
  font-size: 13px;
  padding: 10px 0;
}
.link-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.link-row {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 12px;
  background: var(--bg-surface);
}
.link-title {
  font-weight: 700;
  color: var(--text-primary);
}
.link-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-muted);
}
.status-pill {
  border-radius: 999px;
  padding: 1px 8px;
  border: 1px solid var(--border-default);
}
.status-accepted {
  color: #136f36;
  background: #e7f7ec;
  border-color: #b6e1c3;
}
.status-candidate {
  color: #7c4a03;
  background: #fff4d6;
  border-color: #f3d58b;
}
.status-needs_review {
  color: #8a3a00;
  background: #ffeddc;
  border-color: #f0c39b;
}
.rationale {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
}
.link-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.link-actions select {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 6px 8px;
  background: var(--bg-surface);
  color: var(--text-primary);
}
.danger-btn {
  border: 1px solid #f2b8b5;
  color: #8c1d18;
  background: #fff1f0;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
}
</style>
