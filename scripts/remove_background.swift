import AppKit
import CoreImage
import CoreImage.CIFilterBuiltins
import Foundation
import Vision

enum BackgroundRemovalError: Error {
    case invalidArguments
    case couldNotLoadImage
    case couldNotGenerateMask
    case couldNotRenderImage
    case couldNotEncodePNG
}

guard CommandLine.arguments.count == 3 else {
    throw BackgroundRemovalError.invalidArguments
}

let inputURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])

guard let sourceImage = CIImage(contentsOf: inputURL) else {
    throw BackgroundRemovalError.couldNotLoadImage
}

let request = VNGenerateForegroundInstanceMaskRequest()
let handler = VNImageRequestHandler(ciImage: sourceImage)
try handler.perform([request])

guard
    let observation = request.results?.first,
    let maskBuffer = try? observation.generateScaledMaskForImage(forInstances: observation.allInstances, from: handler)
else {
    throw BackgroundRemovalError.couldNotGenerateMask
}

let maskImage = CIImage(cvPixelBuffer: maskBuffer)
let clearBackground = CIImage(color: .clear).cropped(to: sourceImage.extent)

let filter = CIFilter.blendWithMask()
filter.inputImage = sourceImage
filter.backgroundImage = clearBackground
filter.maskImage = maskImage

let context = CIContext()
guard
    let outputImage = filter.outputImage,
    let cgImage = context.createCGImage(outputImage, from: outputImage.extent)
else {
    throw BackgroundRemovalError.couldNotRenderImage
}

let bitmap = NSBitmapImageRep(cgImage: cgImage)
guard let pngData = bitmap.representation(using: .png, properties: [:]) else {
    throw BackgroundRemovalError.couldNotEncodePNG
}

try pngData.write(to: outputURL)
