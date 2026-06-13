const { ipcRenderer } = require('electron');

let gtaState = "download"; // Статусы: download -> downloading -> play

// Вход в программу
document.getElementById('btn-register').addEventListener('click', () => {
    const username = document.getElementById('reg-username').value || "Игрок";
    const currency = document.getElementById('reg-currency').value;
    
    let sign = currency === "RUB" ? "₽" : currency === "USD" ? "$" : "₸";
    document.getElementById('user-balance').innerText = `0.00 ${sign}`;
    document.getElementById('user-name').innerText = username;

    document.getElementById('auth-screen').classList.add('hidden');
    document.getElementById('main-screen').classList.remove('hidden');
});

// Клик по кнопке GTA V
function handleGta() {
    const btn = document.getElementById('btn-gta');
    const pBox = document.getElementById('gta-progress-box');

    if (gtaState === "download") {
        gtaState = "downloading";
        btn.innerText = "Скачивание...";
        pBox.classList.remove('hidden');

        // Отправляем в main.js команду начать скачивание
        // (Для теста можешь указать любую ссылку на zip, пока оставим заглушку)
        ipcRenderer.send('download-game', {
            url: 'https://example.com', 
            downloadPath: 'C:\\RedDemoGames\\gta5.zip',
            extractTo: 'C:\\RedDemoGames\\GTA5'
        });

    } else if (gtaState === "play") {
        // Отправляем команду запуска exe
        ipcRenderer.send('launch-game', 'C:\\RedDemoGames\\GTA5\\gta5.exe');
    }
}

// Слушаем ответы от главного процесса (прогресс скачивания)
ipcRenderer.on('download-progress', (event, percent) => {
    document.getElementById('gta-fill').style.width = `${percent}%`;
    document.getElementById('btn-gta').innerText = `Скачано: ${percent}%`;
});

ipcRenderer.on('download-status', (event, status) => {
    const btn = document.getElementById('btn-gta');
    if (status === 'Unpacking') {
        btn.innerText = "Распаковка репака...";
    } else if (status === 'Ready') {
        gtaState = "play";
        btn.innerText = "ИГРАТЬ";
        document.getElementById('gta-progress-box').classList.add('hidden');
    } else if (status === 'Error') {
        gtaState = "download";
        btn.innerText = "Ошибка. Скачать заново";
        alert("Произошла ошибка при скачивании архива.");
    }
});
