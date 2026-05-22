import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import './styles/mobile.css'

// 移动端调试工具
import VConsole from 'vconsole'
const vc = new VConsole()

// 测试 vConsole 是否正常工作
console.log('🎉 vConsole 已启动！如果你看到这条消息，说明调试工具正常工作')
console.log('📱 当前浏览器:', navigator.userAgent)
console.log('🔧 调试模式已开启 - 所有操作都会显示详细日志')

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus)

app.mount('#app')
