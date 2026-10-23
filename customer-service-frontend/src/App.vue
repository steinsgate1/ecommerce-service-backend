<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'

// 渲染机器人回复中的 Markdown（加粗/列表等）；禁用 HTML 防注入
const md = new MarkdownIt({ html: false, breaks: true, linkify: false })

function renderMarkdown(text) {
  return md.render(String(text ?? ''))
}

const senderId = ref('u1001')
const draftMessage = ref('')
const isSending = ref(false)
const errorMessage = ref('')
const messages = ref([])
const messagesContainer = ref(null)

const orders = ref([])
const products = ref([])
const isLoadingSidebar = ref(false)
const sidebarError = ref('')
const activeTab = ref('orders')

const failedImages = ref({})

// 前端模拟节点流（仅展示，不接后端 SSE）
const thinkingNodes = ref([])
let thinkingTimers = []

const chatEndpoint = computed(() => '/api/chat')
const chatHistoryEndpoint = computed(
  () => `/api/chat/history?sender_id=${encodeURIComponent(senderId.value.trim())}`
)
const commerceOrdersEndpoint = computed(
  () => `/commerce/users/${encodeURIComponent(senderId.value.trim())}/orders`
)
const commerceProductsEndpoint = computed(
  () => `/commerce/users/${encodeURIComponent(senderId.value.trim())}/products`
)

function createBaseMessage(role) {
  return {
    id: crypto.randomUUID(),
    role,
    buttons: [],
  }
}

function appendUserText(text) {
  messages.value.push({
    ...createBaseMessage('user'),
    type: 'text',
    text,
  })
}

function appendUserObject(objectType, payload) {
  messages.value.push({
    ...createBaseMessage('user'),
    type: 'object',
    objectType,
    payload,
  })
}

function appendBotMessages(botMessages) {
  for (const message of botMessages) {
    appendMessage('bot', message)
  }
}

function appendMessage(role, message) {
  if (role === 'divider') {
    messages.value.push({
      ...createBaseMessage('divider'),
      type: 'divider',
      text: message.text ?? '以上为历史消息',
    })
    return
  }

  if (message.object) {
    messages.value.push({
      ...createBaseMessage(role),
      type: 'object',
      objectType: message.object.type,
      payload: message.object,
    })
  } else {
    messages.value.push({
      ...createBaseMessage(role),
      type: 'text',
      text: message.text ?? '',
    })
  }
}

function setHistoryMessages(historyMessages) {
  messages.value = []
  for (const message of historyMessages) {
    const role = ['user', 'bot', 'divider'].includes(message.role) ? message.role : 'bot'
    appendMessage(role, message)
  }
}

async function scrollToBottom() {
  await nextTick()
  const container = messagesContainer.value
  if (!container) {
    return
  }
  container.scrollTop = container.scrollHeight
}

watch(
  () => messages.value.length,
  async () => {
    await scrollToBottom()
  }
)

function resetConversation() {
  messages.value = []
  errorMessage.value = ''
}

function formatAmount(amount) {
  const numericAmount = Number(amount)
  if (Number.isNaN(numericAmount)) {
    return '¥0.00'
  }
  return `¥${numericAmount.toFixed(2)}`
}

function priceParts(amount) {
  const numericAmount = Number(amount)
  if (Number.isNaN(numericAmount)) {
    return { int: '0', dec: '00' }
  }
  const [int, dec] = numericAmount.toFixed(2).split('.')
  return { int, dec }
}

function buildImageUrl(title) {
  const keyword = (title ?? '商品').toString().slice(0, 30)
  const prompt = encodeURIComponent(`${keyword} 商品主图，纯白背景，电商摄影`)
  return `https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=${prompt}&image_size=square`
}

function imageError(key) {
  failedImages.value = { ...failedImages.value, [key]: true }
}

function formatOrderSummary(order) {
  return order.status ? `订单状态：${order.status}` : '订单'
}

function formatProductSummary(product) {
  if (product.description) {
    return product.description
  }
  if (product.attributes?.price) {
    return `商品价格：${formatAmount(product.attributes.price)}`
  }
  return '商品信息'
}

function getObjectTitle(message) {
  const payload = message.payload ?? {}
  if (payload.title) {
    return payload.title
  }
  return message.objectType === 'order' ? '订单对象' : '商品对象'
}

