// electron/main.js - Electron main process
const { app, BrowserWindow, shell, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const isDev = process.env.NODE_ENV === 'development';

let mainWindow;
let pythonProcess;

function createWindow() {
    // Create the browser window
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1200,
        minHeight: 700,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            enableRemoteModule: false,
            webSecurity: true
        },
        titleBarStyle: 'hiddenInset',
        show: false,
        icon: path.join(__dirname, 'assets', 'icon.png')
    });

    // Start Python backend
    startPythonBackend();

    // Load the app
    if (isDev) {
        mainWindow.loadURL('http://127.0.0.1:8765');
        mainWindow.webContents.openDevTools();
    } else {
        // Wait for Python server to start, then load
        setTimeout(() => {
            mainWindow.loadURL('http://127.0.0.1:8765');
        }, 3000);
    }

    // Show window when ready
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
        
        // Focus on the window
        if (isDev) {
            mainWindow.focus();
        }
    });

    // Handle window closed
    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    // Handle external links
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: 'deny' };
    });
}

function startPythonBackend() {
    const pythonExecutable = isDev ? 'python' : getPythonExecutablePath();
    const scriptPath = isDev ? 'main.py' : path.join(process.resourcesPath, 'main.py');
    
    console.log('Starting Python backend...');
    console.log('Python executable:', pythonExecutable);
    console.log('Script path:', scriptPath);
    
    pythonProcess = spawn(pythonExecutable, [scriptPath, '--electron'], {
        cwd: isDev ? process.cwd() : process.resourcesPath,
        env: { ...process.env, PYTHONPATH: isDev ? process.cwd() : process.resourcesPath }
    });

    pythonProcess.stdout.on('data', (data) => {
        console.log(`Python stdout: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
        console.error(`Python stderr: ${data}`);
    });

    pythonProcess.on('close', (code) => {
        console.log(`Python process exited with code ${code}`);
    });

    pythonProcess.on('error', (error) => {
        console.error('Failed to start Python process:', error);
    });
}

function getPythonExecutablePath() {
    // In production, Python executable is bundled
    if (process.platform === 'win32') {
        return path.join(process.resourcesPath, 'python', 'python.exe');
    } else if (process.platform === 'darwin') {
        return path.join(process.resourcesPath, 'python', 'bin', 'python');
    } else {
        return path.join(process.resourcesPath, 'python', 'bin', 'python');
    }
}

// App event handlers
app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    // Kill Python process
    if (pythonProcess) {
        pythonProcess.kill();
    }
    
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('before-quit', () => {
    // Kill Python process
    if (pythonProcess) {
        pythonProcess.kill();
    }
});

// IPC handlers
ipcMain.handle('get-app-version', () => {
    return app.getVersion();
});

ipcMain.handle('show-item-in-folder', (event, fullPath) => {
    shell.showItemInFolder(fullPath);
});

// Security
app.on('web-contents-created', (event, contents) => {
    contents.on('new-window', (event, navigationUrl) => {
        event.preventDefault();
        shell.openExternal(navigationUrl);
    });
});

// Prevent navigation to external websites
app.on('web-contents-created', (event, contents) => {
    contents.on('will-navigate', (event, navigationUrl) => {
        const parsedUrl = new URL(navigationUrl);
        
        if (parsedUrl.origin !== 'http://127.0.0.1:8765') {
            event.preventDefault();
        }
    });
});