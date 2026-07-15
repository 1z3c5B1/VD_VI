let userCoins = 0;
let userIsPro = false;
let userIsAdmin = false;

const API_BASE = "https://vd-ai.onrender.com";
let authToken = localStorage.getItem('vdai_token');
let chatHistory = [];
let lastImageResult = null;

// Debounce helper
function debounce(fn, delay) {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn(...args), delay);
    };
}

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
    
    if (!username || !password) {
        document.getElementById('authError').textContent = 'Заполните все поля';
        return;
    }
    
    document.getElementById('authError').textContent = '';
    document.getElementById('authLoader').classList.remove('hidden');
    
    try {
        const res = await fetch(`${API_BASE}/api/login`, {
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка входа');
        
        authToken = data.token;
        localStorage.setItem('vdai_token', authToken);
        userCoins = data.coins || 0;
        userIsPro = !!data.pro;
        document.getElementById('authScreen').style.display = 'none';
        document.getElementById('userName').textContent = data.username;
        document.getElementById('userAvatar').textContent = data.username.charAt(0).toUpperCase();
        document.getElementById('userMenu').classList.add('active');
        document.getElementById('userCoins').textContent = userCoins;
    } catch (err) {
        document.getElementById('authError').textContent = err.message;
    } finally {
        document.getElementById('authLoader').classList.add('hidden');
    }
}

async function authRegister() {
    const username = document.getElementById('regUsername').value.trim();
    const password = document.getElementById('regPassword').value;
    
    if (!username || !password) {
        document.getElementById('regError').textContent = 'Заполните все поля';
        return;
    }
    if (password.length < 4) {
        document.getElementById('regError').textContent = 'Пароль минимум 4 символа';
        return;
    }
    
    document.getElementById('regError').textContent = '';
    document.getElementById('authLoader').classList.remove('hidden');
    
    try {
        const res = await fetch(`${API_BASE}/api/register`, {
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка регистрации');
        
        authToken = data.token;
        localStorage.setItem('vdai_token', authToken);
        userCoins = data.coins || 10;
        document.getElementById('authScreen').style.display = 'none';
        document.getElementById('userName').textContent = data.username;
        document.getElementById('userAvatar').textContent = data.username.charAt(0).toUpperCase();
        document.getElementById('userMenu').classList.add('active');
        document.getElementById('userCoins').textContent = userCoins;
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
    document.getElementById('regUsername').value = '';
    document.getElementById('regPassword').value = '';
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
        userCoins = data.coins || 0;
        userIsPro = !!data.pro;
        userIsAdmin = !!data.is_admin;
        document.getElementById('userCoins').textContent = userCoins;
        document.getElementById('coinsBadge').classList.toggle('pro', userIsPro);
        if (userIsAdmin) {
            document.getElementById('adminTab').classList.remove('hidden');
        }
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
        if (btn.dataset.tab === 'admin') loadAdminData();
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
    if (file.size > 10 * 1024 * 1024) { 
        alert('Файл слишком большой (макс 10MB)'); 
        return; 
    }
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

function onStatusClick() {
    if (!authToken) return alert('Войдите в аккаунт');
    if (userIsAdmin) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.querySelector('[data-tab="admin"]').classList.add('active');
        document.getElementById('tab-admin').classList.add('active');
        loadAdminData();
        return;
    }
    const pw = prompt('Пароль админки:');
    if (!pw) return;
    fetch(`${API_BASE}/api/admin/auth`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify({ code: pw }),
    }).then(r => r.json()).then(data => {
        if (data.success) {
            userIsAdmin = true;
            document.getElementById('adminTab').classList.remove('hidden');
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelector('[data-tab="admin"]').classList.add('active');
            document.getElementById('tab-admin').classList.add('active');
            loadAdminData();
        } else {
            alert(data.detail || 'Неверный пароль');
        }
    }).catch(() => alert('Ошибка'));
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
            headers: { 
                'Content-Type': 'application/json', 
                'Authorization': `Bearer ${authToken}` 
            },
            body: JSON.stringify({
                prompt: fullPrompt,
                negative_prompt: document.getElementById('negativePrompt').value || null,
                width: parseInt(document.getElementById('width').value),
                height: parseInt(document.getElementById('height').value),
                guidance_scale: parseFloat(document.getElementById('guidance').value) || 7.5,
                num_inference_steps: parseInt(document.getElementById('steps').value) || 25,
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
            `Seed: ${data.seed} | ${document.getElementById('width').value}x${document.getElementById('height').value} | 💎 ${data.unlimited ? '∞' : data.coins}`;

        if (data.coins !== undefined) {
            userCoins = data.coins;
            document.getElementById('userCoins').textContent = userCoins;
        }

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
let currentEditType = 'custom';

function editImageType(type) {
    currentEditType = type;
    document.querySelectorAll('.edit-type-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.edit-type-btn[data-type="${type}"]`).classList.add('active');
    if (document.getElementById('editFileInput').files.length) {
        editImage();
    }
}

async function editImage() {
    const fileInput = document.getElementById('editFileInput');
    const previewImg = document.getElementById('editPreviewImg');

    if (!fileInput.files.length) return alert('Загрузи фото сначала');
    if (!currentEditType) return alert('Выбери эффект');

    const loader = document.getElementById('imageLoader');
    const placeholder = document.getElementById('imagePlaceholder');
    const result = document.getElementById('imageResultContent');
    const btn = document.getElementById('editImageBtn');
    const loaderText = document.getElementById('imageLoaderText');

    loader.classList.remove('hidden');
    placeholder.classList.add('hidden');
    result.classList.add('hidden');
    btn.disabled = true;
    btn.textContent = 'Применяю...';
    loaderText.textContent = 'Применение эффекта...';

    try {
        const res = await fetch(`${API_BASE}/api/generate/edit-image`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json', 
                'Authorization': `Bearer ${authToken}` 
            },
            body: JSON.stringify({
                image_data: previewImg.src,
                edit_type: currentEditType,
            }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Ошибка применения эффекта');
        }

        const data = await res.json();
        lastImageResult = data;

        const img = document.getElementById('generatedImage');
        img.src = `${API_BASE}${data.url}?t=${Date.now()}`;

        document.getElementById('imageInfo').textContent =
            `Эффект: ${currentEditType} | 💎 ${data.unlimited ? '∞' : data.coins}`;

        if (data.coins !== undefined) {
            userCoins = data.coins;
            document.getElementById('userCoins').textContent = userCoins;
        }

        loader.classList.add('hidden');
        result.classList.remove('hidden');
    } catch (err) {
        loader.classList.add('hidden');
        placeholder.classList.remove('hidden');
        alert('Ошибка: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '✎ Применить';
        loaderText.textContent = 'Генерация...';
    }
}

// ---- Chat ----
async function sendChat() {
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg) return;
    if (!authToken) return alert('Войдите, чтобы использовать чат');

    input.value = '';
    addChatMsg('user', msg, 'Вы');
    chatHistory.push({ role: 'user', content: msg });

    const loader = document.getElementById('chatLoader');
    const sendBtn = document.querySelector('#tab-chat .chat-input-row .btn');
    loader.classList.remove('hidden');
    sendBtn.disabled = true;

    try {
        const model = document.getElementById('chatModel').value;
        const headers = { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
        };

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

        if (data.coins !== undefined) {
            userCoins = data.coins;
            document.getElementById('userCoins').textContent = userCoins;
        }
    } catch (err) {
        addChatMsg('assistant', 'Ошибка: ' + err.message, 'Система');
    } finally {
        loader.classList.add('hidden');
        sendBtn.disabled = false;
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
                    <div class="gallery-item-overlay">
                        <span>▶ ${file.filename}</span>
                        <div class="gallery-actions">
                            <button class="gal-btn" onclick="event.stopPropagation(); downloadFile('${file.url}', '${file.filename}')" title="Скачать">⬇</button>
                            <button class="gal-btn" onclick="event.stopPropagation(); deleteFile('${file.filename}')" title="Удалить">✕</button>
                        </div>
                    </div>
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
                overlay.innerHTML = `
                    <span>${file.filename}</span>
                    <div class="gallery-actions">
                        <button class="gal-btn" onclick="event.stopPropagation(); downloadFile('${file.url}', '${file.filename}')" title="Скачать">⬇</button>
                        <button class="gal-btn" onclick="event.stopPropagation(); deleteFile('${file.filename}')" title="Удалить">✕</button>
                    </div>
                `;
                item.appendChild(overlay);
                item.addEventListener('click', () => window.open(`${API_BASE}${file.url}`, '_blank'));
            }
            grid.appendChild(item);
        });
    } catch {
        grid.innerHTML = '<p class="gallery-empty">Сервер недоступен</p>';
    }
}

async function downloadFile(url, filename) {
    const a = document.createElement('a');
    a.href = `${API_BASE}${url}`;
    a.download = filename;
    a.click();
}

async function deleteFile(filename) {
    if (!confirm(`Удалить ${filename}?`)) return;
    try {
        const res = await fetch(`${API_BASE}/api/gallery/${filename}`, { 
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (!res.ok) throw new Error('Не удалось удалить');
        loadGallery();
    } catch (err) {
        alert('Ошибка удаления: ' + err.message);
    }
}

// ---- Promo Code ----
async function activatePromo() {
    const code = document.getElementById('promoCode').value.trim();
    if (!code) return;
    const resultEl = document.getElementById('promoResult');
    resultEl.textContent = '';
    try {
        const res = await fetch(`${API_BASE}/api/promo`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`,
            },
            body: JSON.stringify({ code }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка');
        resultEl.style.color = '#4ade80';
        resultEl.textContent = 'Промокод активирован!';
        if (data.coins !== undefined) {
            userCoins = data.coins;
            document.getElementById('userCoins').textContent = userCoins;
        }
        if (data.pro !== undefined) {
            userIsPro = !!data.pro;
        }
    } catch (err) {
        resultEl.style.color = '#f87171';
        resultEl.textContent = err.message;
    }
}

// ---- Admin Panel ----
async function loadAdminData() {
    if (!userIsAdmin) return;
    await loadAdminUsers();
    await loadAdminPromos();
}

async function loadAdminUsers() {
    try {
        const res = await fetch(`${API_BASE}/api/admin/users`, {
            headers: { 'Authorization': `Bearer ${authToken}` },
        });
        const data = await res.json();
        if (!data.success) return;
        const el = document.getElementById('adminUsersList');
        el.innerHTML = data.users.map(u => {
            let proLabel = '';
            if (u.pro) {
                proLabel = u.pro_expires ? '⭐PRO ⏰' : '⭐PRO ∞';
            }
            return `
            <div class="admin-item">
                <span>${escapeHtml(u.username)} (id:${u.id}) — 💎${u.coins} ${proLabel} ${u.banned ? '🚫BANNED' + (u.ban_reason ? ' (' + escapeHtml(u.ban_reason) + ')' : '') : ''}</span>
                <div class="admin-actions">
                    <button class="btn btn-small" onclick="adminSetCoins(${u.id})">💎</button>
                    <button class="btn btn-small" onclick="adminTogglePro(${u.id})">⭐</button>
                    ${u.banned
                        ? `<button class="btn btn-small" onclick="adminUnban(${u.id})">✅</button>`
                        : `<button class="btn btn-small" onclick="adminBan(${u.id})">🚫</button>`
                    }
                    <button class="btn btn-small btn-danger" onclick="adminDeleteUser(${u.id})">🗑</button>
                </div>
            </div>`;
        }).join('');
    } catch {}
}

async function loadAdminPromos() {
    try {
        const res = await fetch(`${API_BASE}/api/admin/promos`, {
            headers: { 'Authorization': `Bearer ${authToken}` },
        });
        const data = await res.json();
        if (!data.success) return;
        const el = document.getElementById('adminPromosList');
        el.innerHTML = data.promos.map(p => {
            const durLabel = p.duration ? ` ⏰${p.duration}` : '';
            return `
            <div class="admin-item">
                <span>${escapeHtml(p.code)} — ${p.type} ${p.value ? '(' + p.value + ')' : ''}${durLabel} ${p.used_by ? '✅ used' : '🟡 unused'}</span>
                <div class="admin-actions">
                    <button class="btn btn-small btn-danger" onclick="adminDeletePromo('${escapeHtml(p.code)}')">🗑</button>
                </div>
            </div>`;
        }).join('');
    } catch {}
}

function togglePromoDuration() {
    const type = document.getElementById('adminPromoType').value;
    const dur = document.getElementById('adminPromoDuration');
    dur.style.display = type === 'pro' ? '' : 'none';
}

async function adminCreatePromo() {
    const code = document.getElementById('adminPromoCode').value.trim();
    const type = document.getElementById('adminPromoType').value;
    const value = parseInt(document.getElementById('adminPromoValue').value) || 0;
    const duration = document.getElementById('adminPromoDuration').value;
    if (!code) return;
    try {
        await fetch(`${API_BASE}/api/admin/promo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
            body: JSON.stringify({ code, type, value, duration }),
        });
        document.getElementById('adminPromoCode').value = '';
        loadAdminPromos();
    } catch {}
}

async function adminDeletePromo(code) {
    if (!confirm(`Удалить промокод ${code}?`)) return;
    try {
        await fetch(`${API_BASE}/api/admin/promo/${code}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${authToken}` },
        });
        loadAdminPromos();
    } catch {}
}

async function adminBan(userId) {
    const reason = prompt(`Причина бана для ${userId}? (оставь пустым если без причины)`);
    if (reason === null) return;
    try {
        await fetch(`${API_BASE}/api/admin/ban/${userId}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason }),
        });
        loadAdminUsers();
    } catch {}
}

async function adminUnban(userId) {
    try {
        await fetch(`${API_BASE}/api/admin/unban/${userId}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` },
        });
        loadAdminUsers();
    } catch {}
}

async function adminSetCoins(userId) {
    const coins = prompt('Сколько coins поставить?');
    if (coins === null) return;
    try {
        await fetch(`${API_BASE}/api/admin/coins`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
            body: JSON.stringify({ user_id: userId, coins: parseInt(coins) }),
        });
        loadAdminUsers();
    } catch {}
}

async function adminTogglePro(userId) {
    try {
        await fetch(`${API_BASE}/api/admin/pro/${userId}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` },
        });
        loadAdminUsers();
    } catch {}
}

async function adminDeleteUser(userId) {
    if (!confirm(`УДАЛИТЬ пользователя ${userId}? Это нельзя отменить!`)) return;
    try {
        await fetch(`${API_BASE}/api/admin/user/${userId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${authToken}` },
        });
        loadAdminUsers();
    } catch {}
}

// ---- Init ----
checkAuth();
checkHealth();
setInterval(checkHealth, 30000);