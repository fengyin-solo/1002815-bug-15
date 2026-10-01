import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '@/views/Dashboard.vue'
const Plot = () => import('@/views/plot/index.vue')
const Tree = () => import('@/views/tree/index.vue')
const Shrub = () => import('@/views/shrub/index.vue')
const Lawn = () => import('@/views/lawn/index.vue')
const Flower = () => import('@/views/flower/index.vue')
const Pest = () => import('@/views/pest/index.vue')
const Irrigation = () => import('@/views/irrigation/index.vue')
const IrrigationDetail = () => import('@/views/irrigation/detail.vue')
const Fertilize = () => import('@/views/fertilize/index.vue')
const Prune = () => import('@/views/prune/index.vue')
const Patrol = () => import('@/views/patrol/index.vue')
const Weed = () => import('@/views/weed/index.vue')
const Support = () => import('@/views/support/index.vue')
const Transplant = () => import('@/views/transplant/index.vue')
const Facility = () => import('@/views/facility/index.vue')
const Equipment = () => import('@/views/equipment/index.vue')
const Seedling = () => import('@/views/seedling/index.vue')
const Waterbody = () => import('@/views/waterbody/index.vue')
const Code = () => import('@/views/code/index.vue')
const Complaint = () => import('@/views/complaint/index.vue')
const Seasonplan = () => import('@/views/seasonplan/index.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/plot', name: 'plot', component: Plot },
    { path: '/tree', name: 'tree', component: Tree },
    { path: '/shrub', name: 'shrub', component: Shrub },
    { path: '/lawn', name: 'lawn', component: Lawn },
    { path: '/flower', name: 'flower', component: Flower },
    { path: '/pest', name: 'pest', component: Pest },
    { path: '/irrigation', name: 'irrigation', component: Irrigation },
    { path: '/irrigation/:id', name: 'irrigation-detail', component: IrrigationDetail },
    { path: '/fertilize', name: 'fertilize', component: Fertilize },
    { path: '/prune', name: 'prune', component: Prune },
    { path: '/patrol', name: 'patrol', component: Patrol },
    { path: '/weed', name: 'weed', component: Weed },
    { path: '/support', name: 'support', component: Support },
    { path: '/transplant', name: 'transplant', component: Transplant },
    { path: '/facility', name: 'facility', component: Facility },
    { path: '/equipment', name: 'equipment', component: Equipment },
    { path: '/seedling', name: 'seedling', component: Seedling },
    { path: '/waterbody', name: 'waterbody', component: Waterbody },
    { path: '/code', name: 'code', component: Code },
    { path: '/complaint', name: 'complaint', component: Complaint },
    { path: '/seasonplan', name: 'seasonplan', component: Seasonplan },
  ],
})

export default router
