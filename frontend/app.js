// API Base URL
const API_URL = 'http://localhost:8000';

// Generate session ID
const SESSION_ID = 'session_' + Math.random().toString(36).substr(2, 9);
document.getElementById('sessionId').textContent = SESSION_ID;

// Query input
const queryInput = document.getElementById('queryInput');
queryInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        searchAuto();
    }
});

// Global state
let lastSearchResults = null;
let lastQuery = '';

// V4 Search
async function searchAuto() {
    const query = queryInput.value.trim();
    if (!query) {
        alert('Vui lòng nhập câu hỏi');
        return;
    }

    lastQuery = query;

    // Show loading
    showDocsLoading();
    clearAnswer();

    try {
        const response = await fetch(`${API_URL}/search/v4`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                top_k: 10,
                session_id: SESSION_ID
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        lastSearchResults = data;
        renderDocs(data);
    } catch (error) {
        console.error('Search error:', error);
        showDocsError(error.message);
    }
}

// V4 Search với RAG Answer (streaming)
async function searchWithAnswer() {
    const query = queryInput.value.trim();
    if (!query) {
        alert('Vui lòng nhập câu hỏi');
        return;
    }

    lastQuery = query;

    // Show loading
    showDocsLoading();
    showAnswerLoading();

    try {
        const response = await fetch(`${API_URL}/search/v4/answer`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                top_k: 10,
                session_id: SESSION_ID
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        // Read SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let answerText = '';
        let metadata = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(6));

                    if (data.type === 'metadata') {
                        metadata = data;
                        // Render docs từ V4 metadata
                        renderDocsFromV4Metadata(metadata);
                    } else if (data.type === 'chunk') {
                        answerText += data.content;
                        renderAnswer(answerText, false);
                    } else if (data.type === 'citations') {
                        answerText += '\n\n' + data.content;
                        renderAnswer(answerText, true);
                    } else if (data.type === 'done') {
                        renderAnswer(answerText, true);
                    }
                }
            }
        }
    } catch (error) {
        console.error('Answer error:', error);
        showAnswerError(error.message);
        showDocsError(error.message);
    }
}

