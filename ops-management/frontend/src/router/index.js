import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Home from '../views/Home.vue'
import HomeDashboard from '../views/HomeDashboard.vue'
import ContainerList from '../views/ContainerList.vue'
import Dashboard from '../views/Dashboard.vue'
import PerformanceCoefficient from '../views/PerformanceCoefficient.vue'
import PerformanceEmployee from '../views/PerformanceEmployee.vue'
import OtbDashboard from '../views/OtbDashboard.vue'
import OtbCategory from '../views/OtbCategory.vue'
import OtbBrand from '../views/OtbBrand.vue'
import OtbBrandCategory from '../views/OtbBrandCategory.vue'
import OtbSalesCurve from '../views/OtbSalesCurve.vue'
import OtbReplenishment from '../views/OtbReplenishment.vue'
import BuDefinition from '../views/BuDefinition.vue'
import BuBrandRelation from '../views/BuBrandRelation.vue'
import SystemLoginLog from '../views/SystemLoginLog.vue'
import SystemOnlineUsers from '../views/SystemOnlineUsers.vue'
import SystemChangePassword from '../views/SystemChangePassword.vue'
import IssueMy from '../views/IssueMy.vue'
import IssueMonitor from '../views/IssueMonitor.vue'
import IssueAssigned from '../views/IssueAssigned.vue'
import IssueRoles from '../views/IssueRoles.vue'
import IssueCreatePage from '../views/IssueCreatePage.vue'
import IssueDetailPage from '../views/IssueDetailPage.vue'
import SystemPermission from '../views/SystemPermission.vue'

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
      { path: '', redirect: '/home' },
      { path: 'home', name: 'HomeDashboard', component: HomeDashboard },
      { path: 'container/list', name: 'Container', component: ContainerList },
      { path: 'container/dashboard', name: 'Dashboard', component: Dashboard },
      { path: 'performance/coefficients', name: 'PerformanceCoefficient', component: PerformanceCoefficient },
      { path: 'performance/employee', name: 'PerformanceEmployee', component: PerformanceEmployee },
      { path: 'otb/dashboard', name: 'OtbDashboard', component: OtbDashboard },
      { path: 'otb/category', name: 'OtbCategory', component: OtbCategory },
      { path: 'otb/brand', name: 'OtbBrand', component: OtbBrand },
      { path: 'otb/brand-category', name: 'OtbBrandCategory', component: OtbBrandCategory },
      { path: 'otb/sales-curve', name: 'OtbSalesCurve', component: OtbSalesCurve },
      { path: 'otb/replenishment', name: 'OtbReplenishment', component: OtbReplenishment },
      { path: 'bu/definition', name: 'BuDefinition', component: BuDefinition },
      { path: 'bu/brand', name: 'BuBrandRelation', component: BuBrandRelation },
      { path: 'system/login-log', name: 'SystemLoginLog', component: SystemLoginLog },
      { path: 'system/online-users', name: 'SystemOnlineUsers', component: SystemOnlineUsers },
      { path: 'system/change-password', name: 'SystemChangePassword', component: SystemChangePassword },
      { path: 'issue/my', name: 'IssueMy', component: IssueMy },
      { path: 'issue/monitor', name: 'IssueMonitor', component: IssueMonitor },
      { path: 'issue/assigned', name: 'IssueAssigned', component: IssueAssigned },
      { path: 'issue/roles', name: 'IssueRoles', component: IssueRoles },
      { path: 'issue/create', name: 'IssueCreate', component: IssueCreatePage },
      { path: 'issue/detail/:id', name: 'IssueDetail', component: IssueDetailPage },
      { path: 'system/permission', name: 'SystemPermission', component: SystemPermission },
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
