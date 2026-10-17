import Foundation
import CoreText

struct ProbeError: Error, CustomStringConvertible {
    let description: String
}

struct Coverage: Codable {
    let checked: Int
    let covered: Int
    let missing: [String]
}

struct Measurement: Codable {
    let text: String
    let logicalSize: Double
    let width: Double
    let ascent: Double
    let descent: Double
}

struct FontReport: Codable {
    let fontPostScriptName: String
    let baselinePostScriptName: String
    let hangulSyllables: Coverage
    let modernAndExtendedJamo: Coverage
    let baselineHangulSyllables: Coverage
    let measurements: [Measurement]
    let rendererLaunched: Bool
    let measurementEngine: String
}

func loadFont(_ path: String, size: CGFloat) throws -> CTFont {
    let url = URL(fileURLWithPath: path)
    guard let descriptors = CTFontManagerCreateFontDescriptorsFromURL(url as CFURL) as? [CTFontDescriptor],
          descriptors.count == 1, let descriptor = descriptors.first else {
        throw ProbeError(description: "Expected one readable font face")
    }
    return CTFontCreateWithFontDescriptor(descriptor, size, nil)
}

func coverage(_ font: CTFont, codepoints: [UInt16]) -> Coverage {
    var glyphs = [CGGlyph](repeating: 0, count: codepoints.count)
    CTFontGetGlyphsForCharacters(font, codepoints, &glyphs, codepoints.count)
    let missing = zip(codepoints, glyphs).filter { $0.1 == 0 }.map {
        String(format: "U+%04X", $0.0)
    }
    return Coverage(checked: codepoints.count, covered: codepoints.count - missing.count, missing: missing)
}

func measure(_ font: CTFont, text: String, size: Double) -> Measurement {
    let resized = CTFontCreateCopyWithAttributes(font, size, nil, nil)
    let string = NSAttributedString(string: text,
        attributes: [NSAttributedString.Key(kCTFontAttributeName as String): resized])
    let line = CTLineCreateWithAttributedString(string)
    var ascent: CGFloat = 0, descent: CGFloat = 0, leading: CGFloat = 0
    let width = CTLineGetTypographicBounds(line, &ascent, &descent, &leading)
    return Measurement(text: text, logicalSize: size, width: width,
                       ascent: Double(ascent), descent: Double(descent))
}

func run() throws {
    guard CommandLine.arguments.count == 4 else {
        throw ProbeError(description: "Usage: font_probe.swift FONT BASELINE_FONT NEW_REPORT.json")
    }
    let font = try loadFont(CommandLine.arguments[1], size: 28)
    let baseline = try loadFont(CommandLine.arguments[2], size: 28)
    let syllables = Array(UInt16(0xAC00)...UInt16(0xD7A3))
    let jamo = Array(UInt16(0x1100)...UInt16(0x11FF)) + Array(UInt16(0x3131)...UInt16(0x318E))
    let samples = ["새 게임", "불러오기", "환경설정", "마을에 도착했다. 주변을 둘러보자."]
    let measurements = [18.0, 26.0, 28.0].flatMap { size in
        samples.map { measure(font, text: $0, size: size) }
    }
    let report = FontReport(fontPostScriptName: CTFontCopyPostScriptName(font) as String,
        baselinePostScriptName: CTFontCopyPostScriptName(baseline) as String,
        hangulSyllables: coverage(font, codepoints: syllables),
        modernAndExtendedJamo: coverage(font, codepoints: jamo),
        baselineHangulSyllables: coverage(baseline, codepoints: syllables),
        measurements: measurements, rendererLaunched: false,
        measurementEngine: "CoreText font metrics; browser canvas and dialog wrapping not tested")
    let output = URL(fileURLWithPath: CommandLine.arguments[3])
    guard !FileManager.default.fileExists(atPath: output.path) else {
        throw ProbeError(description: "Report already exists")
    }
    guard report.hangulSyllables.missing.isEmpty else {
        throw ProbeError(description: "The bundled font is missing Hangul syllables")
    }
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    try encoder.encode(report).write(to: output, options: .atomic)
    print("Hangul \(report.hangulSyllables.covered)/\(report.hangulSyllables.checked); renderer not launched")
}

do {
    try run()
} catch {
    FileHandle.standardError.write(Data("\(error)\n".utf8))
    exit(1)
}
