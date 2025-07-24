import SwiftUI

struct CollectionsView: View {
    var body: some View {
        VStack {
            Image(systemName: "folder")
                .font(.system(size: 48))
                .foregroundColor(PhoToolsTheme.mutedText)
            
            Text("Collections")
                .font(PhoToolsTheme.titleFont)
                .foregroundColor(PhoToolsTheme.primaryText)
            
            Text("Photo collections will be implemented here")
                .font(.subheadline)
                .foregroundColor(PhoToolsTheme.secondaryText)
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
                .foregroundColor(PhoToolsTheme.mutedText)
            
            Text("Advanced Search")
                .font(PhoToolsTheme.titleFont)
                .foregroundColor(PhoToolsTheme.primaryText)
            
            Text("Advanced search functionality will be implemented here")
                .font(.subheadline)
                .foregroundColor(PhoToolsTheme.secondaryText)
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