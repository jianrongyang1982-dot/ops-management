import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Home from '../views/Home.vue'
import ContainerList from '../views/ContainerList.vue'
import Dashboard from '../views/Dashboard.vue'
import PerformanceCoefficient from '../views/PerformanceCoefficient.vue'
import PerformanceEmployee from '../views/PerformanceEmployee.vue'

const routes = [
  { path: '/login', name: 'Login', component: Login },
  // 旧地址重定向，保证已有收藏夹/链接继续可用
  { path: '/container', redirect: '/container/list' },
  { path: '/dashboard', redirect: '/container/dashboard' },
  {
    path: '/',
    name: 'Home',
    component: Home,
    children: [
      { path: '', redirect: '/container/list' },
      { path: 'container/list', name: 'Container', component: ContainerList },
      { path: 'container/dashboard', name: 'Dashboard', component: Dashboard },
      { path: 'performance/coefficients', name: 'PerformanceCoefficient', component: PerformanceCoefficient },
      { path: 'performance/employee', name: 'PerformanceEmployee', component: PerformanceEmployee },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router
