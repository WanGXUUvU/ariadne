/**
 * 将带 markdown 语法的文本渲染成 HTML 字符串。
 * 在 MessageList 和 ChildAgentPanel 中共用。
 */
export function formatContent(text: string | null): string {
  if (!text) return '';
  if (text.startsWith('[COMPACT_SUMMARY]')) {
    const [, ...summaryParts] = text.split(/\n\s*\n/);
    text = summaryParts.length > 0 ? summaryParts.join('\n\n') : text.replace('[COMPACT_SUMMARY]', '').trim();
  }

  let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  html = html.replace(/```([\w-]*)\n([\s\S]*?)```/g, (_match, lang, code) => {
    const cleanLang = lang ? lang.trim().toLowerCase() : 'code';
    
    // 💡 构造极奢代码头部，包含语言类型标签和带 SVG 图标的 Copy 按钮
    const headerHtml = `
      <div class="code-header">
        <span class="code-lang">${cleanLang}</span>
        <button class="copy-code-btn" type="button">
          <svg class="copy-icon" viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
          <span class="copy-text">Copy</span>
        </button>
      </div>
    `.trim();

    return `<div class="code-block">${headerHtml}<pre><code>${code}</code></pre></div>`;
  });

  html = html.replace(/((?:^\|.+\|$\n?){2,})/gm, (tableBlock) => {
    const rows = tableBlock.trim().split('\n').filter(r => r.trim());
    if (rows.length < 2) return tableBlock;
    const sepLine = rows[1];
    if (!/^\|[\s-:|]+\|$/.test(sepLine)) return tableBlock;

    const parseRow = (row: string) => row.split('|').slice(1, -1).map(cell => cell.trim());
    const headerCells = parseRow(rows[0]);
    const bodyRows = rows.slice(2);

    let tableHtml = '<div class="md-table-wrapper"><table class="md-table">';
    tableHtml += '<thead><tr>' + headerCells.map(c => `<th>${c}</th>`).join('') + '</tr></thead>';
    tableHtml += '<tbody>';
    for (const row of bodyRows) {
      const cells = parseRow(row);
      tableHtml += '<tr>' + cells.map(c => `<td>${c}</td>`).join('') + '</tr>';
    }
    tableHtml += '</tbody></table></div>';
    return tableHtml;
  });

  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

  // Convert double-quoted filenames into luxurious Asset Badges
  html = html.replace(/"([^"\s]+\.(?:txt|md|json|html|py|js|ts|css|scss|go|rs|sh|png|jpg|jpeg|gif|svg))"/g, 
    '<span class="asset-badge"><span class="asset-icon">📄</span><span class="asset-name">$1</span></span>');

  html = html.replace(/^---+$/gm, '<hr style="border:none;border-top:1px solid var(--border-dim);margin:12px 0;">');
  html = html.replace(/^### (.+)$/gm, '<div style="font-size:13px;font-weight:600;color:var(--text-primary);margin:10px 0 4px;">$1</div>');
  html = html.replace(/^## (.+)$/gm, '<div style="font-size:14px;font-weight:600;color:var(--text-primary);margin:12px 0 4px;">$1</div>');
  html = html.replace(/^# (.+)$/gm, '<div style="font-size:15px;font-weight:700;color:var(--text-primary);margin:14px 0 4px;">$1</div>');
  html = html.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/(?<!\*)\*(?!\*)([^\*]+)(?<!\*)\*(?!\*)/g, '<em>$1</em>');

  html = html.replace(/((?:^- .+$\n?)+)/gm, (block) => {
    const items = block.trim().split('\n').filter(l => l.trim().startsWith('- ')).map(l => `<li>${l.replace(/^- /, '')}</li>`);
    return `<ul class="md-list">${items.join('')}</ul>`;
  });

  html = html.replace(/((?:^\d+\. .+$\n?)+)/gm, (block) => {
    const items = block.trim().split('\n').filter(l => /^\d+\. /.test(l.trim())).map(l => `<li>${l.replace(/^\d+\. /, '')}</li>`);
    return `<ol class="md-list">${items.join('')}</ol>`;
  });

  return html;
}
