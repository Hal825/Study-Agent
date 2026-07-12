// ============================================================
// 多格式导出工具函数
// ============================================================

/** 剥离 Markdown 语法 → 纯文本 */
const P = String.fromCharCode(124) // '|' — 避免触发 Tailwind CSS 扫描
const DASHES = String.fromCharCode(45).repeat(1) // '-' — 辅助构造

export function markdownToPlainText(md: string): string {
  const tableSep = new RegExp('^[-:' + P + '\\s]+$', 'gm')
  const hrSep = new RegExp(DASHES + '{3,}', 'g')
  const pipeSep = new RegExp(P, 'g')

  return md
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/`{1,3}[^`]*`{1,3}/g, '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/!\[.*?\]\(.*?\)/g, '')
    .replace(/^>\s+/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '• ')
    .replace(/^\s*\d+\.\s+/gm, '')
    .replace(pipeSep, ' ')
    .replace(tableSep, '')
    .replace(hrSep, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

/** 通过后端 reportlab 引擎生成专业 PDF 并下载 */
export async function downloadAsPDF(content: string, filename: string = 'notes'): Promise<void> {
  const response = await fetch('/api/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, format: 'pdf' }),
  })

  if (!response.ok) {
    throw new Error('PDF 导出失败')
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${filename}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}

/** 调用后端生成 DOCX 并触发下载 */
export async function downloadAsDocx(content: string, filename: string = 'notes'): Promise<void> {
  const response = await fetch('/api/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, format: 'docx' }),
  })

  if (!response.ok) {
    throw new Error('DOCX 导出失败')
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${filename}.docx`
  a.click()
  URL.revokeObjectURL(url)
}
