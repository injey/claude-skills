// Render PDF pages to PNG with macOS PDFKit, for visual checks without poppler.
// Usage: swift pdf_pages.swift <file.pdf> <out-dir> [pages e.g. 1,5,9]
import PDFKit
import AppKit
let args = CommandLine.arguments
guard args.count >= 3, let doc = PDFDocument(url: URL(fileURLWithPath: args[1])) else {
  print("usage: swift pdf_pages.swift <file.pdf> <out-dir> [1,5,9]"); exit(1)
}
let outDir = args[2]
try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)
let wanted: [Int] = args.count > 3 ? args[3].split(separator: ",").compactMap { Int($0) } : Array(1...doc.pageCount)
print("pages: \(doc.pageCount)")
for n in wanted where n >= 1 && n <= doc.pageCount {
  let page = doc.page(at: n - 1)!
  let r = page.bounds(for: .mediaBox)
  let scale: CGFloat = 1.4
  let img = NSImage(size: NSSize(width: r.width * scale, height: r.height * scale))
  img.lockFocus()
  NSColor.white.set(); NSRect(x: 0, y: 0, width: r.width * scale, height: r.height * scale).fill()
  let ctx = NSGraphicsContext.current!.cgContext
  ctx.scaleBy(x: scale, y: scale)
  page.draw(with: .mediaBox, to: ctx)
  img.unlockFocus()
  let png = NSBitmapImageRep(data: img.tiffRepresentation!)!.representation(using: .png, properties: [:])!
  let path = "\(outDir)/p\(String(format: "%02d", n)).png"
  try! png.write(to: URL(fileURLWithPath: path))
  print(path)
}
