<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, drawSelection, placeholder as cmPlaceholder } from '@codemirror/view'
import { history, historyKeymap, defaultKeymap } from '@codemirror/commands'
import { search, searchKeymap } from '@codemirror/search'
import { indentUnit } from '@codemirror/language'
import { markdown } from '@codemirror/lang-markdown'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  minHeight: { type: String, default: '75vh' },
})
const emit = defineEmits(['update:modelValue', 'select', 'arrow-up-out', 'arrow-down-out'])

const hostRef = ref(null)
let view = null

function handleArrowUp(v) {
  const sel = v.state.selection.main
  if (!sel.empty) return false
  const line = v.state.doc.lineAt(sel.head)
  if (line.number !== 1) return false
  emit('arrow-up-out')
  return true
}

function handleArrowDown(v) {
  const sel = v.state.selection.main
  if (!sel.empty) return false
  const line = v.state.doc.lineAt(sel.head)
  if (line.number !== v.state.doc.lines) return false
  emit('arrow-down-out')
  return true
}

onMounted(() => {
  const state = EditorState.create({
    doc: props.modelValue,
    extensions: [
      history(),
      drawSelection(),
      EditorState.allowMultipleSelections.of(true),
      EditorView.lineWrapping,
      indentUnit.of('  '),
      markdown(),
      cmPlaceholder(props.placeholder),
      EditorView.contentAttributes.of({ spellcheck: 'false' }),
      search({ top: true }),
      keymap.of([
        { key: 'ArrowUp', run: handleArrowUp },
        { key: 'ArrowDown', run: handleArrowDown },
        { key: 'Tab', run: (v) => { v.dispatch(v.state.replaceSelection('  ')); return true } },
        ...searchKeymap,
        ...historyKeymap,
        ...defaultKeymap,
      ]),
      EditorView.updateListener.of((u) => {
        if (u.docChanged) emit('update:modelValue', u.state.doc.toString())
        if (u.selectionSet) emit('select', u.state.selection.main.head)
      }),
    ],
  })
  view = new EditorView({ state, parent: hostRef.value })
})

onBeforeUnmount(() => {
  if (view) view.destroy()
  view = null
})

watch(() => props.modelValue, (val) => {
  if (view && val !== view.state.doc.toString()) {
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: val } })
  }
})

function focus() { view?.focus() }

function focusAtStart() {
  if (!view) return
  view.dispatch({ selection: { anchor: 0 } })
  view.focus()
}

function focusAtEnd() {
  if (!view) return
  const end = view.state.doc.length
  view.dispatch({ selection: { anchor: end } })
  view.focus()
}

function insertAtCursor(text) {
  if (!view) return
  const { from, to } = view.state.selection.main
  view.dispatch({
    changes: { from, to, insert: text },
    selection: { anchor: from + text.length },
  })
  view.focus()
}

function scrollIntoView() {
  hostRef.value?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
}

function getLength() {
  return view ? view.state.doc.length : 0
}

defineExpose({ focus, focusAtStart, focusAtEnd, insertAtCursor, scrollIntoView, getLength })
</script>

<template>
  <div
    ref="hostRef"
    :style="{ '--cm-min-height': minHeight }"
    class="code-editor-host"
  ></div>
</template>

<style scoped>
.code-editor-host {
  background-color: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-sizing: border-box;
  width: 100%;
  overflow: hidden;
}
:deep(.cm-editor) { height: auto; }
:deep(.cm-scroller) { overflow: visible; }
:deep(.cm-content) {
  padding: 12px 14px;
  font-family: ui-monospace, monospace;
  font-size: 14px;
  line-height: 1.6;
  min-height: var(--cm-min-height, 75vh);
}
:deep(.cm-focused) { outline: none; }
</style>
