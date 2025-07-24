import SwiftUI

// Custom theme for PhoTools - Modern dark mode with classic black/white aesthetics
struct PhoToolsTheme {
    
    // MARK: - Modern Dark Theme Colors
    
    // Pure black/gray backgrounds for modern dark mode
    static let backgroundColor = Color.black // Pure black background
    static let sidebarBackground = Color(red: 0.05, green: 0.05, blue: 0.05) // Very dark gray #0D0D0D
    static let cardBackground = Color(red: 0.11, green: 0.11, blue: 0.11) // Dark card background #1C1C1C
    
    // High contrast white text - modern accessibility
    static let primaryText = Color.white // Pure white for primary text
    static let secondaryText = Color(red: 0.8, green: 0.8, blue: 0.8) // Light gray #CCCCCC
    static let mutedText = Color(red: 0.6, green: 0.6, blue: 0.6) // Medium gray #999999
    
    // Modern accent colors with high contrast
    static let primaryColor = Color.white // White for primary actions
    static let secondaryColor = Color(red: 0.7, green: 0.7, blue: 0.7) // Light gray #B3B3B3
    static let accentColor = Color(red: 0.0, green: 0.48, blue: 1.0) // System blue #007AFF
    
    // Interface elements with modern contrast
    static let borderColor = Color(red: 0.2, green: 0.2, blue: 0.2) // #333333
    static let hoverColor = Color(red: 0.15, green: 0.15, blue: 0.15) // #262626
    static let selectedColor = Color(red: 0.25, green: 0.25, blue: 0.25) // #404040
    
    // MARK: - Typography
    
    static let titleFont = Font.custom("PerfectlyNineties-Regular", size: 28)
//    static let headlineFont = Font.system(.headline, design: .rounded, weight: .semibold)
    static let headlineFont = Font.custom("PerfectlyNineties-Semibold", size: 18)
    static let bodyFont = Font.custom("SysfontRegular", size: 14)
//    static let captionFont = Font.system(.caption, design: .default, weight: .medium)
    static let captionFont = Font.custom("SysfontRegular", size: 12)

    // MARK: - Styling Helpers
    
    static func cardStyle() -> some View {
        RoundedRectangle(cornerRadius: 8)
            .fill(cardBackground)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(borderColor, lineWidth: 0.5)
            )
    }
    
    static func primaryButton() -> some ViewModifier {
        return PhoToolsPrimaryButtonStyle()
    }
    
    static func secondaryButton() -> some ViewModifier {
        return PhoToolsSecondaryButtonStyle()
    }
}

// MARK: - Custom Button Styles

struct PhoToolsPrimaryButtonStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .font(PhoToolsTheme.headlineFont)
            .foregroundColor(PhoToolsTheme.backgroundColor)
            .padding(.horizontal, 20)
            .padding(.vertical, 10)
            .background(
                RoundedRectangle(cornerRadius: 4)
                    .fill(PhoToolsTheme.primaryColor)
            )
    }
}

struct PhoToolsSecondaryButtonStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .font(PhoToolsTheme.bodyFont)
            .foregroundColor(PhoToolsTheme.primaryText)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 4)
                    .fill(PhoToolsTheme.cardBackground)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 4)
                    .stroke(PhoToolsTheme.borderColor, lineWidth: 0.5)
            )
    }
}

// MARK: - Rating Stars Component

struct PhoToolsRatingView: View {
    let rating: Int
    let maxRating: Int = 5
    let size: CGFloat
    
    var body: some View {
        HStack(spacing: 2) {
            ForEach(1...maxRating, id: \.self) { star in
                Image(systemName: star <= rating ? "star.fill" : "star")
                    .foregroundColor(star <= rating ? PhoToolsTheme.accentColor : PhoToolsTheme.mutedText.opacity(0.3))
                    .font(.system(size: size))
            }
        }
    }
}

// MARK: - Extensions for easy use

extension View {
    func photoToolsPrimaryButton() -> some View {
        self.modifier(PhoToolsPrimaryButtonStyle())
    }
    
    func photoToolsSecondaryButton() -> some View {
        self.modifier(PhoToolsSecondaryButtonStyle())
    }
    
    func photoToolsCard() -> some View {
        self
            .background(PhoToolsTheme.cardBackground)
            .cornerRadius(6)
            .overlay(
                RoundedRectangle(cornerRadius: 6)
                    .stroke(PhoToolsTheme.borderColor, lineWidth: 0.5)
            )
    }
}