function getObjectIdentifier(message) {
  const payload = message.payload ?? {}
  const id = payload.order_id ?? payload.product_id ?? payload.id
  const label = message.objectType === 'order' ? '订单号' : '商品号'
  return id ? `${label}：${id}` : label
}

function getObjectSummary(message) {
  const payload = message.payload ?? {}
  if (message.objectType === 'order') {
    const status = payload.status ?? payload.attributes?.status
    return status ? `订单状态：${status}` : '订单'
  }
  return formatProductSummary(payload)
}

function getObjectAmount(message) {
  const payload = message.payload ?? {}
  const amount = message.objectType === 'order'
    ? payload.amount ?? payload.attributes?.amount
    : payload.price ?? payload.attributes?.price
  return formatAmount(amount)
}

async function fetchSidebarData() {
  const currentSenderId = senderId.value.trim()
  orders.value = []
  products.value = []
  sidebarError.value = ''

  if (!currentSenderId) {
    return
  }

  isLoadingSidebar.value = true
  try {
    const [ordersResponse, productsResponse] = await Promise.all([
      fetch(commerceOrdersEndpoint.value),
      fetch(commerceProductsEndpoint.value),
    ])

    const [ordersPayload, productsPayload] = await Promise.all([
      ordersResponse.json(),
      productsResponse.json(),
    ])

    if (!ordersResponse.ok) {
      throw new Error(ordersPayload.detail || '加载订单列表失败。')
    }
    if (!productsResponse.ok) {
      throw new Error(productsPayload.detail || '加载商品列表失败。')
    }

    orders.value = Array.isArray(ordersPayload?.data?.orders) ? ordersPayload.data.orders : []
    products.value = Array.isArray(productsPayload?.data?.products) ? productsPayload.data.products : []
  } catch (error) {
    sidebarError.value = error instanceof Error ? error.message : '加载右侧列表失败。'
  } finally {
    isLoadingSidebar.value = false
  }
}

async function fetchChatHistory() {
  const currentSenderId = senderId.value.trim()
  if (!currentSenderId) {
    messages.value = []
    return
  }

  try {
    const response = await fetch(chatHistoryEndpoint.value)
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.detail || '加载历史消息失败。')
    }
    if (currentSenderId === senderId.value.trim()) {
      setHistoryMessages(Array.isArray(data?.messages) ? data.messages : [])
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载历史消息失败。'
  }
}

function startThinking(payload) {
  stopThinking()
  const firstLabel = payload.object
    ? payload.object.type === 'order'
      ? '解析订单对象'
      : '解析商品对象'
    : '意图识别'

  thinkingNodes.value = [
    { label: firstLabel, status: 'active' },
    { label: '检索业务信息', status: 'pending' },
    { label: '生成回复', status: 'pending' },
  ]

  // 模拟节点流推进节奏；若响应提前返回，由 stopThinking 兜底清理
  thinkingTimers.push(setTimeout(() => advanceThinking(1), 500))
  thinkingTimers.push(setTimeout(() => advanceThinking(2), 1100))
  scrollToBottom()
}

function advanceThinking(index) {
  if (!thinkingNodes.value.length) {
    return
  }
  thinkingNodes.value = thinkingNodes.value.map((node, i) => ({
    ...node,
    status: i < index ? 'done' : i === index ? 'active' : 'pending',
  }))
  scrollToBottom()
}

function stopThinking() {
  for (const timer of thinkingTimers) {
    clearTimeout(timer)
  }
  thinkingTimers = []
  thinkingNodes.value = []
}

async function sendPayload(payload) {
  if (isSending.value) {
    return
  }

  errorMessage.value = ''
  isSending.value = true
  startThinking(payload)

  try {
    const response = await fetch(chatEndpoint.value, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        sender_id: senderId.value.trim(),
        ...payload,
      }),
    })

    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.detail || '请求失败。')
    }

    appendBotMessages(data.messages ?? [])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '请求失败。'
  } finally {
    stopThinking()
    isSending.value = false
  }
}

async function sendTextMessage() {
  const text = draftMessage.value.trim()
  const currentSenderId = senderId.value.trim()

  if (!currentSenderId) {
    errorMessage.value = '请先输入 sender_id。'
    return
  }
  if (!text) {
    return
  }

  draftMessage.value = ''
  appendUserText(text)
  await sendPayload({ text })
}

