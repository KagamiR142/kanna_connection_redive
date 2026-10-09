import { createRouter, createWebHashHistory, RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/store/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/change-password',
    name: 'ChangePassword',
    component: () => import('@/views/ChangePassword.vue'),
    meta: { title: '修改密码', requiresAuth: true }
  },
  {
    path: '/',
    component: () => import('@/layout/Layout.vue'),
    redirect: '/home',
    children: [
      {
        path: 'home',
        name: 'Home',
        component: () => import('@/views/Home.vue'),
        meta: { title: '首页', icon: 'HomeFilled', requiresAuth: true }
      },
      {
        path: 'clan/panel/:groupId?',
        name: 'Panel',
        component: () => import('@/views/Panel.vue'),
        meta: { title: '会战面板', icon: 'DataAnalysis', requiresAuth: true }
      },
      {
        path: 'clan/profile/:groupId?',
        name: 'Profile',
        component: () => import('@/views/Profile.vue'),
        meta: { title: '个人数据', icon: 'User', requiresAuth: true }
      },
      {
        path: 'clan/stats/:groupId?',
        name: 'Stats',
        component: () => import('@/views/Stats.vue'),
        meta: { title: '统计数据', icon: 'Document', requiresAuth: true }
      },
      {
        path: 'clan/admin',
        name: 'Admin',
        component: () => import('@/views/Admin.vue'),
        meta: { title: '管理运维', icon: 'Setting', requiresAuth: true, globalAdmin: true }
      },
      {
        path: 'forbidden',
        name: 'Forbidden',
        component: () => import('@/views/Forbidden.vue'),
        meta: { title: '无权访问', requiresAuth: true }
      },
      { path: 'dashboard/:groupId?', redirect: (to) => `/clan/panel/${to.params.groupId || ''}` },
      { path: 'report/:groupId?', redirect: (to) => `/clan/stats/${to.params.groupId || ''}` },
      { path: 'notice/:groupId?', redirect: (to) => `/clan/panel/${to.params.groupId || ''}` }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/home' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

function hasCookieToken() {
  try {
    return /(^|;\s*)token=/.test(document.cookie)
  } catch {
    return false
  }
}

router.beforeEach(async (to, _from, next) => {
  const title = (to.meta?.title as string) || '会战管理'
  document.title = `${title} · 环奈连结 R`

  const userStore = useUserStore()

  if (to.meta.requiresAuth === false) {
    if (userStore.isLoggedIn && userStore.userId) {
      return next('/home')
    }
    return next()
  }

  const hasLocalMark = userStore.isLoggedIn || hasCookieToken()
  if (!hasLocalMark) {
    return next({ path: '/login', query: { redirect: to.fullPath } })
  }

  if (!userStore.userId) {
    try {
      await userStore.fetchUserInfo()
    } catch (e: any) {
      const status = e?.response?.status ?? e?.status
      if (status === 401) return false as any
    }
  }

  if (to.meta.globalAdmin && !userStore.isGlobalAdmin) {
    return next('/forbidden')
  }

  next()
})

export default router
