<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { marked } from 'marked'
import katex from 'katex'
import { editText } from '../services/api'

const props = defineProps({
  pages: { type: Array, required: true },
  currentPageIndex: { type: Number, default: 0 },
  currentSelection: { type: Object, default: null },
  provider: { type: String, default: 'openai' },
})

const emit = defineEmits(['close', 'apply'])

const SCOPE_SELECTION = 'selection'
const SCOPE_PAGE = 'page'
const SCOPE_ALL = 'all'

const hasSelection = computed(
  () => !!props.currentSelection && (props.currentSelection.text || '').length > 0
)

const scope = ref(hasSelection.value ? SCOPE_SELECTION : SCOPE_PAGE)
const targetPageIndex = ref(
  Math.min(Math.max(props.currentPageIndex || 0, 0), Math.max(props.pages.length - 1, 0))
)
const instruction = ref('')
const isLoading = ref(false)
const globalError = ref(null)

const results = ref([])
const previewMode = ref('editor')

function renderLatex(text) {
  if (!text) return ''

  let result = text.replace(/\$\$([\s\S]+?)\$\$/g, (match, latex) => {
    try {
      return katex.renderToString(latex.trim(), { displayMode: true, throwOnError: false })
    } catch {
      return `<span style="color: #f87171;">${match}</span>`
    }
  })

  result = result.replace(/(?<!\$)\$(?!\$)([^\$\n]+?)\$(?!\$)/g, (match, latex) => {
    try {
      return katex.renderToString(latex.trim(), { displayMode: false, throwOnError: false })
    } catch {
      return `<span style="color: #f87171;">${match}</span>`
    }
  })

  return result
}

function renderMarkdown(text) {
  return marked.parse(renderLatex(text || ''))
}

const hasAnySuccess = computed(() => results.value.some((r) => r.ok))
const hasAnyFailure = computed(() => results.value.some((r) => !r.ok))

function onKeydown(e) {
  if (e.key === 'Escape' && !isLoading.value) emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
})

async function runOne({ pageIndex, text, from = null, to = null }) {
  try {
    const data = await editText({
      text,
      instruction: instruction.value,
      provider: props.provider,
    })
    return {
      ok: true,
      pageIndex,
      from,
      to,
      oldText: text,
      newText: data.edited_text || '',
    }
  } catch (err) {
    return {
      ok: false,
      pageIndex,
      from,
      to,
      oldText: text,
      error: err.message || 'Edit failed',
      code: err.code,
    }
  }
}

async function generatePreview() {
  if (!instruction.value.trim() || isLoading.value) return
  isLoading.value = true
  globalError.value = null
  results.value = []
  try {
    if (scope.value === SCOPE_SELECTION && hasSelection.value) {
      const sel = props.currentSelection
      const r = await runOne({
        pageIndex: sel.pageIndex,
        text: sel.text,
        from: sel.from,
        to: sel.to,
      })
      results.value = [r]
    } else if (scope.value === SCOPE_PAGE) {
      const idx = targetPageIndex.value
      const page = props.pages[idx]
      const r = await runOne({
        pageIndex: idx,
        text: page?.markdown || '',
      })
      results.value = [r]
    } else if (scope.value === SCOPE_ALL) {
      const settled = await Promise.allSettled(
        props.pages.map((page, idx) =>
          runOne({ pageIndex: idx, text: page?.markdown || '' })
        )
      )
      results.value = settled.map((s, idx) =>
        s.status === 'fulfilled'
          ? s.value
          : {
              ok: false,
              pageIndex: idx,
              from: null,
              to: null,
              oldText: props.pages[idx]?.markdown || '',
              error: s.reason?.message || 'Unknown error',
            }
      )
    }
  } finally {
    isLoading.value = false
  }
}

function acceptAll() {
  const payload = results.value
    .filter((r) => r.ok)
    .map((r) => ({
      pageIndex: r.pageIndex,
      from: r.from,
      to: r.to,
      newText: r.newText,
    }))
  if (payload.length === 0) return
  emit('apply', payload)
}

function rejectPreview() {
  results.value = []
}
</script>