// Render docs panel (V4 response)
function renderDocs(data) {
    const panel = document.getElementById('docsPanel');
    const count = document.getElementById('docsCount');

    if (!data || !data.results || data.results.length === 0) {
        panel.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🔍</div>
                <p>Không tìm thấy kết quả phù hợp</p>
            </div>
        `;
        count.textContent = '0 results';
        return;
    }

    // Metadata V4
    let metadataHtml = '<div class="metadata">';
    metadataHtml += `<div class="metadata-row"><span class="metadata-label">Query:</span><span class="metadata-value">${escapeHtml(data.query)}</span></div>`;
    metadataHtml += `<div class="metadata-row"><span class="metadata-label">Total matched:</span><span class="metadata-value">${data.total} docs</span></div>`;
    metadataHtml += `<div class="metadata-row"><span class="metadata-label">Returned:</span><span class="metadata-value">${data.results.length} bids</span></div>`;
    metadataHtml += `<div class="metadata-row"><span class="metadata-label">Latency:</span><span class="metadata-value">${data.took_ms.toFixed(0)}ms</span></div>`;

    // Method used
    if (data.method) {
        const methodColor = data.method === 'hybrid' ? '#9b59b6' : data.method === 'filter_only' ? '#f39c12' : '#3498db';
        metadataHtml += `<div class="metadata-row"><span class="metadata-label">Method:</span><span class="badge" style="background: ${methodColor}; color: white;">${data.method}</span></div>`;
    }

    // Timing breakdown
    if (data.timings) {
        metadataHtml += `<div class="metadata-row"><span class="metadata-label">Timing:</span><span class="metadata-value">`;
        if (data.timings.llm_analysis) metadataHtml += `LLM ${data.timings.llm_analysis.toFixed(0)}ms · `;
        if (data.timings.search) metadataHtml += `Search ${data.timings.search.toFixed(0)}ms · `;
        if (data.timings.rerank) metadataHtml += `Rerank ${data.timings.rerank.toFixed(0)}ms`;
        metadataHtml += `</span></div>`;
    }

    metadataHtml += '</div>';

    // Docs
    let docsHtml = metadataHtml;
    data.results.forEach((doc, idx) => {
        docsHtml += renderDocItem(doc, idx + 1);
    });

    panel.innerHTML = docsHtml;
    count.textContent = `${data.results.length} / ${data.total} results`;
}

// Render single doc (V4 response)
function renderDocItem(doc, rank) {
    const price = doc.bid_price
        ? formatPrice(doc.bid_price)
        : 'Chưa có thông tin';

    const location = doc.locations && doc.locations.length > 0
        ? formatLocation(doc.locations)
        : 'N/A';

    const score = doc.score ? doc.score.toFixed(3) : 'N/A';

    return `
        <div class="doc-item">
            <div class="doc-header">
                <div class="doc-title">[${rank}] ${escapeHtml(doc.bid_name)}</div>
                <div class="doc-score">${score}</div>
            </div>
            <div class="doc-field"><strong>Mã số:</strong> ${escapeHtml(doc.bid_no || 'N/A')}</div>
            <div class="doc-field"><strong>Đơn vị:</strong> ${escapeHtml(doc.procuring_entity || 'N/A')}</div>
            <div class="doc-field"><strong>Giá trị:</strong> ${price}</div>
            <div class="doc-field"><strong>Địa điểm:</strong> ${location}</div>
            <div class="doc-field"><strong>Ngày đóng thầu:</strong> ${doc.bidCloseDate ? formatDate(doc.bidCloseDate) : 'N/A'}</div>
            <div class="doc-field"><strong>Ngày mở thầu:</strong> ${doc.bidOpenDate ? formatDate(doc.bidOpenDate) : 'N/A'}</div>
        </div>
    `;
}

// Format date helper
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('vi-VN');
    } catch {
        return dateStr;
    }
}

// Render docs từ V4 streaming metadata
function renderDocsFromV4Metadata(metadata) {
    const panel = document.getElementById('docsPanel');
    const count = document.getElementById('docsCount');

    let html = '<div class="metadata">';
    html += `<div class="metadata-row"><span class="metadata-label">Total matched:</span><span class="metadata-value">${metadata.total_docs}</span></div>`;
    html += `<div class="metadata-row"><span class="metadata-label">Latency:</span><span class="metadata-value">${metadata.took_ms.toFixed(0)}ms</span></div>`;

    if (metadata.method) {
        const methodColor = metadata.method === 'hybrid' ? '#9b59b6' : metadata.method === 'filter_only' ? '#f39c12' : '#3498db';
        html += `<div class="metadata-row"><span class="metadata-label">Method:</span><span class="badge" style="background: ${methodColor}; color: white;">${metadata.method}</span></div>`;
    }

    html += '</div>';

    // Render docs nếu có
    if (metadata.docs && metadata.docs.length > 0) {
        metadata.docs.forEach((doc, idx) => {
            html += renderDocItem(doc, idx + 1);
        });
        count.textContent = `${metadata.docs.length} / ${metadata.total_docs} results`;
    } else {
        html += '<p style="color: #7f8c8d; font-size: 14px; margin-top: 10px;">📄 Đang tải chi tiết gói thầu...</p>';
        count.textContent = `${metadata.total_docs} results`;
    }

    panel.innerHTML = html;
}

// Render docs từ streaming metadata (V2 - deprecated)
function renderDocsFromMetadata(metadata) {
    const panel = document.getElementById('docsPanel');
    const count = document.getElementById('docsCount');

    let html = '<div class="metadata">';
    html += `<div class="metadata-row"><span class="metadata-label">Total docs:</span><span class="metadata-value">${metadata.total_docs}</span></div>`;
    html += `<div class="metadata-row"><span class="metadata-label">Latency:</span><span class="metadata-value">${metadata.took_ms.toFixed(0)}ms</span></div>`;

    if (metadata.intent) {
        html += `<div class="metadata-row"><span class="metadata-label">Intent:</span><span class="badge badge-intent">${metadata.intent}</span></div>`;
    }

    if (metadata.methods && metadata.methods.length > 0) {
        html += `<div class="metadata-row"><span class="metadata-label">Methods:</span><span>`;
        metadata.methods.forEach(m => {
            html += `<span class="badge badge-method">${m}</span>`;
        });
        html += `</span></div>`;
    }

    if (metadata.filters && Object.keys(metadata.filters).length > 0) {
        html += `<div class="metadata-row"><span class="metadata-label">Filters:</span><span>`;
        for (const [key, value] of Object.entries(metadata.filters)) {
            html += `<span class="badge badge-filter">${key}: ${value}</span>`;
        }
        html += `</span></div>`;
    }

    html += '</div>';

    // Render docs nếu có
    if (metadata.docs && metadata.docs.length > 0) {
        metadata.docs.forEach((doc, idx) => {
            html += renderDocItem(doc, idx + 1);
        });
    } else {
        html += '<p style="color: #7f8c8d; font-size: 14px; margin-top: 10px;">📄 Đang tải chi tiết gói thầu từ RAG answer...</p>';
    }

    panel.innerHTML = html;
    count.textContent = `${metadata.total_docs} docs`;
}

// Render answer panel
function renderAnswer(text, isDone) {
    const panel = document.getElementById('answerPanel');
    const status = document.getElementById('answerStatus');

    // Simple formatting: preserve line breaks, format citations
    const formatted = text
        .split('\n')
        .map(line => {
            // Format citations [1], [2], etc.
            line = line.replace(/\[(\d+)\]/g, '<span class="citation">[$1]</span>');
            // Bold **text**
            line = line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            return line;
        })
        .join('<br>');

    panel.innerHTML = `<div class="answer-box">${formatted}</div>`;

    if (isDone) {
        status.innerHTML = '<span style="color: #27ae60;">✓ Hoàn thành</span>';
    } else {
        status.innerHTML = '<span class="loading"><span class="spinner"></span> Đang trả lời...</span>';
    }

    // Auto scroll to bottom
    panel.scrollTop = panel.scrollHeight;
}

// Show loading states
function showDocsLoading() {
    const panel = document.getElementById('docsPanel');
    panel.innerHTML = `
        <div class="empty-state">
            <div class="loading">
                <span class="spinner"></span>
                Đang tìm kiếm...
            </div>
        </div>
    `;
    document.getElementById('docsCount').textContent = 'Loading...';
}

function showAnswerLoading() {
    const panel = document.getElementById('answerPanel');
    const status = document.getElementById('answerStatus');

    panel.innerHTML = `
        <div class="empty-state">
            <div class="loading">
                <span class="spinner"></span>
                Đang tạo câu trả lời...
            </div>
        </div>
    `;
    status.innerHTML = '<span class="loading"><span class="spinner"></span> Đang xử lý...</span>';
}

// Show errors
function showDocsError(message) {
    const panel = document.getElementById('docsPanel');
    panel.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">⚠️</div>
            <p style="color: #e74c3c;">Lỗi: ${escapeHtml(message)}</p>
        </div>
    `;
    document.getElementById('docsCount').textContent = 'Error';
}

function showAnswerError(message) {
    const panel = document.getElementById('answerPanel');
    const status = document.getElementById('answerStatus');

    panel.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">⚠️</div>
            <p style="color: #e74c3c;">Lỗi: ${escapeHtml(message)}</p>
        </div>
    `;
    status.innerHTML = '<span style="color: #e74c3c;">✗ Lỗi</span>';
}

// Clear results
function clearResults() {
    queryInput.value = '';
    lastSearchResults = null;
    lastQuery = '';
    clearDocs();
    clearAnswer();
}

function clearDocs() {
    const panel = document.getElementById('docsPanel');
    panel.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <p>Chưa có kết quả tìm kiếm</p>
        </div>
    `;
    document.getElementById('docsCount').textContent = '0 results';
}

function clearAnswer() {
    const panel = document.getElementById('answerPanel');
    const status = document.getElementById('answerStatus');

    panel.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">💭</div>
            <p>Chưa có câu trả lời</p>
        </div>
    `;
    status.textContent = '';
}

// Utilities
function formatPrice(price) {
    if (price >= 1_000_000_000) {
        return `${(price / 1_000_000_000).toFixed(1)} tỷ VNĐ`;
    } else if (price >= 1_000_000) {
        return `${(price / 1_000_000).toFixed(0)} triệu VNĐ`;
    } else {
        return `${price.toLocaleString('vi-VN')} VNĐ`;
    }
}

function formatLocation(locations) {
    if (!locations || locations.length === 0) return 'N/A';

    const names = locations.slice(0, 3).map(loc => {
        if (typeof loc === 'string') return loc;
        return loc.provinceName || loc.districtName || loc.name || 'N/A';
    });

    return names.join(', ');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
