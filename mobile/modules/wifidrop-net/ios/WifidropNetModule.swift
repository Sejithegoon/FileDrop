import CryptoKit
import ExpoModulesCore
import Foundation
import Network
import Security

// Talks to the WiFiDrop PC over HTTPS. The PC makes its own certificate, so instead of the usual
// certificate authorities we trust exactly one key: the one whose SHA-256 "pin" came from the PC's
// QR code (or that the person confirmed by comparing the code shown on the PC).

struct RequestOptions: Record {
  @Field var url: String = ""
  @Field var method: String = "GET"
  @Field var headers: [String: String] = [:]
  @Field var body: String? = nil
  @Field var bodyFile: String? = nil  // send part of a file instead (upload chunks)
  @Field var bodyOffset: Double = 0
  @Field var bodyLength: Double = -1  // -1: to the end of the file
  @Field var pin: String = ""
  @Field var timeoutMs: Double = 30000
}

struct DownloadOptions: Record {
  @Field var id: String = ""
  @Field var url: String = ""
  @Field var headers: [String: String] = [:]
  @Field var destination: String = ""
  @Field var pin: String = ""
}

enum NetError: Error {
  case badUrl
  case pinMismatch
  case noKey
}

enum Pin {
  // DER prefix of a SubjectPublicKeyInfo for an EC P-256 key; the PC always makes a P-256 key.
  static let p256Header: [UInt8] = [
    0x30, 0x59, 0x30, 0x13, 0x06, 0x07, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x02, 0x01,
    0x06, 0x08, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07, 0x03, 0x42, 0x00,
  ]

  /// base64url(SHA-256(SubjectPublicKeyInfo)) of the server's key, matching the PC's tls.public_key_pin.
  static func of(_ trust: SecTrust) -> String? {
    guard let chain = SecTrustCopyCertificateChain(trust) as? [SecCertificate], let leaf = chain.first,
          let key = SecCertificateCopyKey(leaf),
          let attrs = SecKeyCopyAttributes(key) as? [CFString: Any],
          (attrs[kSecAttrKeyType] as? String) == (kSecAttrKeyTypeECSECPrimeRandom as String),
          (attrs[kSecAttrKeySizeInBits] as? Int) == 256,
          let raw = SecKeyCopyExternalRepresentation(key, nil) as Data?
    else { return nil }
    let digest = SHA256.hash(data: Data(p256Header) + raw)
    return Data(digest).base64EncodedString()
      .replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_")
      .replacingOccurrences(of: "=", with: "")
  }
}

final class PinDelegate: NSObject, URLSessionTaskDelegate {
  let expected: String?  // nil: just record the key (probe)
  var seen: String?
  var mismatch = false
  var onProgress: ((Int64, Int64) -> Void)?
  private var observation: NSKeyValueObservation?

  init(expected: String?) {
    self.expected = expected
  }

  func urlSession(_ session: URLSession, didCreateTask task: URLSessionTask) {
    guard let onProgress else { return }
    observation = task.progress.observe(\.completedUnitCount) { progress, _ in
      onProgress(progress.completedUnitCount, progress.totalUnitCount)
    }
  }

  func urlSession(_ session: URLSession, task: URLSessionTask, didReceive challenge: URLAuthenticationChallenge,
                  completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
    guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
          let trust = challenge.protectionSpace.serverTrust
    else {
      completionHandler(.performDefaultHandling, nil)
      return
    }
    seen = Pin.of(trust)
    if let seen, expected == nil || seen == expected {
      completionHandler(.useCredential, URLCredential(trust: trust))
    } else {
      mismatch = true
      completionHandler(.cancelAuthenticationChallenge, nil)
    }
  }
}

enum Net {
  static let session: URLSession = {
    let config = URLSessionConfiguration.ephemeral
    config.httpShouldSetCookies = false
    config.httpCookieStorage = nil
    config.urlCache = nil
    config.waitsForConnectivity = false
    return URLSession(configuration: config)
  }()

  static func fileURL(_ s: String) -> URL {
    if s.hasPrefix("file:"), let url = URL(string: s) { return url }
    return URL(fileURLWithPath: s)
  }

  static func makeRequest(_ urlString: String, method: String, headers: [String: String], timeoutMs: Double) throws -> URLRequest {
    guard let url = URL(string: urlString), url.scheme == "https" else { throw NetError.badUrl }
    var req = URLRequest(url: url, timeoutInterval: max(1, timeoutMs / 1000))
    req.httpMethod = method
    for (k, v) in headers { req.setValue(v, forHTTPHeaderField: k) }
    return req
  }

  static func readSlice(_ file: String, offset: Double, length: Double) throws -> Data {
    let handle = try FileHandle(forReadingFrom: fileURL(file))
    defer { try? handle.close() }
    try handle.seek(toOffset: UInt64(offset))
    if length < 0 { return try handle.readToEnd() ?? Data() }
    return try handle.read(upToCount: Int(length)) ?? Data()
  }

  static func headerMap(_ r: HTTPURLResponse) -> [String: String] {
    var out: [String: String] = [:]
    for (k, v) in r.allHeaderFields { out["\(k)".lowercased()] = "\(v)" }
    return out
  }

