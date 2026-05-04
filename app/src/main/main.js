import { app, BrowserWindow, dialog, ipcMain, Menu } from "electron";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const APP_ROOT = app.isPackaged ? app.getAppPath() : path.resolve(__dirname, "../..");
const PROJECT_ROOT = app.isPackaged ? path.join(process.resourcesPath, "StillFrame") : path.resolve(APP_ROOT, "..");
const SERVER_DIR = path.join(PROJECT_ROOT, "server");
const SERVER_URL = "http://127.0.0.1:8765";

let mainWindow = null;
let serverProcess = null;

function createMenu() {
  const template = [
    {
      label: "StillFrame",
      submenu: [
        { role: "about" },
        { type: "separator" },
        { role: "quit" }
      ]
    },
    {
      label: "File",
      submenu: [
        {
          label: "Add Folder",
          accelerator: "CommandOrControl+O",
          click: () => mainWindow?.webContents.send("menu:add-folder")
        },
        { type: "separator" },
        { role: "close" }
      ]
    },
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "toggleDevTools" },
        { type: "separator" },
        { role: "togglefullscreen" }
      ]
    }
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function packagedStorageEnv() {
  if (!app.isPackaged) {
    return {};
  }

  const userDataDir = app.getPath("userData");
  const mediaCacheDir = process.env.STILLFRAME_MEDIA_CACHE_DIR || path.join(userDataDir, "media_cache");
  fs.mkdirSync(mediaCacheDir, { recursive: true });

  return {
    STILLFRAME_DB_PATH: process.env.STILLFRAME_DB_PATH || path.join(userDataDir, "stillframe.db"),
    STILLFRAME_MEDIA_CACHE_DIR: mediaCacheDir
  };
}

function startBackend() {
  if (serverProcess) {
    return;
  }

  const env = {
    ...process.env,
    PYTHONPATH: [PROJECT_ROOT, SERVER_DIR, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
    ...packagedStorageEnv(),
    STILLFRAME_HOST: "127.0.0.1",
    STILLFRAME_PORT: "8765"
  };
  const venvPython = path.join(SERVER_DIR, ".venv", "bin", "python");
  const python = fs.existsSync(venvPython) ? venvPython : "python3";

  serverProcess = spawn(
    python,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8765"],
    {
      cwd: SERVER_DIR,
      env,
      stdio: process.env.NODE_ENV === "development" ? "inherit" : "ignore"
    }
  );

  serverProcess.on("exit", () => {
    serverProcess = null;
  });
}

function stopBackend() {
  if (!serverProcess) {
    return;
  }
  serverProcess.kill();
  serverProcess = null;
}

async function waitForBackend(deadlineMs = 8000) {
  const started = Date.now();
  while (Date.now() - started < deadlineMs) {
    try {
      const response = await fetch(`${SERVER_URL}/health`);
      if (response.ok) {
        return true;
      }
    } catch {
      // Backend is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return false;
}

async function createWindow() {
  startBackend();
  await waitForBackend();

  mainWindow = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 980,
    minHeight: 680,
    backgroundColor: "#0f1115",
    titleBarStyle: "hiddenInset",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  if (process.env.NODE_ENV === "development") {
    await mainWindow.loadURL("http://127.0.0.1:5173");
  } else {
    await mainWindow.loadFile(path.join(APP_ROOT, "dist", "index.html"));
  }
}

app.whenReady().then(() => {
  createMenu();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopBackend();
});

ipcMain.handle("dialog:open-directory", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ["openDirectory"],
    buttonLabel: "Add Folder"
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle("app:get-server-url", () => SERVER_URL);