<template>
  <Teleport to="body">
    <div
      @click.self="!isLoading && emit('close')"
      style="position: fixed; inset: 0; background: rgba(0,0,0,0.85); display: flex; align-items: center; justify-content: center; z-index: 10001; padding: 24px;"
    >
      <div style="background: var(--color-surface); border-radius: 12px; width: min(900px, 95vw); max-height: 92vh; display: flex; flex-direction: column; overflow: hidden; border: 1px solid var(--color-border);">
        <div style="padding: 14px 18px; border-bottom: 1px solid var(--color-border); display: flex; justify-content: space-between; align-items: center;">
          <div>
            <h3 style="margin: 0; font-size: 16px; font-weight: 600; color: var(--color-text-primary);">Edit with AI</h3>
            <p style="margin: 4px 0 0; font-size: 12px; color: var(--color-text-muted);">Describe what to change. Preview before applying.</p>
          </div>
          <button
            @click="emit('close')"
            :disabled="isLoading"
            style="background: none; border: none; cursor: pointer; color: var(--color-text-muted); font-size: 22px; line-height: 1; padding: 4px 10px; border-radius: 6px;"
          >&times;</button>
        </div>

        <div style="padding: 16px 18px; overflow-y: auto; flex: 1;">
          <div style="margin-bottom: 14px;">
            <label style="display: block; font-size: 12px; font-weight: 500; color: var(--color-text-muted); margin-bottom: 6px;">Scope</label>
            <div style="display: flex; flex-direction: column; gap: 6px;">
              <label :style="{ display: 'flex', alignItems: 'center', gap: '8px', cursor: hasSelection ? 'pointer' : 'not-allowed', opacity: hasSelection ? 1 : 0.5 }">
                <input type="radio" :value="SCOPE_SELECTION" v-model="scope" :disabled="!hasSelection" />
                <span style="font-size: 14px; color: var(--color-text-primary);">
                  Selected text
                  <span v-if="hasSelection" style="color: var(--color-text-muted);">({{ currentSelection.text.length }} chars)</span>
                  <span v-else style="color: var(--color-text-muted);">(nothing selected)</span>
                </span>
              </label>
              <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                <input type="radio" :value="SCOPE_PAGE" v-model="scope" />
                <span style="font-size: 14px; color: var(--color-text-primary); display: flex; align-items: center; gap: 8px;">
                  Current page
                  <select
                    v-model.number="targetPageIndex"
                    :disabled="scope !== SCOPE_PAGE"
                    style="padding: 4px 8px; font-size: 13px; background: var(--color-bg); color: var(--color-text-primary); border: 1px solid var(--color-border); border-radius: 4px;"
                  >
                    <option v-for="(p, i) in pages" :key="i" :value="i">Page {{ i + 1 }}</option>
                  </select>
                </span>
              </label>
              <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                <input type="radio" :value="SCOPE_ALL" v-model="scope" />
                <span style="font-size: 14px; color: var(--color-text-primary);">All pages ({{ pages.length }})</span>
              </label>
            </div>
          </div>

          <div style="margin-bottom: 14px;">
            <label style="display: block; font-size: 12px; font-weight: 500; color: var(--color-text-muted); margin-bottom: 6px;">Instruction (max 500)</label>
            <textarea
              v-model="instruction"
              maxlength="500"
              placeholder="e.g. Fix spelling and grammar. Keep LaTeX blocks intact."
              style="width: 100%; min-height: 80px; padding: 10px; font-size: 14px; font-family: inherit; background-color: var(--color-bg); color: var(--color-text-primary); border: 1px solid var(--color-border); border-radius: 6px; resize: vertical; outline: none; box-sizing: border-box;"
            ></textarea>
            <div style="text-align: right; font-size: 12px; color: var(--color-text-muted); margin-top: 2px;">{{ instruction.length }} / 500</div>
          </div>

          <div v-if="globalError" style="margin-bottom: 14px; padding: 10px; border-radius: 6px; background-color: rgba(239, 68, 68, 0.1); color: #f87171; font-size: 14px;">
            {{ globalError }}
          </div>

          <div style="display: flex; gap: 8px; justify-content: flex-end; margin-bottom: 16px;">
            <button
              @click="emit('close')"
              :disabled="isLoading"
              style="padding: 8px 16px; font-size: 14px; border-radius: 6px; background: transparent; border: 1px solid var(--color-border); cursor: pointer; color: var(--color-text-primary);"
            >Cancel</button>
            <button
              @click="generatePreview"
              :disabled="isLoading || !instruction.trim()"
              :style="{
                padding: '8px 16px',
                fontSize: '14px',
                borderRadius: '6px',
                border: 'none',
                cursor: isLoading || !instruction.trim() ? 'not-allowed' : 'pointer',
                backgroundColor: 'var(--color-accent)',
                color: 'white',
                opacity: isLoading || !instruction.trim() ? 0.6 : 1
              }"
            >{{ isLoading ? 'Generating...' : 'Generate preview' }}</button>
          </div>

          <div v-if="results.length > 0">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
              <h4 style="margin: 0; font-size: 14px; font-weight: 600; color: var(--color-text-primary);">Preview</h4>
              <div style="display: flex; align-items: center; gap: 4px; background-color: var(--color-bg); border-radius: 8px; padding: 4px;">
                <button
                  @click="previewMode = 'editor'"
                  :style="{
                    padding: '6px 12px',
                    fontSize: '13px',
                    borderRadius: '6px',
                    border: 'none',
                    cursor: 'pointer',
                    backgroundColor: previewMode === 'editor' ? 'var(--color-accent)' : 'transparent',
                    color: previewMode === 'editor' ? 'white' : 'var(--color-text-muted)'
                  }"
                >
                  Editor
                </button>
                <button
                  @click="previewMode = 'preview'"
                  :style="{
                    padding: '6px 12px',
                    fontSize: '13px',
                    borderRadius: '6px',
                    border: 'none',
                    cursor: 'pointer',
                    backgroundColor: previewMode === 'preview' ? 'var(--color-accent)' : 'transparent',
                    color: previewMode === 'preview' ? 'white' : 'var(--color-text-muted)'
                  }"
                >
                  Preview
                </button>
              </div>
            </div>
            <div
              v-for="(r, i) in results"
              :key="i"
              :style="{
                marginBottom: '12px',
                padding: '10px',
                borderRadius: '8px',
                border: '1px solid ' + (r.ok ? 'var(--color-border)' : '#f87171'),
                background: 'var(--color-bg)'
              }"
            >
              <div style="font-size: 13px; font-weight: 600; color: var(--color-text-primary); margin-bottom: 6px;">
                Page {{ r.pageIndex + 1 }}
                <span v-if="!r.ok" style="color: #f87171; font-weight: 400; margin-left: 6px;">— {{ r.error }}</span>
              </div>
              <div v-if="r.ok" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                <div>
                  <div style="font-size: 11px; color: var(--color-text-muted); margin-bottom: 4px;">Old</div>
                  <pre v-if="previewMode === 'editor'" style="margin: 0; padding: 8px; font-family: ui-monospace, monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; background: var(--color-surface); border-radius: 4px; max-height: 300px; overflow: auto;">{{ r.oldText }}</pre>
                  <div v-else class="markdown-preview" style="max-height: 300px; overflow: auto; padding: 8px; background: var(--color-surface); border-radius: 4px;" v-html="renderMarkdown(r.oldText)"></div>
                </div>
                <div>
                  <div style="font-size: 11px; color: var(--color-text-muted); margin-bottom: 4px;">New</div>
                  <pre v-if="previewMode === 'editor'" style="margin: 0; padding: 8px; font-family: ui-monospace, monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; background: var(--color-surface); border-radius: 4px; max-height: 300px; overflow: auto;">{{ r.newText }}</pre>
                  <div v-else class="markdown-preview" style="max-height: 300px; overflow: auto; padding: 8px; background: var(--color-surface); border-radius: 4px;" v-html="renderMarkdown(r.newText)"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="results.length > 0" style="padding: 12px 18px; border-top: 1px solid var(--color-border); display: flex; justify-content: flex-end; gap: 8px; background: var(--color-surface);">
          <button
            @click="rejectPreview"
            :disabled="isLoading"
            style="padding: 8px 16px; font-size: 14px; border-radius: 6px; background: transparent; border: 1px solid var(--color-border); cursor: pointer; color: var(--color-text-primary);"
          >Reject</button>
          <button
            @click="acceptAll"
            :disabled="isLoading || !hasAnySuccess"
            :style="{
              padding: '8px 16px',
              fontSize: '14px',
              borderRadius: '6px',
              border: 'none',
              cursor: isLoading || !hasAnySuccess ? 'not-allowed' : 'pointer',
              backgroundColor: 'var(--color-accent)',
              color: 'white',
              opacity: isLoading || !hasAnySuccess ? 0.6 : 1
            }"
          >{{ hasAnyFailure && hasAnySuccess ? 'Accept successful pages only' : 'Accept' }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
