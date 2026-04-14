import { reactive } from 'vue'

export const articleStore = reactive({
  article: null,
  graph: null,
  readingStructure: null,
  diagnostics: null,
  loading: false,
  error: '',
})
