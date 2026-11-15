import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'upload',
    component: () => import('../views/UploadView.vue')
  },
  {
    path: '/editor',
    name: 'editor',
    component: () => import('../views/EditorView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
