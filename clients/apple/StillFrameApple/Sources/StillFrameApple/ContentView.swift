import SwiftUI

enum StillFrameTab: String, CaseIterable, Identifiable {
    case library = "Library"
    case folders = "Folders"
    case diagnostics = "Diagnostics"
    case settings = "Settings"

    var id: String { rawValue }

    var systemImage: String {
        switch self {
        case .library:
            return "rectangle.grid.2x2"
        case .folders:
            return "folder"
        case .diagnostics:
            return "waveform.path.ecg"
        case .settings:
            return "gearshape"
        }
    }
}

struct ContentView: View {
    @AppStorage("serverURL") private var serverURL = "http://127.0.0.1:8765"
    @StateObject private var model = AppModel()
    @State private var selection: StillFrameTab? = .library

    var body: some View {
        NavigationSplitView {
            List(StillFrameTab.allCases, selection: $selection) { tab in
                Label(tab.rawValue, systemImage: tab.systemImage)
                    .tag(tab)
            }
            .navigationTitle("StillFrame")
        } detail: {
            switch selection ?? .library {
            case .library:
                LibraryView(model: model)
            case .folders:
                FoldersView(model: model)
            case .diagnostics:
                DiagnosticsView(model: model)
            case .settings:
                SettingsView(serverURL: $serverURL, model: model)
            }
        }
        .task {
            await model.connect(to: serverURL)
        }
        .onChange(of: serverURL) { _, newValue in
            Task {
                await model.connect(to: newValue)
            }
        }
    }
}
