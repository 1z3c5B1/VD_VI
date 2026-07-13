const API_BASE = window.location.origin;
let authToken = localStorage.getItem('vdai_token');
let chatHistory = [];
let lastImageResult = null;
let lastVideoResult = null;

// ---- Auth ----
function switchAuthTab(tab) {
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('#authScreen form').forEach(f => f.classList.add('hidden'));
    document.querySelector(`.auth-tab[data-auth="${tab}"]`).classList.add('active');
    document.getElementById(tab === 'login' ? 'loginForm' : 'registerForm').classList.remove('hidden');
    document.getElementById('authError').textContent = '';
    document.getElementById('regError').textContent = '';
}

async function authLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    document.getElementById('authError').textContent = '';
    document.getElementById('authLoader').classList.remove('hidden');
    try {
        const res = await fetch(`${API_BASE}/api/login`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail);
        authToken = data.token;
        localStorage.setItem('vdai_token', authToken);
        document.getElementById('authScreen').style.display = 'none';
        document.getElementById('userName').textContent = data.username;
        document.getElementById('userAvatar').textContent = data.username.charAt(0).toUpperCase();
        document.getElementById('userMenu').classList.add('active');
    } catch (err) {
        document.getElementById('authError').textContent = err.message;
    } finally {
        document.getElementById('authLoader').classList.add('hidden');
    }
}

async function authRegister() {
    const username = document.getElementById('regUsername').value.trim();
    const password = document.getElementById('regPassword').value;
    document.getElementById('regError').textContent = '';
    document.getElementById('authLoader').classList.remove('hidden');
    try {
        const res = await fetch(`${API_BASE}/api/register`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail);
        authToken = data.token;
        localStorage.setItem('vdai_token', authToken);
        document.getElementById('authScreen').style.display = 'none';
        document.getElementById('userName').textContent = data.username;
        document.getElementById('userAvatar').textContent = data.username.charAt(0).toUpperCase();
        document.getElementById('userMenu').classList.add('active');
    } catch (err) {
        document.getElementById('regError').textContent = err.message;
    } finally {
        document.getElementById('authLoader').classList.add('hidden');
    }
}

function authLogout() {
    localStorage.removeItem('vdai_token');
    authToken = null;
    document.getElementById('authScreen').style.display = 'flex';
    document.getElementById('userMenu').classList.remove('active');
    document.getElementById('loginUsername').value = '';
    document.getElementById('loginPassword').value = '';
}

async function checkAuth() {
    if (!authToken) return;
    try {
        const res = await fetch(`${API_BASE}/api/me`, {
            headers: { 'Authorization': `Bearer ${authToken}` },
        });
        if (!res.ok) throw new Error('invalid');
        const data = await res.json();
        document.getElementById('authScreen').style.display = 'none';
        document.getElementById('userName').textContent = data.username;
        document.getElementById('userAvatar').textContent = data.username.charAt(0).toUpperCase();
        document.getElementById('userMenu').classList.add('active');
    } catch {
        localStorage.removeItem('vdai_token');
        authToken = null;
    }
}

// ---- Tab switching ----
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
        if (btn.dataset.tab === 'gallery') loadGallery();
    });
});

// ---- Image mode switch ----
function switchImageMode(mode) {
    document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.mode-tab[data-mode="${mode}"]`).classList.add('active');
    document.getElementById('imageGenerateMode').classList.toggle('hidden', mode !== 'generate');
    document.getElementById('imageEditMode').classList.toggle('hidden', mode !== 'edit');
    document.getElementById('imagePlaceholder').classList.remove('hidden');
    document.getElementById('imageResultContent').classList.add('hidden');
}

// ---- Style tags ----
document.querySelectorAll('.style-tag').forEach(tag => {
    tag.addEventListener('click', () => {
        if (tag.classList.contains('active')) return;
        document.querySelectorAll('.style-tag').forEach(t => t.classList.remove('active'));
        tag.classList.add('active');
    });
});

// ---- Image Upload ----
function onEditFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { alert('Файл слишком большой (макс 10MB)'); return; }
    const reader = new FileReader();
    reader.onload = e => {
        document.getElementById('uploadArea').classList.add('hidden');
        const preview = document.getElementById('editPreview');
        preview.classList.remove('hidden');
        document.getElementById('editPreviewImg').src = e.target.result;
    };
    reader.readAsDataURL(file);
}

function clearEditFile() {
    document.getElementById('editFileInput').value = '';
    document.getElementById('editPreview').classList.add('hidden');
    document.getElementById('uploadArea').classList.remove('hidden');
}

// ---- Health check ----
async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/api/health`);
        const data = await res.json();
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        dot.className = `status-dot ${data.status === 'ok' ? 'online' : 'offline'}`;
        text.textContent = data.status === 'ok' ? 'Сервер работает' : 'Ошибка сервера';
    } catch {
        document.getElementById('statusDot').className = 'status-dot offline';
        document.getElementById('statusText').textContent = 'Сервер недоступен';
    }
}

