import AppKit
import SwiftUI

enum AriadneDesign {
    enum ColorToken {
        static let canvas = Color(nsColor: NSColor(name: nil) { appearance in
            appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
                ? NSColor(calibratedRed: 0.105, green: 0.100, blue: 0.090, alpha: 1)
                : NSColor(calibratedRed: 0.965, green: 0.950, blue: 0.920, alpha: 1)
        })
        static let surface = Color(nsColor: NSColor(name: nil) { appearance in
            appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
                ? NSColor(calibratedRed: 0.145, green: 0.137, blue: 0.122, alpha: 1)
                : NSColor(calibratedRed: 0.988, green: 0.980, blue: 0.955, alpha: 1)
        })
        static let elevated = Color(nsColor: NSColor(name: nil) { appearance in
            appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
                ? NSColor(calibratedRed: 0.180, green: 0.170, blue: 0.150, alpha: 1)
                : NSColor(calibratedRed: 1.000, green: 0.995, blue: 0.976, alpha: 1)
        })
        static let line = Color.primary.opacity(0.085)
        static let softLine = Color.primary.opacity(0.055)
        static let mutedText = Color.secondary.opacity(0.86)
        static let accent = Color(nsColor: NSColor(name: nil) { appearance in
            appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
                ? NSColor(calibratedRed: 0.820, green: 0.560, blue: 0.360, alpha: 1)
                : NSColor(calibratedRed: 0.620, green: 0.330, blue: 0.180, alpha: 1)
        })
        static let accentSoft = accent.opacity(0.115)
        static let success = Color(nsColor: .systemGreen)
        static let warning = Color(nsColor: .systemOrange)
        static let danger = Color(nsColor: .systemRed)
    }

    enum Space {
        static let xxs: CGFloat = 4
        static let xs: CGFloat = 6
        static let sm: CGFloat = 8
        static let md: CGFloat = 12
        static let lg: CGFloat = 16
        static let xl: CGFloat = 24
        static let xxl: CGFloat = 32
        static let page: CGFloat = 40
    }

    enum Radius {
        static let sm: CGFloat = 6
        static let md: CGFloat = 8
        static let lg: CGFloat = 12
    }

    static let readingWidth: CGFloat = 820
    static let composerWidth: CGFloat = 860
}

struct AriadneDivider: View {
    var body: some View {
        Rectangle()
            .fill(AriadneDesign.ColorToken.softLine)
            .frame(height: 1)
    }
}

struct AriadneSectionLabel: View {
    let title: String
    var detail: String? = nil

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: AriadneDesign.Space.sm) {
            Text(title)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
            if let detail {
                Text(detail)
                    .font(.system(size: 11))
                    .foregroundStyle(.tertiary)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
        }
    }
}

struct AriadneBadge: View {
    let text: String
    var color: Color = AriadneDesign.ColorToken.accent

    var body: some View {
        Text(text)
            .font(.system(size: 10, weight: .medium))
            .foregroundStyle(color)
            .padding(.horizontal, 7)
            .padding(.vertical, 3)
            .background(color.opacity(0.12), in: Capsule())
            .overlay(Capsule().stroke(color.opacity(0.18), lineWidth: 1))
    }
}

struct AriadneIconButtonStyle: ButtonStyle {
    var isSelected = false

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .foregroundStyle(isSelected ? AriadneDesign.ColorToken.accent : .secondary)
            .frame(width: 26, height: 26)
            .background(
                RoundedRectangle(cornerRadius: AriadneDesign.Radius.sm, style: .continuous)
                    .fill(isSelected || configuration.isPressed ? AriadneDesign.ColorToken.accentSoft : Color.clear)
            )
    }
}
