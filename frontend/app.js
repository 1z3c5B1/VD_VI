const API_BASE = window.location.origin;
let authToken = localStorage.getItem('vdai_token');

// ---- Auth ----
function switchAuthTab(tab) {
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('#authScreen form').forEach(f => f.classList.add('hidden'));
    document.querySelector(`.auth-tab[onclick*="${tab}"]`).classList.add('active');
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
        const tab = btn.dataset.tab;
        document.getElementById(`tab-${tab}`).classList.add('active');
        if (tab === 'gallery') loadGallery();
    });
});

// ---- Style tags ----
document.querySelectorAll('.style-tag').forEach(tag => {
    tag.addEventListener('click', () => {
        const isActive = tag.classList.contains('active');
        document.querySelectorAll('.style-tag').forEach(t => t.classList.remove('active'));
        if (!isActive) tag.classList.add('active');
    });
});

// ---- Health check ----
async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/api/health`);
        const data = await res.json();
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        if (data.status === 'ok') {
            dot.className = 'status-dot online';
            text.textContent = 'Сервер работает';
        } else {
            dot.className = 'status-dot offline';
            text.textContent = 'Ошибка сервера';
        }
    } catch {
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        dot.className = 'status-dot offline';
        text.textContent = 'Сервер недоступен';
    }
}

// ---- Image Generation ----
let lastImageResult = null;

function getActiveStyle() {
    const active = document.querySelector('.style-tag.active');
    return active ? active.dataset.style || '' : '';
}

async function generateImage() {
    const prompt = document.getElementById('prompt').value.trim();
    if (!prompt) return alert('Введите промпт');

    const uiLoader = document.getElementById('imageLoader');
    const uiPlaceholder = document.getElementById('imagePlaceholder');
    const uiResult = document.getElementById('imageResultContent');
    const btn = document.getElementById('generateImageBtn');

    uiLoader.classList.remove('hidden');
    uiPlaceholder.classList.add('hidden');
    uiResult.classList.add('hidden');
    btn.disabled = true;
    btn.textContent = 'Генерация...';

    try {
        const style = getActiveStyle();
        const fullPrompt = style ? `${prompt}, ${style}` : prompt;

        const seed = parseInt(document.getElementById('seed').value) || null;

        const body = {
            prompt: fullPrompt,
            negative_prompt: document.getElementById('negativePrompt').value || null,
            width: parseInt(document.getElementById('width').value),
            height: parseInt(document.getElementById('height').value),
            guidance_scale: parseFloat(document.getElementById('guidance').value) || 7.5,
            num_inference_steps: parseInt(document.getElementById('steps').value) || 30,
            seed: seed || null,
        };

        const res = await fetch(`${API_BASE}/api/generate/image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Ошибка генерации');
        }

        const data = await res.json();
        lastImageResult = data;

        const img = document.getElementById('generatedImage');
        img.src = `${API_BASE}${data.url}?t=${Date.now()}`;
        img.onload = () => {
            img.style.display = 'block';
        };

        document.getElementById('imageInfo').textContent =
            `Seed: ${data.seed} | Размер: ${body.width}x${body.height} | Шаги: ${body.num_inference_steps}`;

        uiLoader.classList.add('hidden');
        uiResult.classList.remove('hidden');
    } catch (err) {
        uiLoader.classList.add('hidden');
        uiPlaceholder.classList.remove('hidden');
        alert('Ошибка: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">✦</span> Сгенерировать';
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

// ---- Video Generation ----
let lastVideoResult = null;

async function generateVideo() {
    const prompt = document.getElementById('videoPrompt').value.trim();
    if (!prompt) return alert('Введите промпт');

    const uiLoader = document.getElementById('videoLoader');
    const uiPlaceholder = document.getElementById('videoPlaceholder');
    const uiResult = document.getElementById('videoResultContent');
    const btn = document.querySelector('#tab-video .btn-primary');

    uiLoader.classList.remove('hidden');
    uiPlaceholder.classList.add('hidden');
    uiResult.classList.add('hidden');
    btn.disabled = true;
    btn.textContent = 'Генерация видео...';

    try {
        const seed = parseInt(document.getElementById('videoSeed').value) || null;
        const duration = parseInt(document.getElementById('videoDuration').value) || 6;
        const fps = parseInt(document.getElementById('videoFps').value) || 10;

        const body = {
            prompt: prompt,
            seed: seed || null,
            duration: duration,
            fps: fps,
        };

        const res = await fetch(`${API_BASE}/api/generate/video`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
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

        uiLoader.classList.add('hidden');
        uiResult.classList.remove('hidden');
    } catch (err) {
        uiLoader.classList.add('hidden');
        uiPlaceholder.classList.remove('hidden');
        alert('Ошибка: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">▶</span> Сгенерировать видео';
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
let chatHistory = [];

async function sendChat() {
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg) return;

    input.value = '';
    addChatMsg('user', msg);
    chatHistory.push({ role: 'user', content: msg });

    const loader = document.getElementById('chatLoader');
    loader.classList.remove('hidden');

    try {
        const model = document.getElementById('chatModel').value;
        const headers = { 'Content-Type': 'application/json' };
        if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
        const res = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST', headers: headers,
            body: JSON.stringify({
                message: msg,
                history: chatHistory.slice(0, -1),
                model: model,
                system_prompt: "Ты VD AI — умный и дружелюбный ИИ-ассистент. Отвечай кратко и полезно. Твоё имя VD AI."
            }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка');
        addChatMsg('assistant', data.reply);
        chatHistory.push({ role: 'assistant', content: data.reply });
    } catch (err) {
        addChatMsg('assistant', 'Ошибка: ' + err.message);
    } finally {
        loader.classList.add('hidden');
    }
}

function addChatMsg(role, text) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    div.innerHTML = `<div class="msg-content">${escapeHtml(text)}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ---- Gallery ----
async function loadGallery() {
    const grid = document.getElementById('galleryGrid');
    grid.innerHTML = '<p class="gallery-empty">Загрузка...</p>';

    try {
        const res = await fetch(`${API_BASE}/api/generate/image`, { method: 'OPTIONS' });
    } catch {
        // pass
    }

    try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (!res.ok) throw new Error('Server error');

        const imgRes = await fetch(`${API_BASE}/api/generate/image`, { method: 'OPTIONS' });

        grid.innerHTML = `
            <p class="gallery-empty">Галерея просматривает папку outputs/ на сервере.<br>
            Откройте папку проекта и проверьте сгенерированные файлы вручную.</p>
        `;
    } catch {
        grid.innerHTML = '<p class="gallery-empty">Сервер недоступен</p>';
    }
}

// ---- Init ----
checkAuth();
checkHealth();
setInterval(checkHealth, 30000);