// ---- Image Generation ----
function getActiveStyle() {
    const active = document.querySelector('.style-tag.active');
    return active ? active.dataset.style || '' : '';
}

async function generateImage() {
    const prompt = document.getElementById('prompt').value.trim();
    if (!prompt) return alert('Введите промпт');

    const loader = document.getElementById('imageLoader');
    const placeholder = document.getElementById('imagePlaceholder');
    const result = document.getElementById('imageResultContent');
    const btn = document.getElementById('generateImageBtn');

    loader.classList.remove('hidden');
    placeholder.classList.add('hidden');
    result.classList.add('hidden');
    btn.disabled = true;
    btn.textContent = 'Генерация...';

    try {
        const style = getActiveStyle();
        const fullPrompt = style ? `${prompt}, ${style}` : prompt;
        const seed = parseInt(document.getElementById('seed').value) || null;

        const res = await fetch(`${API_BASE}/api/generate/image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: fullPrompt,
                negative_prompt: document.getElementById('negativePrompt').value || null,
                width: parseInt(document.getElementById('width').value),
                height: parseInt(document.getElementById('height').value),
                guidance_scale: parseFloat(document.getElementById('guidance').value) || 7.5,
                num_inference_steps: parseInt(document.getElementById('steps').value) || 30,
                seed: seed || null,
            }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Ошибка генерации');
        }

        const data = await res.json();
        lastImageResult = data;

        const img = document.getElementById('generatedImage');
        img.src = `${API_BASE}${data.url}?t=${Date.now()}`;

        document.getElementById('imageInfo').textContent =
            `Seed: ${data.seed} | ${document.getElementById('width').value}x${document.getElementById('height').value} | ${document.getElementById('steps').value} шагов`;

        loader.classList.add('hidden');
        result.classList.remove('hidden');
    } catch (err) {
        loader.classList.add('hidden');
        placeholder.classList.remove('hidden');
        alert('Ошибка: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '✦ Сгенерировать';
    }
}

function downloadImage() {
    if (!lastImageResult) return;
    const a = document.createElement('a');
    a.href = `${API_BASE}${lastImageResult.url}`;
    a.download = lastImageResult.filename;
    a.click();
}

function regenerateImage() {
    if (lastImageResult && lastImageResult.seed) {
        document.getElementById('seed').value = lastImageResult.seed + 1;
    }
    generateImage();
}

// ---- Image Edit ----
async function editImage() {
    const fileInput = document.getElementById('editFileInput');
    const previewImg = document.getElementById('editPreviewImg');
    const editPrompt = document.getElementById('editPrompt').value.trim();

    if (!fileInput.files.length) return alert('Загрузи фото сначала');
    if (!editPrompt) return alert('Напиши, что изменить');

    const loader = document.getElementById('imageLoader');
    const placeholder = document.getElementById('imagePlaceholder');
    const result = document.getElementById('imageResultContent');
    const btn = document.getElementById('editImageBtn');
    const loaderText = document.getElementById('imageLoaderText');

    loader.classList.remove('hidden');
    placeholder.classList.add('hidden');
    result.classList.add('hidden');
    btn.disabled = true;
    btn.textContent = 'Редактирую...';
    loaderText.textContent = 'Редактирование изображения...';

    try {
        const res = await fetch(`${API_BASE}/api/generate/edit-image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image_data: previewImg.src,
                prompt: editPrompt,
                width: parseInt(document.getElementById('width').value) || 1024,
                height: parseInt(document.getElementById('height').value) || 1024,
            }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Ошибка редактирования');
        }

        const data = await res.json();
        lastImageResult = data;

        const img = document.getElementById('generatedImage');
        img.src = `${API_BASE}${data.url}?t=${Date.now()}`;

        document.getElementById('imageInfo').textContent =
            `Редактирование: "${editPrompt}"`;

        loader.classList.add('hidden');
        result.classList.remove('hidden');
    } catch (err) {
        loader.classList.add('hidden');
        placeholder.classList.remove('hidden');
        alert('Ошибка: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '✎ Редактировать';
        loaderText.textContent = 'Генерация...';
    }
}

