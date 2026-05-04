import SwiftUI

struct DiagnosticsView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        List {
            Section("Host") {
                LabeledContent("Server") {
                    Text(model.health?.app ?? "Not connected")
                }
                LabeledContent("Version") {
                    Text(model.health?.version ?? "-")
                }
                LabeledContent("Database") {
                    Text(model.health?.databasePath ?? "-")
                        .textSelection(.enabled)
                }
            }

            Section("Playback") {
                LabeledContent("mpv") {
                    Text(toolStatus(model.diagnostics?.mpv.present))
                }
                LabeledContent("ffmpeg") {
                    Text(toolStatus(model.diagnostics?.ffmpeg.present))
                }
                LabeledContent("Full Playback") {
                    Text((model.diagnostics?.fullPlaybackAvailable ?? false) ? "Ready" : "Needs setup")
                }

                if let hint = model.diagnostics?.installHint {
                    Text(hint)
                        .foregroundStyle(.secondary)
                }
            }

            if let issues = model.diagnostics?.issues, !issues.isEmpty {
                Section("Issues") {
                    ForEach(issues) { issue in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(issue.message)
                                .font(.headline)
                            Text(issue.action)
                                .font(.callout)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .navigationTitle("Diagnostics")
        .refreshable {
            await model.reloadAll()
        }
    }

    private func toolStatus(_ present: Bool?) -> String {
        switch present {
        case true:
            return "Installed"
        case false:
            return "Missing"
        case nil:
            return "-"
        }
    }
}
