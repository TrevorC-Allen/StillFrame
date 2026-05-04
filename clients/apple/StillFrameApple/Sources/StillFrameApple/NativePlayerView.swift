import SwiftUI

#if canImport(AVKit)
import AVKit
#endif

struct NativePlayerView: View {
    let title: String
    let url: URL

    var body: some View {
        NavigationStack {
            player
                .navigationTitle(title)
                #if os(iOS)
                .navigationBarTitleDisplayMode(.inline)
                #endif
        }
    }

    @ViewBuilder
    private var player: some View {
        #if canImport(AVKit)
        VideoPlayer(player: AVPlayer(url: url))
            .ignoresSafeArea()
        #else
        ContentUnavailableView("Native Playback Unavailable", systemImage: "play.slash")
        #endif
    }
}