async function sendOrder(order) {
  const currentSenderId = senderId.value.trim()
  if (!currentSenderId) {
    errorMessage.value = '请先输入 sender_id。'
    return
  }

  appendUserObject('order', order)
  await sendPayload({
    object: {
      type: 'order',
      id: order.order_id,
      title: order.title,
      attributes: {
        status: order.status,
        amount: order.amount,
        created_at: order.created_at,
      },
    },
  })
}

async function sendProduct(product) {
  const currentSenderId = senderId.value.trim()
  if (!currentSenderId) {
    errorMessage.value = '请先输入 sender_id。'
    return
  }

  appendUserObject('product', product)
  await sendPayload({
    object: {
      type: 'product',
      id: product.product_id,
      title: product.title,
      attributes: {
        price: product.price,
      },
    },
  })
}

watch(
  () => senderId.value.trim(),
  async (value, previousValue) => {
    if (value === previousValue) {
      return
    }

    resetConversation()
    if (!value) {
      orders.value = []
      products.value = []
      return
    }
    await Promise.all([fetchSidebarData(), fetchChatHistory()])
  }
)

onMounted(async () => {
  await Promise.all([fetchSidebarData(), fetchChatHistory()])
})
</script>

<template>
  <div class="app-shell">
    <div class="jd-topbar">
      <div class="jd-container topbar-inner">
        <div class="topbar-left">
          <span class="topbar-loc">北京</span>
        </div>
        <div class="topbar-right">
          <span>你好，请登录</span>
          <a href="javascript:void(0)">免费注册</a>
          <i class="topbar-sep"></i>
          <a href="javascript:void(0)">我的订单</a>
          <i class="topbar-sep"></i>
          <a href="javascript:void(0)">个人中心</a>
          <i class="topbar-sep"></i>
          <a href="javascript:void(0)">会员中心</a>
          <i class="topbar-sep"></i>
          <a href="javascript:void(0)">客户服务</a>
        </div>
      </div>
    </div>

    <header class="jd-header">
      <div class="jd-container header-inner">
        <div class="jd-logo">
          <span class="jd-logo-mark">应答有言</span>
          <span class="jd-logo-sub">客服</span>
        </div>
        <div class="jd-search">
          <input type="text" readonly placeholder="搜索商品、订单、客服问题" />
          <button type="button" class="jd-search-btn">搜索</button>
        </div>
        <div class="jd-cart">
          <span class="jd-cart-icon">🛒</span>
          <span>我的购物车</span>
        </div>
      </div>
    </header>

    <main class="jd-container workspace">
      <div class="chat-card">
        <header class="chat-header">
          <div class="chat-title">在线客服</div>
          <div class="chat-status">
            <i class="dot"></i>
            <span>人工客服在线中</span>
          </div>
        </header>

        <section class="controls">
          <label class="field">
            <span class="field-label">sender_id</span>
            <div class="field-row">
              <input v-model="senderId" type="text" placeholder="u1001" />
              <button
                type="button"
                class="btn btn-outline"
                :disabled="isLoadingSidebar"
                @click="fetchSidebarData"
              >
                {{ isLoadingSidebar ? '加载中...' : '刷新对象列表' }}
              </button>
            </div>
          </label>
        </section>

        <section ref="messagesContainer" class="messages">
          <div v-if="messages.length === 0" class="empty-state">
            <p class="empty-title">欢迎咨询应答有言</p>
            <p class="empty-desc">
              可以先发一句「你好」「我要退款」「这件衣服适合什么季节」，
              也可以直接点击右侧订单或商品，把业务对象送入后端会话。
            </p>
          </div>

          <template v-for="message in messages" :key="message.id">
            <div v-if="message.type === 'divider'" class="history-divider">
              <span>{{ message.text }}</span>
            </div>

            <article v-else class="message" :class="message.role">
              <div class="avatar" :class="`avatar-${message.role}`">
                {{ message.role === 'user' ? '我' : '应' }}
              </div>

              <div class="message-main">
                <div class="meta">
                  {{ message.role === 'user' ? '我' : '应答有言' }}
                </div>

                <p
                  v-if="message.type === 'text' && message.role === 'bot'"
                  class="bubble"
                  v-html="renderMarkdown(message.text)"
                ></p>

                <p v-else-if="message.type === 'text'" class="bubble">{{ message.text }}</p>

                <div v-else class="object-card" :class="`object-card-${message.objectType}`">
                  <div class="object-thumb">
                    <img
                      v-if="!failedImages[message.id]"
                      :src="buildImageUrl(getObjectTitle(message))"
                      :alt="getObjectTitle(message)"
                      @error="imageError(message.id)"
                    />
                    <div v-else class="thumb-fallback">暂无图片</div>
                  </div>
                  <div class="object-info">
                    <div class="object-badge">
                      {{ message.objectType === 'order' ? '订单' : '商品' }}
                    </div>
                    <div class="object-title">{{ getObjectTitle(message) }}</div>
                    <div class="object-meta">{{ getObjectIdentifier(message) }}</div>
                    <div class="object-meta">{{ getObjectSummary(message) }}</div>
                    <div class="object-price">{{ getObjectAmount(message) }}</div>
                  </div>
                </div>
              </div>
            </article>
          </template>

          <article v-if="thinkingNodes.length" class="message bot">
            <div class="avatar avatar-bot">应</div>
            <div class="message-main">
              <div class="meta">应答有言</div>
              <div class="thinking-card">
                <div
                  v-for="node in thinkingNodes"
                  :key="node.label"
                  class="thinking-node"
                  :class="node.status"
                >
                  <span class="node-icon">
                    <i v-if="node.status === 'done'" class="node-check">✓</i>
                    <i v-else-if="node.status === 'active'" class="node-spinner"></i>
                    <i v-else class="node-dot"></i>
                  </span>
                  <span class="node-label">{{ node.label }}</span>
                  <span v-if="node.status === 'active'" class="node-ellipsis">
                    <i>.</i><i>.</i><i>.</i>
                  </span>
                </div>
              </div>
            </div>
          </article>
        </section>

        <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>

        <form class="composer" @submit.prevent="sendTextMessage">
          <input
            v-model="draftMessage"
            type="text"
            placeholder="请输入咨询内容..."
            :disabled="isSending"
          />
          <button type="submit" class="btn btn-primary" :disabled="isSending || !draftMessage.trim()">
            {{ isSending ? '发送中...' : '发送' }}
          </button>
        </form>
      </div>

      <aside class="sidebar">
        <div class="sidebar-header">
          <h2>我的业务对象</h2>
          <span class="sidebar-sub">点击卡片即可发送给客服</span>
        </div>

        <div class="tabs">
          <button
            type="button"
            class="tab-button"
            :class="{ active: activeTab === 'orders' }"
            @click="activeTab = 'orders'"
          >
            我的订单
          </button>
          <button
            type="button"
            class="tab-button"
            :class="{ active: activeTab === 'products' }"
            @click="activeTab = 'products'"
          >
            浏览的商品
          </button>
        </div>

        <p v-if="sidebarError" class="sidebar-error">{{ sidebarError }}</p>

        <div v-if="activeTab === 'orders'" class="sidebar-list">
          <div v-if="!orders.length && !isLoadingSidebar" class="sidebar-empty">
            暂无订单数据
          </div>

          <article v-for="order in orders" :key="order.order_id" class="sidebar-card">
            <div class="card-thumb">
              <img
                v-if="!failedImages[order.order_id]"
                :src="buildImageUrl(order.title)"
                :alt="order.title"
                @error="imageError(order.order_id)"
              />
              <div v-else class="thumb-fallback">暂无图片</div>
            </div>
            <div class="card-main">
              <div class="card-title">{{ order.title }}</div>
              <div class="card-meta">订单号：{{ order.order_id }}</div>
              <div class="card-meta">
                状态：<span class="status-tag">{{ order.status }}</span>
              </div>
              <div class="card-foot">
                <span class="price">
                  <i>¥</i><b>{{ priceParts(order.amount).int }}</b><em>.{{ priceParts(order.amount).dec }}</em>
                </span>
                <button
                  type="button"
                  class="btn btn-primary btn-sm"
                  :disabled="isSending"
                  @click="sendOrder(order)"
                >
                  发送订单
                </button>
              </div>
            </div>
          </article>
        </div>

        <div v-else class="sidebar-list">
          <div v-if="!products.length && !isLoadingSidebar" class="sidebar-empty">
            暂无商品数据
          </div>

          <article v-for="product in products" :key="product.product_id" class="sidebar-card">
            <div class="card-thumb">
              <img
                v-if="!failedImages[product.product_id]"
                :src="buildImageUrl(product.title)"
                :alt="product.title"
                @error="imageError(product.product_id)"
              />
              <div v-else class="thumb-fallback">暂无图片</div>
            </div>
            <div class="card-main">
              <div class="card-title">{{ product.title }}</div>
              <div class="card-meta">商品号：{{ product.product_id }}</div>
              <div class="card-foot">
                <span class="price">
                  <i>¥</i><b>{{ priceParts(product.price).int }}</b><em>.{{ priceParts(product.price).dec }}</em>
                </span>
                <button
                  type="button"
                  class="btn btn-primary btn-sm"
                  :disabled="isSending"
                  @click="sendProduct(product)"
                >
                  发送商品
                </button>
              </div>
            </div>
          </article>
        </div>
      </aside>
    </main>
  </div>
