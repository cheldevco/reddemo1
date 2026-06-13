const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { exec } = require('child_process');
const fs = require('fs');
const axios = require('axios');
const AdmZip = require('adm-zip');

let mainWindow;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1000,
        height: 650,
        resizable: false, // Фиксированный размер окна
        autoHideMenuBar: true, // Прячем меню сверху
        backgroundColor: '#0b0c10',
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    mainWindow.loadFile('index.html');
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});

// --- ТЕХНИЧЕСКИЙ ФУНКЦИОНАЛ ДЛЯ ИГР ---

// 1. Принудительный запуск .exe файла игры с ПК
ipcMain.on('launch-game', (event, exePath) => {
    exec(`"${exePath}"`, (error) => {
        if (error) console.error('Ошибка запуска игры:', error);
    });
});

// 2. Скачивание ZIP-архива игры с прогресс-баром и авто-распаковкой
ipcMain.on('download-game', async (event, { url, downloadPath, extractTo }) => {
    try {
        const writer = fs.createWriteStream(downloadPath);
        const response = await axios({ url, method: 'GET', responseType: 'stream' });

        const totalLength = response.headers['content-length'];
        let downloadedLength = 0;

        response.data.on('data', (chunk) => {
            downloadedLength += chunk.length;
            const progress = ((downloadedLength / totalLength) * 100).toFixed(0);
            mainWindow.webContents.send('download-progress', progress); // шлем % в HTML
        });

        response.data.pipe(writer);

        writer.on('finish', () => {
            mainWindow.webContents.send('download-status', 'Unpacking');
            
            try {
                // Распаковываем архив
                const zip = new AdmZip(downloadPath);
                zip.extractAllTo(extractTo, true);
                
                // Стираем временный zip-архив, чтобы сэкономить место
                fs.unlinkSync(downloadPath); 
                
                mainWindow.webContents.send('download-status', 'Ready');
            } catch (err) {
                mainWindow.webContents.send('download-status', 'Error');
            }
        });

    } catch (error) {
        mainWindow.webContents.send('download-status', 'Error');
    }
});