  static func request(_ o: RequestOptions) async throws -> [String: Any] {
    var req = try makeRequest(o.url, method: o.method, headers: o.headers, timeoutMs: o.timeoutMs)
    if let body = o.body {
      req.httpBody = Data(body.utf8)
    } else if let file = o.bodyFile {
      req.httpBody = try readSlice(file, offset: o.bodyOffset, length: o.bodyLength)
    }
    let delegate = PinDelegate(expected: o.pin)
    do {
      let (data, response) = try await session.data(for: req, delegate: delegate)
      let http = response as! HTTPURLResponse
      return ["status": http.statusCode, "headers": headerMap(http), "body": String(decoding: data, as: UTF8.self)]
    } catch {
      if delegate.mismatch { throw NetError.pinMismatch }
      throw error
    }
  }

  static func probe(_ urlString: String) async throws -> [String: Any] {
    let req = try makeRequest(urlString, method: "GET", headers: ["X-WiFiDrop": "1"], timeoutMs: 8000)
    let delegate = PinDelegate(expected: nil)
    let (data, response) = try await session.data(for: req, delegate: delegate)
    guard let pin = delegate.seen else { throw NetError.noKey }
    let http = response as! HTTPURLResponse
    return ["pin": pin, "status": http.statusCode, "body": String(decoding: data, as: UTF8.self)]
  }

  static func download(_ o: DownloadOptions, progress: @escaping (Int64, Int64) -> Void) async throws -> [String: Any] {
    let req = try makeRequest(o.url, method: "GET", headers: o.headers, timeoutMs: 60000)
    let delegate = PinDelegate(expected: o.pin)
    delegate.onProgress = progress
    let tmp: URL
    let response: URLResponse
    do {
      (tmp, response) = try await session.download(for: req, delegate: delegate)
    } catch {
      if delegate.mismatch { throw NetError.pinMismatch }
      throw error
    }
    let http = response as! HTTPURLResponse
    let fm = FileManager.default
    if http.statusCode >= 400 {
      let body = (try? String(contentsOf: tmp, encoding: .utf8)) ?? ""
      try? fm.removeItem(at: tmp)
      return ["status": http.statusCode, "body": body]
    }
    let dest = fileURL(o.destination)
    try fm.createDirectory(at: dest.deletingLastPathComponent(), withIntermediateDirectories: true)
    try? fm.removeItem(at: dest)
    try fm.moveItem(at: tmp, to: dest)
    let attributes = try? fm.attributesOfItem(atPath: dest.path)
    let size = (attributes?[.size] as? NSNumber)?.int64Value ?? 0
    return ["status": http.statusCode, "uri": dest.absoluteString, "bytes": size]
  }
}

public class WifidropNetModule: Module {
  private var browser: NWBrowser?

  public func definition() -> ModuleDefinition {
    Name("WifidropNet")

    Events("onProgress", "onServiceFound", "onServiceLost", "onDiscoveryError")

    AsyncFunction("request") { (options: RequestOptions, promise: Promise) in
      Task { await Self.settle(promise) { try await Net.request(options) } }
    }

    AsyncFunction("probe") { (url: String, promise: Promise) in
      Task { await Self.settle(promise) { try await Net.probe(url) } }
    }

    AsyncFunction("download") { (options: DownloadOptions, promise: Promise) in
      Task {
        await Self.settle(promise) {
          try await Net.download(options) { [weak self] written, total in
            self?.sendEvent("onProgress", ["id": options.id, "written": written, "total": total])
          }
        }
      }
    }

    Function("startDiscovery") {
      self.startDiscovery()
    }

    Function("stopDiscovery") {
      self.browser?.cancel()
      self.browser = nil
    }

    OnDestroy {
      self.browser?.cancel()
    }
  }

  private static func settle(_ promise: Promise, _ work: () async throws -> [String: Any]) async {
    do {
      promise.resolve(try await work())
    } catch NetError.pinMismatch {
      promise.reject("PIN_MISMATCH", "This isn't the PC you paired with (its security key changed).")
    } catch NetError.badUrl {
      promise.reject("BAD_URL", "That address isn't a WiFiDrop link.")
    } catch NetError.noKey {
      promise.reject("NO_KEY", "The PC didn't present a WiFiDrop security key.")
    } catch let error as URLError {
      let code = error.code == .timedOut ? "TIMEOUT" : error.code == .notConnectedToInternet ? "OFFLINE" : "NETWORK"
      promise.reject(code, error.localizedDescription)
    } catch {
      promise.reject("NETWORK", error.localizedDescription)
    }
  }

  private func startDiscovery() {
    browser?.cancel()
    let parameters = NWParameters()
    parameters.includePeerToPeer = false
    let b = NWBrowser(for: .bonjourWithTXTRecord(type: "_wifidrop._tcp", domain: "local."), using: parameters)
    b.browseResultsChangedHandler = { [weak self] _, changes in
      for change in changes {
        switch change {
        case .added(let result):
          self?.report(result)
        case .changed(_, let result, _):
          self?.report(result)
        case .removed(let result):
          if case let .service(name, _, _, _) = result.endpoint {
            self?.sendEvent("onServiceLost", ["name": name])
          }
        default:
          break
        }
      }
    }
    b.stateUpdateHandler = { [weak self] state in
      switch state {
      case .failed(let error), .waiting(let error):
        // .waiting with a policy error means the person turned off Local Network access for the app.
        self?.sendEvent("onDiscoveryError", ["message": "\(error)"])
      default:
        break
      }
    }
    b.start(queue: .main)
    browser = b
  }

  private func report(_ result: NWBrowser.Result) {
    guard case let .service(name, _, _, _) = result.endpoint else { return }
    var txt: [String: String] = [:]
    if case let .bonjour(record) = result.metadata {
      txt = record.dictionary
    }
    sendEvent("onServiceFound", ["name": name, "txt": txt])
  }
}