</template>

<style scoped>
:global(*) {
  box-sizing: border-box;
}

:global(body) {
  margin: 0;
  font-family: "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", Arial, sans-serif;
  background: #f4f4f4;
  color: #333;
  font-size: 12px;
}

:global(button),
:global(input) {
  font: inherit;
}

#app {
  min-height: 100vh;
}

.app-shell {
  height: 100dvh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #f4f4f4;
}

.jd-container {
  width: min(1360px, 100%);
  margin: 0 auto;
  padding: 0 16px;
}

/* ---------- 顶部工具条 ---------- */
.jd-topbar {
  height: 30px;
  flex: 0 0 auto;
  background: #f1f1f1;
  border-bottom: 1px solid #e8e8e8;
  color: #999;
  font-size: 12px;
}

.topbar-inner {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.topbar-loc {
  color: #999;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.topbar-right a {
  color: #666;
  text-decoration: none;
}

.topbar-right a:hover {
  color: #e1251b;
}

.topbar-sep {
  width: 1px;
  height: 12px;
  background: #ddd;
}

/* ---------- 头部 ---------- */
.jd-header {
  height: 92px;
  flex: 0 0 auto;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.header-inner {
  height: 100%;
  display: flex;
  align-items: center;
  gap: 40px;
}

.jd-logo {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex: 0 0 auto;
}

.jd-logo-mark {
  display: inline-block;
  padding: 6px 10px;
  background: #e1251b;
  border-radius: 6px;
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 2px;
  line-height: 1;
}

.jd-logo-sub {
  color: #e1251b;
  font-size: 14px;
  font-weight: 700;
}

.jd-search {
  flex: 1 1 auto;
  max-width: 560px;
  display: flex;
  height: 36px;
  border: 2px solid #e1251b;
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}

.jd-search input {
  flex: 1;
  min-width: 0;
  padding: 0 12px;
  border: none;
  outline: none;
  color: #333;
  font-size: 13px;
}

.jd-search input::placeholder {
  color: #bbb;
}

.jd-search-btn {
  flex: 0 0 auto;
  width: 82px;
  border: none;
  background: #e1251b;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}

.jd-search-btn:hover {
  background: #c81623;
}

.jd-cart {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  color: #e1251b;
  background: #fff;
  font-size: 13px;
}

.jd-cart-icon {
  font-size: 15px;
}

/* ---------- 主体布局 ---------- */
.workspace {
  flex: 1 1 auto;
  min-height: 0;
  padding-top: 12px;
  padding-bottom: 16px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 12px;
}

.chat-card,
.sidebar {
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
}

/* ---------- 会话卡片 ---------- */
.chat-header {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 44px;
  padding: 0 16px;
  background: #e1251b;
  color: #fff;
}

.chat-title {
  font-size: 15px;
  font-weight: 700;
}

.chat-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.9);
}

.chat-status .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #7ef29a;
}

