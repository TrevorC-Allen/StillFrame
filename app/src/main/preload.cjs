const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("stillframe", {
  chooseFolder: () => ipcRenderer.invoke("dialog:open-directory"),
  getServerUrl: () => ipcRenderer.invoke("app:get-server-url"),
  onAddFolder: (callback) => {
    const listener = () => callback();
    ipcRenderer.on("menu:add-folder", listener);
    return () => ipcRenderer.removeListener("menu:add-folder", listener);
  }
});

