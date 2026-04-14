<template>
  <div class="subgraph-card">
    <svg v-if="positionedNodes.length" class="subgraph-svg" viewBox="0 0 420 220" role="img" aria-label="局部子图预览">
      <line
        v-for="edge in positionedEdges"
        :key="edge.id"
        class="graph-edge"
        :x1="edge.source.x"
        :y1="edge.source.y"
        :x2="edge.target.x"
        :y2="edge.target.y"
      />

      <g v-for="node in positionedNodes" :key="node.id">
        <circle
          class="graph-node"
          :class="{ focus: node.isFocus }"
          :cx="node.x"
          :cy="node.y"
          :r="node.isFocus ? 28 : 22"
        />
        <text class="node-label" :x="node.x" :y="node.y - 2" text-anchor="middle">
          {{ shortenNodeName(node.name) }}
        </text>
        <text class="node-kind" :x="node.x" :y="node.y + 15" text-anchor="middle">
          {{ node.label }}
        </text>
      </g>
    </svg>

    <p class="graph-caption">{{ subgraph?.caption || '当前没有局部子图可展示。' }}</p>

    <div v-if="positionedEdges.length" class="edge-list">
      <div v-for="edge in subgraph.edges" :key="edge.id" class="edge-item">
        <span class="edge-name">{{ edge.label }}</span>
        <span class="edge-fact">{{ shortenText(edge.fact, 96) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  subgraph: {
    type: Object,
    default: () => ({
      nodes: [],
      edges: [],
      caption: '',
    }),
  },
})

const layoutSlots = [
  { x: 210, y: 110 },
  { x: 95, y: 60 },
  { x: 325, y: 60 },
  { x: 95, y: 170 },
  { x: 325, y: 170 },
  { x: 210, y: 36 },
]

function shortenNodeName(name) {
  const value = String(name || '')
  return value.length > 10 ? `${value.slice(0, 9)}…` : value
}

function shortenText(value, maxLength = 80) {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength - 1)}…`
}

const positionedNodes = computed(() => {
  const nodes = props.subgraph?.nodes || []
  return nodes.map((node, index) => ({
    ...node,
    ...layoutSlots[index % layoutSlots.length],
  }))
})

const nodeMap = computed(() => new Map(positionedNodes.value.map((node) => [node.id, node])))

const positionedEdges = computed(() =>
  (props.subgraph?.edges || [])
    .map((edge) => ({
      ...edge,
      source: nodeMap.value.get(edge.source),
      target: nodeMap.value.get(edge.target),
    }))
    .filter((edge) => edge.source && edge.target),
)
</script>

<style scoped>
.subgraph-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.subgraph-svg {
  width: 100%;
  height: 240px;
  border-radius: 18px;
  background:
    radial-gradient(circle at top right, rgba(247, 203, 123, 0.12), transparent 30%),
    linear-gradient(180deg, #fffefb 0%, #fff8ee 100%);
  border: 1px solid #efe3d2;
}

.graph-edge {
  stroke: #d4b283;
  stroke-width: 2;
  opacity: 0.9;
}

.graph-node {
  fill: #ffffff;
  stroke: #d9ba8e;
  stroke-width: 2;
}

.graph-node.focus {
  fill: #fff0d6;
  stroke: #bf7d28;
  stroke-width: 3;
}

.node-label,
.node-kind {
  fill: #2c241b;
  font-size: 12px;
  font-weight: 700;
}

.node-kind {
  fill: #8a6a3a;
  font-size: 10px;
  font-weight: 600;
}

.graph-caption,
.edge-fact {
  color: #62584d;
  line-height: 1.6;
}

.edge-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.edge-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border: 1px solid #efe3d2;
  border-radius: 14px;
  background: #fffdf9;
  padding: 10px 12px;
}

.edge-name {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #8f6c38;
  font-weight: 700;
}
</style>