.controls {
  flex: 0 0 auto;
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  color: #999;
  font-size: 12px;
}

.field-row {
  display: flex;
  gap: 8px;
}

.field input,
.composer input {
  width: 100%;
  min-width: 0;
  height: 34px;
  padding: 0 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #fff;
  color: #333;
  font-size: 13px;
  outline: none;
}

.field input:focus,
.composer input:focus {
  border-color: #e1251b;
}

/* ---------- 消息区 ---------- */
.messages {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: #fafafa;
}

.empty-state {
  margin: auto;
  max-width: 460px;
  text-align: center;
  color: #999;
  line-height: 1.8;
}

.empty-title {
  margin: 0 0 8px;
  color: #333;
  font-size: 14px;
  font-weight: 700;
}

.empty-desc {
  margin: 0;
  font-size: 13px;
}

.history-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #bbb;
  font-size: 12px;
}

.history-divider::before,
.history-divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: #e8e8e8;
}

.history-divider span {
  padding: 2px 10px;
  border-radius: 10px;
  background: #f1f1f1;
}

.message {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.message.user {
  flex-direction: row-reverse;
}

.message-main {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: min(76%, 640px);
}

.message.user .message-main {
  align-items: flex-end;
}

.avatar {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
}

.avatar-bot {
  background: #e1251b;
}

.avatar-user {
  background: #b0b0b0;
}

.meta {
  font-size: 12px;
  color: #bbb;
}

.bubble {
  margin: 0;
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.message.bot .bubble {
  background: #fff;
  border: 1px solid #e8e8e8;
  color: #333;
  /* Markdown 已用 <br> 处理换行，关闭 pre-wrap 避免双重换行 */
  white-space: normal;
}

/* markdown-it 输出元素的排版修正 */
.message.bot .bubble :deep(p) {
  margin: 0;
}

.message.bot .bubble :deep(ul),
.message.bot .bubble :deep(ol) {
  margin: 4px 0;
  padding-left: 20px;
}

.message.bot .bubble :deep(code) {
  padding: 1px 4px;
  border-radius: 4px;
  background: #f4f4f4;
  font-size: 12px;
}

.message.user .bubble {
  background: #e1251b;
  border: 1px solid #e1251b;
  color: #fff;
}

/* ---------- 对象卡片 ---------- */
.object-card {
  display: flex;
  gap: 10px;
  width: 300px;
  max-width: 100%;
  padding: 10px;
  border: 1px solid #e8e8e8;
  border-radius: 10px;
  background: #fff;
  text-align: left;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.object-card:hover {
  border-color: #e1251b;
  box-shadow: 0 2px 8px rgba(225, 37, 27, 0.08);
}

.object-thumb,
.card-thumb {
  flex: 0 0 auto;
  width: 68px;
  height: 68px;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  background: #fafafa;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.object-thumb img,
.card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.thumb-fallback {
  color: #ccc;
  font-size: 11px;
}

.object-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.object-badge {
  width: fit-content;
  padding: 1px 6px;
  border: 1px solid #e1251b;
  border-radius: 4px;
  color: #e1251b;
  font-size: 11px;
  line-height: 16px;
}

.object-title {
  font-size: 13px;
  line-height: 1.5;
  color: #333;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.object-meta {
  font-size: 12px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.object-price {
  color: #e1251b;
  font-size: 14px;
  font-weight: 700;
}

/* ---------- 节点流（thinking） ---------- */
.thinking-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 180px;
  padding: 10px 14px;
  border: 1px solid #e8e8e8;
  border-radius: 10px;
  background: #fff;
}

.thinking-node {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  line-height: 1.4;
  color: #bbb;
  transition: color 0.2s ease;
}

.thinking-node.active {
  color: #e1251b;
}

.thinking-node.done {
  color: #999;
}

.node-icon {
  width: 14px;
  height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.node-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  border: 1px solid #d8d8d8;
}

.node-check {
  font-style: normal;
  font-size: 12px;
  font-weight: 700;
  color: #4caf50;
}

.node-spinner {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid rgba(225, 37, 27, 0.2);
  border-top-color: #e1251b;
  animation: node-spin 0.8s linear infinite;
}

@keyframes node-spin {
  to {
    transform: rotate(360deg);
  }
}

.node-ellipsis {
  display: inline-flex;
  gap: 2px;
  color: #e1251b;
}

.node-ellipsis i {
  font-style: normal;
  animation: node-blink 1.2s infinite;
}

.node-ellipsis i:nth-child(2) {
  animation-delay: 0.2s;
}

.node-ellipsis i:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes node-blink {
  0%,
  60%,
  100% {
    opacity: 0.2;
  }
  30% {
    opacity: 1;
  }
}

/* ---------- 输入区 ---------- */
.error-message,
.sidebar-error {
  flex: 0 0 auto;
  margin: 0;
  padding: 8px 16px;
  color: #e1251b;
  font-size: 12px;
}

.composer {
  flex: 0 0 auto;
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #f0f0f0;
  background: #fff;
}

.composer input {
  height: 38px;
}

/* ---------- 按钮 ---------- */
.btn {
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.btn-primary {
  border: 1px solid #e1251b;
  background: #e1251b;
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: #c81623;
  border-color: #c81623;
}

.btn-outline {
  border: 1px solid #ddd;
  background: #fff;
  color: #333;
}

.btn-outline:hover:not(:disabled) {
  border-color: #e1251b;
  color: #e1251b;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.composer .btn-primary {
  flex: 0 0 auto;
  min-width: 88px;
}

.controls .btn-outline {
  flex: 0 0 auto;
  min-width: 112px;
  height: 34px;
}

.btn-sm {
  height: 26px;
  padding: 0 12px;
  font-size: 12px;
}

/* ---------- 侧栏 ---------- */
.sidebar-header {
  flex: 0 0 auto;
  padding: 12px 16px 0;
}

.sidebar-header h2 {
  margin: 0;
  color: #333;
  font-size: 14px;
  font-weight: 700;
}

.sidebar-sub {
  display: block;
  margin-top: 4px;
  color: #999;
  font-size: 12px;
}

.tabs {
  flex: 0 0 auto;
  display: flex;
  gap: 20px;
  padding: 0 16px;
  border-bottom: 1px solid #e8e8e8;
}

.tab-button {
  position: relative;
  padding: 10px 2px;
  border: none;
  background: transparent;
  color: #666;
  font-size: 13px;
  cursor: pointer;
}

.tab-button:hover {
  color: #e1251b;
}

.tab-button.active {
  color: #e1251b;
  font-weight: 700;
}

.tab-button.active::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 2px;
  background: #e1251b;
}

.sidebar-list {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 12px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sidebar-empty {
  margin: auto;
  color: #bbb;
  font-size: 13px;
}

.sidebar-card {
  display: flex;
  gap: 10px;
  padding: 10px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #fff;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.sidebar-card:hover {
  border-color: #e1251b;
  box-shadow: 0 2px 8px rgba(225, 37, 27, 0.08);
}

.card-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.card-title {
  font-size: 13px;
  line-height: 1.5;
  color: #333;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  font-size: 12px;
  color: #999;
}

.status-tag {
  color: #e1251b;
}

.card-foot {
  margin-top: 2px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.price {
  color: #e1251b;
  font-family: Verdana, Arial, sans-serif;
  white-space: nowrap;
}

.price i {
  font-style: normal;
  font-size: 12px;
  margin-right: 1px;
}

.price b {
  font-size: 16px;
  font-weight: 700;
}

.price em {
  font-style: normal;
  font-size: 12px;
}

/* ---------- 滚动条 ---------- */
.messages::-webkit-scrollbar,
.sidebar-list::-webkit-scrollbar {
  width: 6px;
}

.messages::-webkit-scrollbar-thumb,
.sidebar-list::-webkit-scrollbar-thumb {
  background: #dcdcdc;
  border-radius: 3px;
}

.messages::-webkit-scrollbar-thumb:hover,
.sidebar-list::-webkit-scrollbar-thumb:hover {
  background: #c4c4c4;
}

/* ---------- 响应式 ---------- */
@media (max-width: 1180px) {
  /* 外壳仍为 100dvh 不滚动，工作区内部滚动，
     聊天卡固定高度（消息区内滚），侧栏随工作区滚动可见 */
  .workspace {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }

  .chat-card {
    flex: 0 0 auto;
    height: 70vh;
  }

  .sidebar {
    flex: 0 0 auto;
    height: auto;
    overflow: visible;
  }

  .sidebar-list {
    max-height: 420px;
  }
}

@media (max-width: 720px) {
  .jd-topbar,
  .jd-cart {
    display: none;
  }

  .header-inner {
    gap: 16px;
  }

  .jd-search {
    max-width: none;
  }

  .message-main {
    max-width: 100%;
  }

  .object-card {
    width: 100%;
  }
}
</style>
