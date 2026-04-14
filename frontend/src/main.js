import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

// Design tokens + themes. tokens.css 必须最先引入,作为所有主题的 fallback。
import './styles/tokens.css'
import './styles/themes/ivory-study.css'
import './styles/themes/night-scholar.css'
import './styles/themes/blue-ledger.css'
import './styles/themes/ink-wash.css'
import './styles/themes/sepia-archive.css'

const app = createApp(App)

app.use(router)

app.mount('#app')
