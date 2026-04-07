import SwiftUI

struct ContentView: View {
    var body: some View {
        NavigationStack {
            UsersView()
                .navigationTitle("Home")
        }
    }
}

#Preview {
    ContentView()
}
