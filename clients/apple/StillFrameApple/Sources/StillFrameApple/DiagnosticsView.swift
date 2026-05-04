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

            Section("Media Cache") {
                LabeledContent("Root") {
                    Text(model.cacheDiagnostics?.root ?? "-")
                        .textSelection(.enabled)
                }
                LabeledContent("Files") {
                    Text(formatCount(model.cacheDiagnostics?.totalFiles))
                }
                LabeledContent("Storage") {
                    Text(formatBytes(model.cacheDiagnostics?.totalBytes))
                }

                ForEach(model.cacheDiagnostics?.buckets ?? []) { bucket in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(bucket.name.capitalized)
                            Spacer()
                            Text("\(formatCount(bucket.files)) files")
                                .foregroundStyle(.secondary)
                        }
                        Text(bucket.exists ? bucket.path : "Not created yet")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .textSelection(.enabled)
                    }
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

    private func formatCount(_ value: Int?) -> String {
        (value ?? 0).formatted()
    }

    private func formatBytes(_ value: Int?) -> String {
        let bytes = Double(value ?? 0)
        guard bytes > 0 else {
            return "0 B"
        }
        let formatter = ByteCountFormatter()
        formatter.allowedUnits = [.useKB, .useMB, .useGB, .useTB]
        formatter.countStyle = .file
        return formatter.string(fromByteCount: Int64(bytes))
    }
}
