<template>
  <div class="planner-home">
    <section class="planner-hero">
      <div class="hero-copy">
        <p class="eyebrow">Trip Planner Style Demo</p>
        <h1>规划一条更像成品的旅行路线</h1>
        <p class="hero-text">
          支持多个城市，按顺序自动拆分天数，并结合天气、景点、酒店与预算生成结构化行程。
        </p>
      </div>

      <div class="planner-panel">
        <a-form :model="formData" layout="vertical" @finish="handleSubmit">
          <div class="input-block">
            <label class="block-label">目的地</label>
            <div class="city-input-row">
              <a-input
                v-model:value="cityInput"
                size="large"
                placeholder="输入城市，回车添加，例如：上海"
                @pressEnter="addCity"
              />
              <a-button size="large" @click="addCity">添加</a-button>
            </div>
            <div class="city-tags">
              <a-tag
                v-for="city in formData.cities"
                :key="city"
                closable
                class="city-tag"
                @close="removeCity(city)"
              >
                {{ city }}
              </a-tag>
            </div>
            <p class="field-help">按输入顺序规划，第一阶段不做自动调序。</p>
          </div>

          <div class="grid-row">
            <a-form-item class="grid-item" label="开始日期" required>
              <a-date-picker
                v-model:value="formData.start_date"
                style="width: 100%"
                size="large"
                placeholder="选择开始日期"
              />
            </a-form-item>
            <a-form-item class="grid-item" label="结束日期" required>
              <a-date-picker
                v-model:value="formData.end_date"
                style="width: 100%"
                size="large"
                placeholder="选择结束日期"
              />
            </a-form-item>
            <div class="trip-days-card">
              <span class="trip-days-label">旅行天数</span>
              <strong>{{ formData.travel_days }}</strong>
            </div>
          </div>

          <div class="input-block">
            <label class="block-label">旅行风格</label>
            <a-checkbox-group v-model:value="formData.preferences" class="style-grid">
              <a-checkbox v-for="option in preferenceOptions" :key="option" :value="option" class="style-chip">
                {{ option }}
              </a-checkbox>
            </a-checkbox-group>
          </div>

          <a-collapse ghost class="advanced-panel">
            <a-collapse-panel key="advanced" header="更多偏好">
              <div class="advanced-grid">
                <a-form-item label="交通方式">
                  <a-select v-model:value="formData.transportation" size="large">
                    <a-select-option value="公共交通">公共交通</a-select-option>
                    <a-select-option value="自驾">自驾</a-select-option>
                    <a-select-option value="步行">步行</a-select-option>
                    <a-select-option value="混合">混合</a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item label="住宿偏好">
                  <a-select v-model:value="formData.accommodation" size="large">
                    <a-select-option value="经济型酒店">经济型酒店</a-select-option>
                    <a-select-option value="舒适型酒店">舒适型酒店</a-select-option>
                    <a-select-option value="豪华酒店">豪华酒店</a-select-option>
                    <a-select-option value="民宿">民宿</a-select-option>
                  </a-select>
                </a-form-item>
              </div>
              <a-form-item label="额外要求">
                <a-textarea
                  v-model:value="formData.free_text_input"
                  :rows="4"
                  placeholder="例如：希望节奏轻松一些，第二天少走路，酒店尽量靠近地铁。"
                />
              </a-form-item>
            </a-collapse-panel>
          </a-collapse>

          <a-button type="primary" html-type="submit" :loading="loading" size="large" block class="submit-button">
            {{ loading ? '正在生成行程...' : '开始规划' }}
          </a-button>

          <div v-if="loading" class="loading-box">
            <a-progress :percent="loadingProgress" status="active" />
            <span>{{ loadingStatus }}</span>
          </div>
        </a-form>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import type { Dayjs } from 'dayjs'
import { generateTripPlan } from '@/services/api'
import type { TripFormData } from '@/types'

const router = useRouter()
const loading = ref(false)
const loadingProgress = ref(0)
const loadingStatus = ref('')
const cityInput = ref('')
const preferenceOptions = ['历史文化', '自然风光', '美食', '购物', '艺术', '休闲']

type PlannerFormState = Omit<TripFormData, 'start_date' | 'end_date'> & {
  start_date: Dayjs | null
  end_date: Dayjs | null
}

const formData = reactive<PlannerFormState>({
  city: '',
  cities: [],
  start_date: null,
  end_date: null,
  travel_days: 1,
  transportation: '公共交通',
  accommodation: '舒适型酒店',
  preferences: ['历史文化'],
  free_text_input: ''
})

watch([() => formData.start_date, () => formData.end_date], ([start, end]) => {
  if (!start || !end) return
  const days = end.diff(start, 'day') + 1
  if (days <= 0) {
    message.warning('结束日期不能早于开始日期')
    formData.end_date = null
    return
  }
  if (days > 30) {
    message.warning('旅行天数不能超过30天')
    formData.end_date = null
    return
  }
  formData.travel_days = days
})