// ---- Video Generation ----
async function generateVideo() {
    const prompt = document.getElementById('videoPrompt').value.trim();
    if (!prompt) return alert('Введите промпт');

    const loader = document.getElementById('videoLoader');
    const placeholder = document.getElementById('videoPlaceholder');
    const result = document.getElementById('videoResultContent');
    const btn = document.querySelector('#tab-video .btn-primary');

    loader.classList.remove('hidden');
    placeholder.classList.add('hidden');
    result.classList.add('hidden');
    btn.disabled = true;
    btn.textContent = 'Генерация видео...';

    try {
        const seed = parseInt(document.getElementById('videoSeed').value) || null;
        const duration = parseInt(document.getElementById('videoDuration').value) || 6;
        const fps = parseInt(document.getElementById('videoFps').value) || 10;

        const res = await fetch(`${API_BASE}/api/generate/video`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, seed: seed || null, duration, fps }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Ошибка генерации видео');
        }

        const data = await res.json();
        lastVideoResult = data;

        const video = document.getElementById('generatedVideo');
        video.querySelector('source').src = `${API_BASE}${data.url}?t=${Date.now()}`;
        video.load();

        document.getElementById('videoInfo').textContent =
            `${data.duration} сек | ${data.frames} кадров | ${data.fps} FPS | Seed: ${data.seed}`;

        loader.classList.add('hidden');
        result.classList.remove('hidden');
    } catch (err) {
        loader.classList.add('hidden');
        placeholder.classList.remove('hidden');
        alert('Ошибка: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '▶ Сгенерировать видео';
    }
}

function downloadVideo() {
    if (!lastVideoResult) return;
    const a = document.createElement('a');
    a.href = `${API_BASE}${lastVideoResult.url}`;
    a.download = lastVideoResult.filename;
    a.click();
}

// ---- Chat ----
async function sendChat() {
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg) return;

    input.value = '';
    addChatMsg('user', msg, 'Вы');
    chatHistory.push({ role: 'user', content: msg });

    const loader = document.getElementById('chatLoader');
    loader.classList.remove('hidden');

    try {
        const model = document.getElementById('chatModel').value;
        const headers = { 'Content-Type': 'application/json' };
        if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

        const res = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST', headers,
            body: JSON.stringify({
                message: msg,
                history: chatHistory.slice(0, -1),
                model,
                system_prompt: "Ты VD AI — умный и дружелюбный ИИ-ассистент. Отвечай кратко и полезно. Твоё имя VD AI."
            }),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка');

        const modelLabel = document.getElementById('chatModel').selectedOptions[0].text;
        addChatMsg('assistant', data.reply, modelLabel);
        chatHistory.push({ role: 'assistant', content: data.reply });
    } catch (err) {
        addChatMsg('assistant', 'Ошибка: ' + err.message, 'Система');
    } finally {
        loader.classList.add('hidden');
    }
}

function addChatMsg(role, text, label) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    const labelHtml = label ? `<div class="msg-label">${escapeHtml(label)}</div>` : '';
    div.innerHTML = `${labelHtml}<div class="msg-content">${escapeHtml(text)}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ---- Gallery ----
async function loadGallery() {
    const grid = document.getElementById('galleryGrid');
    grid.innerHTML = '<p class="gallery-empty">Загрузка...</p>';

    try {
        const res = await fetch(`${API_BASE}/api/gallery`);
        const data = await res.json();

        if (!data.files || data.files.length === 0) {
            grid.innerHTML = '<p class="gallery-empty">Пока нет сгенерированных файлов</p>';
            return;
        }

        grid.innerHTML = '';
        data.files.forEach(file => {
            const item = document.createElement('div');
            item.className = 'gallery-item';

            if (file.type === 'video') {
                item.innerHTML = `
                    <video src="${API_BASE}${file.url}" muted loop></video>
                    <div class="gallery-item-overlay">▶ Видео</div>
                `;
                item.addEventListener('click', () => {
                    const vid = item.querySelector('video');
                    vid.paused ? vid.play() : vid.pause();
                });
            } else {
                const img = document.createElement('img');
                img.src = `${API_BASE}${file.url}`;
                img.loading = 'lazy';
                item.appendChild(img);
                const overlay = document.createElement('div');
                overlay.className = 'gallery-item-overlay';
                overlay.textContent = file.filename;
                item.appendChild(overlay);
                item.addEventListener('click', () => window.open(`${API_BASE}${file.url}`, '_blank'));
            }
            grid.appendChild(item);
        });
    } catch {
        grid.innerHTML = '<p class="gallery-empty">Сервер недоступен</p>';
    }
}

// ---- Init ----
checkAuth();
checkHealth();
setInterval(checkHealth, 30000);
