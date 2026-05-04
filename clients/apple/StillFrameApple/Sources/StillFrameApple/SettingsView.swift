import SwiftUI

struct SettingsView: View {
    @Binding var serverURL: String
    @ObservedObject var model: AppModel
    @State private var draftServerURL = ""

    var body: some View {
        Form {
            Section("StillFrame Host") {
                TextField("Server URL", text: $draftServerURL)
                    #if os(iOS)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
                    #endif
                    .autocorrectionDisabled()

                Button {
                    serverURL = draftServerURL.trimmingCharacters(in: .whitespacesAndNewlines)
                    Task {
                        await model.connect(to: serverURL)
                    }
                } label: {
                    Label("Connect", systemImage: "network")
                }
                .buttonStyle(.borderedProminent)
            }

            Section("How to Connect iPhone or iPad") {
                Text("Run StillFrame on the Mac, expose the API on your trusted LAN, then enter http://<mac-lan-ip>:8765 here.")
                    .foregroundStyle(.secondary)

                Text("./scripts/run_server_lan.sh")
                    .font(.system(.callout, design: .monospaced))
                    .textSelection(.enabled)
            }

            Section("Native Playback") {
                Text("Preview uses AVPlayer for formats supported by iOS and iPadOS. Full-quality playback can be launched on the Mac host through mpv.")
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("Settings")
        .onAppear {
            draftServerURL = serverURL
        }
    }
}