const addCity = () => {
  const value = cityInput.value.trim()
  if (!value) return
  if (formData.cities.includes(value)) {
    message.warning('城市已存在')
    cityInput.value = ''
    return
  }
  formData.cities.push(value)
  formData.city = formData.cities[0] || ''
  cityInput.value = ''
}

const removeCity = (city: string) => {
  formData.cities = formData.cities.filter(item => item !== city)
  formData.city = formData.cities[0] || ''
}

const handleSubmit = async () => {
  if (!formData.start_date || !formData.end_date) {
    message.error('请选择开始和结束日期')
    return
  }
  if (!formData.cities.length) {
    message.error('请至少添加一个城市')
    return
  }
  if (formData.cities.length > formData.travel_days) {
    message.error('城市数量不能超过旅行天数')
    return
  }

  loading.value = true
  loadingProgress.value = 0
  loadingStatus.value = '正在初始化规划上下文...'

  const progressInterval = setInterval(() => {
    if (loadingProgress.value >= 92) return
    loadingProgress.value += 8
    if (loadingProgress.value <= 24) loadingStatus.value = '正在拆分多城市行程...'
    else if (loadingProgress.value <= 48) loadingStatus.value = '正在搜索景点与天气...'
    else if (loadingProgress.value <= 72) loadingStatus.value = '正在推荐酒店与门票...'
    else loadingStatus.value = '正在合成最终行程...'
  }, 450)

  try {
    const requestData: TripFormData = {
      city: formData.cities[0],
      cities: [...formData.cities],
      start_date: formData.start_date.format('YYYY-MM-DD'),
      end_date: formData.end_date.format('YYYY-MM-DD'),
      travel_days: formData.travel_days,
      transportation: formData.transportation,
      accommodation: formData.accommodation,
      preferences: [...formData.preferences],
      free_text_input: formData.free_text_input
    }
    const response = await generateTripPlan(requestData)
    clearInterval(progressInterval)
    loadingProgress.value = 100
    loadingStatus.value = '行程生成完成'

    if (!response.success || !response.data) {
      message.error(response.message || '生成失败')
      return
    }

    sessionStorage.setItem('tripPlan', JSON.stringify(response.data))
    message.success('旅行计划生成成功')
    setTimeout(() => router.push('/result'), 300)
  } catch (error: any) {
    clearInterval(progressInterval)
    message.error(error.message || '生成旅行计划失败')
  } finally {
    setTimeout(() => {
      loading.value = false
      loadingProgress.value = 0
      loadingStatus.value = ''
    }, 800)
  }
}
</script>

<style scoped>
.planner-home {
  min-height: calc(100vh - 128px);
  background: linear-gradient(180deg, #f8fafc 0%, #eef3ff 100%);
  padding: 32px;
}

.planner-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(420px, 640px);
  gap: 32px;
  align-items: start;
  max-width: 1320px;
  margin: 0 auto;
}

.hero-copy {
  padding-top: 32px;
}

.eyebrow {
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 600;
  color: #5b6b8a;
  text-transform: uppercase;
}

.hero-copy h1 {
  margin: 0 0 16px;
  font-size: 52px;
  line-height: 1.05;
  color: #0f172a;
}

.hero-text {
  max-width: 560px;
  margin: 0;
  font-size: 18px;
  line-height: 1.7;
  color: #4a5568;
}

.planner-panel {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.08);
  padding: 24px;
  backdrop-filter: blur(8px);
}

.input-block {
  margin-bottom: 24px;
}

.block-label {
  display: block;
  margin-bottom: 10px;
  color: #1e293b;
  font-size: 14px;
  font-weight: 600;
}

.city-input-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
}

.city-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 40px;
  margin-top: 12px;
}

.city-tag {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 13px;
}

.field-help {
  margin: 8px 0 0;
  font-size: 12px;
  color: #64748b;
}

.grid-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) 140px;
  gap: 16px;
  align-items: end;
}

.grid-item {
  margin-bottom: 0;
}

.trip-days-card {
  height: 88px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.trip-days-card strong {
  font-size: 32px;
  color: #0f172a;
}

.trip-days-label {
  font-size: 13px;
  color: #64748b;
}

.style-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

:deep(.style-chip) {
  margin-inline-start: 0;
  padding: 10px 14px;
  background: #f8fafc;
  border: 1px solid #dbe3ef;
  border-radius: 999px;
}

.advanced-panel {
  margin-bottom: 24px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fbfdff;
}

.advanced-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.submit-button {
  height: 52px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
}

.loading-box {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

@media (max-width: 1080px) {
  .planner-hero {
    grid-template-columns: 1fr;
  }

  .hero-copy {
    padding-top: 0;
  }
}

@media (max-width: 768px) {
  .planner-home {
    padding: 20px 16px 28px;
  }

  .hero-copy h1 {
    font-size: 36px;
  }

  .grid-row,
  .advanced-grid,
  .city-input-row {
    grid-template-columns: 1fr;
  }
}
</style>
