import SwiftUI

struct PhotoThumbnailView: View {
    let photo: Photo
    let size: CGFloat
    let isSelected: Bool
    
    var body: some View {
        VStack(spacing: 4) {
            // Thumbnail container
            ZStack {
                // Placeholder background
                RoundedRectangle(cornerRadius: 8)
                    .fill(PhoToolsTheme.cardBackground)
                    .aspectRatio(1, contentMode: .fit)
                
                // Mock thumbnail - in real app this would be AsyncImage loading from API
                RoundedRectangle(cornerRadius: 8)
                    .fill(
                        LinearGradient(
                            colors: [PhoToolsTheme.mutedText.opacity(0.3), PhoToolsTheme.mutedText.opacity(0.1)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .aspectRatio(1, contentMode: .fit)
                    .overlay {
                        VStack {
                            Image(systemName: "photo")
                                .font(.title)
                                .foregroundColor(PhoToolsTheme.primaryText.opacity(0.8))
                            Text(photo.filename)
                                .font(.caption2)
                                .foregroundColor(PhoToolsTheme.primaryText.opacity(0.9))
                                .multilineTextAlignment(.center)
                        }
                        .padding(8)
                    }
                
                // Selection overlay
                if isSelected {
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(PhoToolsTheme.accentColor, lineWidth: 2)
                        .background(PhoToolsTheme.accentColor.opacity(0.1))
                        .cornerRadius(8)
                }
                
                // Rating overlay (top-right)
                if let rating = photo.userRating, rating > 0 {
                    VStack {
                        HStack {
                            Spacer()
                            RatingBadge(rating: rating)
                                .padding(6)
                        }
                        Spacer()
                    }
                }
                
                // File type badge (bottom-left)
                VStack {
                    Spacer()
                    HStack {
                        if photo.mimeType.contains("heic") {
                            Text("HEIC")
                                .font(.caption2)
                                .padding(.horizontal, 4)
                                .padding(.vertical, 2)
                                .background(PhoToolsTheme.backgroundColor.opacity(0.8))
                                .foregroundColor(PhoToolsTheme.primaryText)
                                .cornerRadius(4)
                                .padding(6)
                        }
                        Spacer()
                    }
                }
            }
            .frame(width: size, height: size)
            
            // Photo info
            VStack(alignment: .leading, spacing: 2) {
                Text(photo.filename)
                    .font(.caption)
                    .foregroundColor(PhoToolsTheme.primaryText)
                    .lineLimit(1)
                    .truncationMode(.middle)
                
                HStack {
                    if let metadata = photo.metadata {
                        Text(metadata.cameraInfo)
                            .font(.caption2)
                            .foregroundColor(PhoToolsTheme.secondaryText)
                            .lineLimit(1)
                    }
                    
                    Spacer()
                    
                    Text(photo.displaySize)
                        .font(.caption2)
                        .foregroundColor(PhoToolsTheme.secondaryText)
                }
            }
            .frame(width: size)
        }
        .contentShape(Rectangle()) // Makes entire area tappable
    }
}

struct RatingBadge: View {
    let rating: Int
    
    var body: some View {
        HStack(spacing: 2) {
            ForEach(0..<rating, id: \.self) { _ in
                Image(systemName: "star.fill")
                    .font(.caption2)
                    .foregroundColor(PhoToolsTheme.accentColor)
            }
        }
        .padding(.horizontal, 4)
        .padding(.vertical, 2)
        .background(PhoToolsTheme.backgroundColor.opacity(0.8))
        .cornerRadius(4)
    }
}

#Preview {
    LazyVGrid(columns: [GridItem(.adaptive(minimum: 200))], spacing: 8) {
        ForEach(Photo.mockPhotos) { photo in
            PhotoThumbnailView(
                photo: photo,
                size: 200,
                isSelected: photo.id == "1"
            )
        }
    }
    .padding()
}