// Picks the icon whose meaning best matches a renamed tab's name using Apple's
// on-device model, for the "apple-foundation-model" icon mode in tab_bar.py.
// tab_bar.py compiles it on first use and passes the icons, so they are only
// defined there.
//
// Usage: tab-icon '{"name": "...", "icons": [{"id": "...", "meaning": "..."}, ...]}'
//
// Prints the chosen icon's id. Exits with 2 if the model refuses to choose for
// the name and 3 if the model is unavailable on this Mac.

import Foundation
import FoundationModels

struct Icon: Decodable {
    let id: String
    let meaning: String
}

struct Request: Decodable {
    let name: String
    let icons: [Icon]
}

func fail(_ message: String, _ code: Int32) -> Never {
    FileHandle.standardError.write(Data("\(message)\n".utf8))
    exit(code)
}

guard CommandLine.arguments.count == 2,
    let request = try? JSONDecoder().decode(
        Request.self, from: Data(CommandLine.arguments[1].utf8)),
    !request.icons.isEmpty
else {
    fail("Usage: tab-icon '{\"name\": ..., \"icons\": [{\"id\": ..., \"meaning\": ...}]}'", 1)
}

let model = SystemLanguageModel.default
guard case .available = model.availability else {
    fail("Model unavailable: \(model.availability)", 3)
}

let icons = request.icons.map { "\($0.id): \($0.meaning)" }.joined(separator: "\n")
let instructions = """
    Choose an icon for a terminal tab. Choose the icon whose meaning best matches \
    the tab's name. Consider what the name literally says, what kind of work it \
    suggests, and any well-known associations. If nothing fits well, choose the \
    closest in mood or theme.

    Icons:
    \(icons)
    """

// Constrains the model to answer with one of the icon ids
let schema = try GenerationSchema(
    root: DynamicGenerationSchema(name: "Icon", anyOf: request.icons.map(\.id)),
    dependencies: [])

// Whether the model will always refuse to choose for this name, as opposed to
// errors that may not happen again, such as rate limiting
func isRefusal(_ error: Error) -> Bool {
    // macOS 27 replaced GenerationError with LanguageModelError, and Swift 6.4
    // is the first compiler shipped with the macOS 27 SDK
    #if compiler(>=6.4)
        if #available(macOS 27.0, *), let error = error as? LanguageModelError {
            switch error {
            case .guardrailViolation, .refusal, .unsupportedLanguageOrLocale: return true
            default: return false
            }
        }
    #else
        if let error = error as? LanguageModelSession.GenerationError {
            switch error {
            case .guardrailViolation, .refusal, .unsupportedLanguageOrLocale: return true
            default: return false
            }
        }
    #endif
    return false
}

do {
    let session = LanguageModelSession(instructions: instructions)
    let response = try await session.respond(to: "Tab name: \(request.name)", schema: schema)
    print(try response.content.value(String.self))
} catch {
    fail("\(error)", isRefusal(error) ? 2 : 1)
}
