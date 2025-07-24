import SwiftUI

struct CollectionsView: View {
    var body: some View {
        VStack {
            Image(systemName: "folder")
                .font(.system(size: 48))
                .foregroundColor(.secondary)
            
            Text("Collections")
                .font(.title)
                .fontWeight(.semibold)
            
            Text("Photo collections will be implemented here")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .navigationTitle("Collections")
    }
}

struct SearchView: View {
    var body: some View {
        VStack {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 48))
                .foregroundColor(.secondary)
            
            Text("Advanced Search")
                .font(.title)
                .fontWeight(.semibold)
            
            Text("Advanced search functionality will be implemented here")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .navigationTitle("Search")
    }
}

#Preview("Collections") {
    CollectionsView()
}

#Preview("Search") {
    SearchView()
}